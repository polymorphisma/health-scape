import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from src.base_scraper import JobScraper


# Keyword → canonical client category label
KEYWORD_CATEGORY_MAP = {
    'nurse':              'Nursing',
    'aged care':          'Aged Care',
    'disability support': 'Disability Support',
    'allied health':      'Allied Health',
    'support worker':     'Disability Support',
}

PAGE_DELAY = 2.0  # seconds between page requests


class JoraScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("jora", base_dir)
        self.base_url = "https://au.jora.com"
        self.max_pages = 5  # POC cap

        self.session.headers.update({
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-AU,en;q=0.9',
            'user-agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
        })

    def run(self, search_terms: Optional[List[str]] = None) -> None:
        """Scrapes Jora by keyword. All fields extracted from listing page HTML."""
        if search_terms is None:
            search_terms = list(KEYWORD_CATEGORY_MAP.keys())

        for keyword in search_terms:
            category_label = KEYWORD_CATEGORY_MAP.get(keyword, 'Healthcare')
            self.logger.info(f"Starting Jora scrape: '{keyword}' → {category_label}")
            slug = keyword.title().replace(' ', '-')
            page_1_url = f"{self.base_url}/{slug}-jobs"

            page = 1
            total_pages = None

            while page <= self.max_pages:
                self.logger.info(f"Fetching page {page} for '{keyword}'")
                try:
                    params = {'disallow': 'true', 'sp': 'recent_homepage', 'pt': 'unseen'}
                    if page > 1:
                        params['p'] = str(page)

                    response = self._make_request(
                        'GET', page_1_url, params=params,
                        headers={'Referer': page_1_url}
                    )
                    html = response.text
                    jobs, total_pages_found = self._parse_listing(html, category_label)

                    if not jobs:
                        self.logger.info(f"No jobs on page {page} for '{keyword}'. Stopping.")
                        break

                    self.logger.info(f"Found {len(jobs)} jobs on page {page}.")

                    if total_pages is None and total_pages_found:
                        total_pages = min(total_pages_found, self.max_pages)
                        self.logger.info(
                            f"Total pages available: {total_pages_found} (capped at {self.max_pages})"
                        )

                    identifier = f"{keyword.replace(' ', '_')}_p{page}"
                    self.save_raw_data({"category": category_label, "data": jobs}, identifier)

                    if total_pages and page >= total_pages:
                        break

                    page += 1
                    time.sleep(PAGE_DELAY)

                except Exception as e:
                    self.logger.error(f"Failed on '{keyword}' page {page}: {e}", exc_info=True)
                    break

    def _parse_listing(self, html: str, category_label: str) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Parses Jora listing HTML. Returns (jobs, total_pages)."""
        soup = BeautifulSoup(html, 'html.parser')

        # Primary: div.job-card (confirmed class on Jora AU)
        cards = soup.find_all('div', class_='job-card')

        # Fallback: divs with id="r_{hex}" pattern
        if not cards:
            cards = [el for el in soup.find_all('div', id=re.compile(r'^r_[a-f0-9]+$'))]

        jobs = []
        seen_urls = set()
        for card in cards:
            job = self._extract_card(card, category_label)
            if job and job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                jobs.append(job)

        total_pages = self._extract_total_pages(soup)
        return jobs, total_pages

    def _extract_card(self, card, category_label: str) -> Optional[Dict[str, Any]]:
        """Extracts all job fields from a single job card element."""
        # --- Job URL ---
        title_h2 = card.find('h2', class_='job-title')
        link = title_h2.find('a') if title_h2 else card.find('a', href=re.compile(r'^/job/'))
        if not link:
            return None

        clean_path = link.get('href', '').split('?')[0]
        job_url = f"{self.base_url}{clean_path}"

        # --- Job ID ---
        card_id = card.get('id', '')
        job_id = card_id[2:] if card_id.startswith('r_') else clean_path.split('/')[-1]

        # --- Job Title ---
        title_text = link.get_text(separator=' ', strip=True)
        # Jora DOM duplicates the title text in the link (e.g., "Nurse Nurse" → "Nurse")
        words = title_text.split()
        half = len(words) // 2
        if half > 0 and words[:half] == words[half:]:
            title_text = ' '.join(words[:half])
        if not title_text:
            return None

        # --- Company Name ---
        company_el = card.find('span', class_='job-company')
        facility_name = company_el.get_text(strip=True) if company_el else 'Unknown Facility'

        # --- Location ---
        location_el = card.find('a', class_='job-location') or card.find(class_='job-location')
        location_str = location_el.get_text(strip=True) if location_el else ''
        city, state = self._parse_location(location_str)

        # --- Date Posted ---
        date_el = card.find('span', class_='job-listed-date')
        date_text = date_el.get_text(strip=True) if date_el else ''
        date_posted = self._parse_relative_date(date_text)

        return {
            'id':            job_id,
            'title':         title_text,
            'facility_name': facility_name,
            'category':      category_label,
            'state':         state,
            'city':          city,
            'date_posted':   date_posted,
            'url':           job_url,
            'raw_location':  location_str,
        }

    def _parse_location(self, location_str: str) -> Tuple[str, str]:
        """Parses 'Brisbane QLD' → (city='Brisbane', state='QLD')."""
        if not location_str:
            return '', 'Unknown'

        state_abbrevs = {'NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'}
        parts = location_str.strip().split()

        if parts and parts[-1].upper() in state_abbrevs:
            return ' '.join(parts[:-1]), parts[-1].upper()

        for part in parts:
            if part.upper() in state_abbrevs:
                return location_str.replace(part, '').strip(), part.upper()

        return location_str, 'Unknown'

    def _parse_relative_date(self, text: str) -> str:
        """Converts '2h ago', '3d ago', '1w ago' → ISO date string."""
        now = datetime.now()
        if not text:
            return now.strftime('%Y-%m-%d')

        m = re.search(r'(\d+)\s*([hdwm])\s+ago', text.lower())
        if not m:
            return now.strftime('%Y-%m-%d')

        n, unit = int(m.group(1)), m.group(2)
        deltas = {'h': timedelta(hours=n), 'd': timedelta(days=n),
                  'w': timedelta(weeks=n), 'm': timedelta(days=n * 30)}
        return (now - deltas.get(unit, timedelta(0))).strftime('%Y-%m-%d')

    def _extract_total_pages(self, soup: BeautifulSoup) -> Optional[int]:
        """Extracts total page count from 'Page X of Y' text."""
        page_text = soup.find(string=re.compile(r'Page\s+\d+\s+of\s+\d+', re.I))
        if page_text:
            m = re.search(r'Page\s+\d+\s+of\s+(\d+)', page_text, re.I)
            if m:
                return int(m.group(1))
        return None


if __name__ == "__main__":
    scraper = JoraScraper(base_dir=".")
    scraper.run(['nurse', 'aged care', 'disability support', 'allied health', 'support worker'])
