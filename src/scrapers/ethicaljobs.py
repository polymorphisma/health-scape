import re
import json
import math
import time
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from src.base_scraper import JobScraper


# Keyword → canonical client category label
KEYWORD_CATEGORY_MAP = {
    'nurse':             'Nursing',
    'aged care':         'Aged Care',
    'disability support':'Disability Support',
    'allied health':     'Allied Health',
    'support worker':    'Disability Support',
}

# EthicalJobs location name → AU state abbreviation
LOCATION_STATE_MAP = {
    'sydney':                    'NSW',
    'regional nsw':              'NSW',
    'melbourne':                 'VIC',
    'regional vic':              'VIC',
    'brisbane & gold coast':     'QLD',
    'regional qld':              'QLD',
    'perth':                     'WA',
    'regional wa':               'WA',
    'adelaide':                  'SA',
    'regional sa':               'SA',
    'hobart':                    'TAS',
    'regional tas':              'TAS',
    'canberra & act':            'ACT',
    'act':                       'ACT',
    'darwin':                    'NT',
    'regional nt':               'NT',
    'remote':                    'Unknown',
    'australia wide':            'Unknown',
    'work from home':            'Unknown',
    'flexible / work from home': 'Unknown',
}

JOBS_PER_PAGE = 30   # confirmed via RSC payload
DETAIL_DELAY  = 0.5  # seconds between detail page requests


class EthicalJobsScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("ethicaljobs", base_dir)
        self.base_url = "https://www.ethicaljobs.com.au"
        self.search_url = f"{self.base_url}/jobs"

        self.session.headers.update({
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-GB,en;q=0.8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        })

        self.max_pages = 5  # POC cap

    def run(self, search_terms: Optional[List[str]] = None) -> None:
        """
        Scrapes EthicalJobs by keyword. Category inferred from keyword.
        Fetches each job's detail page to extract the real 'approvedAt' posting date.
        """
        if search_terms is None:
            search_terms = list(KEYWORD_CATEGORY_MAP.keys())

        for keyword in search_terms:
            category_label = KEYWORD_CATEGORY_MAP.get(keyword, 'Healthcare')
            self.logger.info(f"Starting scrape for keyword: '{keyword}' → category: {category_label}")

            page = 1
            total_pages = None

            while page <= self.max_pages:
                self.logger.info(f"Fetching page {page} for keyword '{keyword}'")
                try:
                    response = self._make_request(
                        'GET', self.search_url,
                        params={'keywords': keyword, 'page': page}
                    )
                    jobs, total = self._parse_listing_rsc(response.text)

                    if not jobs:
                        self.logger.info(f"No jobs on page {page} for '{keyword}'. Stopping.")
                        break

                    self.logger.info(f"Found {len(jobs)} jobs (total available: {total}). Fetching detail pages...")
                    self._enrich_with_detail(jobs)

                    identifier = f"{keyword.replace(' ', '_')}_p{page}"
                    self.save_raw_data({"category": category_label, "data": jobs}, identifier)

                    if total_pages is None and total:
                        total_pages = math.ceil(total / JOBS_PER_PAGE)

                    if total_pages and page >= total_pages:
                        break

                    page += 1

                except Exception as e:
                    self.logger.error(f"Failed on '{keyword}' page {page}: {e}", exc_info=True)
                    break

    def _enrich_with_detail(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Fetches each job's detail page and merges ALL available fields into the job dict.
        This ensures raw dumps are complete — future fields can be pulled without re-scraping.
        Mutates jobs in place. Skips gracefully on individual failures.
        """
        for job in jobs:
            url = job.get('url', '')
            if not url:
                continue
            try:
                time.sleep(DETAIL_DELAY)
                resp = self._make_request('GET', url)
                detail = self._extract_detail_fields(resp.text)
                if detail:
                    # Merge all detail fields; listing fields take precedence for shared keys
                    # except approvedAt which only exists on the detail page
                    job.update({k: v for k, v in detail.items() if k not in job or job[k] is None})
                    self.logger.debug(f"Enriched job {job['id']} with {len(detail)} detail fields")
            except Exception as e:
                self.logger.warning(f"Could not fetch detail for {url}: {e}")

    def _extract_detail_fields(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extracts the full job object from the detail page RSC payload.
        Structure: parsed[3]['job'] on the line containing 'approvedAt' + 'applyMethod'.
        Falls back to scraping 'Job posted on:' from HTML for approvedAt only.
        """
        soup = BeautifulSoup(html, 'html.parser')
        chunks = []
        for script in soup.find_all('script'):
            text = script.string or ''
            for m in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', text, re.DOTALL):
                try:
                    chunks.append(m.encode('utf-8').decode('unicode_escape'))
                except Exception:
                    chunks.append(m)

        payload = ''.join(chunks)

        # The detail job object sits inside a large RSC chunk that contains HTML fields
        # (description, application) with newlines — so line-splitting breaks JSON parsing.
        # Instead, find the "job":{...} object directly using the JSON decoder's raw_decode.
        marker = '"job":{'
        idx = payload.find(marker)
        if idx != -1:
            try:
                decoder = json.JSONDecoder()
                job_obj, _ = decoder.raw_decode(payload, idx + len(marker) - 1)
                if isinstance(job_obj, dict) and 'approvedAt' in job_obj:
                    return job_obj
            except Exception:
                pass

        # HTML fallback — extract only approvedAt
        for el in soup.find_all(['li', 'div', 'span', 'p']):
            text = el.get_text(separator=' ', strip=True)
            m = re.search(r'[Jj]ob posted on[:\s]+(\d+\w*\s+\w+\s+\d{4})', text)
            if m:
                return {'approvedAt': self._parse_human_date(m.group(1))}

        return None

    def _parse_human_date(self, date_str: str) -> Optional[str]:
        """Converts '3rd Feb 2026' → '2026-02-03'."""
        from datetime import datetime
        # Strip ordinal suffixes: 3rd → 3, 1st → 1, etc.
        clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str.strip())
        for fmt in ('%d %b %Y', '%d %B %Y'):
            try:
                return datetime.strptime(clean, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    def _parse_listing_rsc(self, html: str):
        """
        Extracts job list from the search results page RSC payload.
        Returns: (list of normalised job dicts, total count)
        """
        soup = BeautifulSoup(html, 'html.parser')
        chunks = []
        for script in soup.find_all('script'):
            text = script.string or ''
            for m in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', text, re.DOTALL):
                try:
                    chunks.append(m.encode('utf-8').decode('unicode_escape'))
                except Exception:
                    chunks.append(m)

        payload = ''.join(chunks)
        for line in payload.split('\n'):
            json_part = re.sub(r'^[0-9a-f]+:', '', line.strip())
            if not json_part or json_part[0] not in ('{', '['):
                continue
            try:
                parsed = json.loads(json_part)
                raw = json.dumps(parsed)
                if 'expiresAt' in raw and 'organisationName' in raw and 'locations' in raw:
                    jobs_data = parsed[3] if isinstance(parsed, list) and len(parsed) > 3 else {}
                    if not isinstance(jobs_data, dict):
                        continue
                    jobs = [self._normalize(j) for j in jobs_data.get('jobs', [])]
                    return jobs, jobs_data.get('total')
            except Exception:
                continue

        return [], None

    def _normalize(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Keeps ALL raw fields from the listing RSC, and adds computed helpers.
        Detail page fields are merged in later by _enrich_with_detail().
        """
        slug = job.get('slug', '')
        locations = job.get('locations', [])
        location_name = locations[0].get('name', '') if locations else ''
        locality = locations[0].get('locality', '') if locations else ''

        title = job.get('title', '')
        if ' - ' in title:
            title = title.rsplit(' - ', 1)[0].strip()

        return {
            # --- all raw listing fields preserved ---
            **job,
            # --- computed / cleaned helpers (override raw where needed) ---
            'title':         title,
            'location_name': location_name,
            'locality':      locality,
            'state':         LOCATION_STATE_MAP.get(location_name.lower(), 'Unknown'),
            'url':           f"{self.base_url}/members/{slug}" if slug else '',
            # detail-page fields default to None until enrichment runs
            'approvedAt':    None,
        }


if __name__ == "__main__":
    scraper = EthicalJobsScraper(base_dir=".")
    scraper.run(['nurse', 'aged care', 'disability support', 'allied health'])
