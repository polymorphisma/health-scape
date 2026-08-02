import time
from typing import List, Dict, Any, Optional
from src.base_scraper import JobScraper


KEYWORD_CATEGORY_MAP = {
    'nurse':              'Nursing',
    'aged care':          'Aged Care',
    'disability support': 'Disability Support',
    'allied health':      'Allied Health',
    'support worker':     'Disability Support',
}

# Full state name → abbreviation (as returned in location.area[1])
STATE_NAME_MAP = {
    'new south wales':              'NSW',
    'victoria':                     'VIC',
    'queensland':                   'QLD',
    'western australia':            'WA',
    'south australia':              'SA',
    'tasmania':                     'TAS',
    'australian capital territory': 'ACT',
    'northern territory':           'NT',
}

APP_ID  = "fef86366"
APP_KEY = "a4f2dcf93901b959d42323d5029cfdb0"

API_URL          = "https://api.adzuna.com/v1/api/jobs/au/search/{page}"
RESULTS_PER_PAGE = 50
PAGE_DELAY       = 1.0


class AdzunaScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("adzuna", base_dir)
        self.max_pages = 5

        self.session.headers.update({
            'accept':          'application/json',
            'accept-language': 'en-AU,en;q=0.9',
            'user-agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
        })

    def run(self, search_terms: Optional[List[str]] = None) -> None:
        if search_terms is None:
            search_terms = list(KEYWORD_CATEGORY_MAP.keys())

        for keyword in search_terms:
            category_label = KEYWORD_CATEGORY_MAP.get(keyword, 'Healthcare')
            self.logger.info(f"Starting Adzuna AU scrape: '{keyword}' → {category_label}")

            all_jobs: List[Dict[str, Any]] = []
            total_count = None

            for page in range(1, self.max_pages + 1):
                self.logger.info(f"  Page {page} for '{keyword}'")
                try:
                    params = {
                        'app_id':           APP_ID,
                        'app_key':          APP_KEY,
                        'results_per_page': RESULTS_PER_PAGE,
                        'what':             keyword,
                        'sort_by':          'date',
                        'content-type':     'application/json',
                    }

                    url = API_URL.format(page=page)
                    response = self._make_request('GET', url, params=params)
                    data = response.json()

                    if total_count is None:
                        total_count = data.get('count', 0)
                        self.logger.info(f"  Total available: {total_count}")

                    results = data.get('results', [])
                    if not results:
                        self.logger.info(f"  No results on page {page}. Stopping.")
                        break

                    jobs = [self._normalize(j, category_label) for j in results]
                    jobs = [j for j in jobs if j]
                    all_jobs.extend(jobs)
                    self.logger.info(f"  Got {len(jobs)} jobs (total: {len(all_jobs)})")

                    if len(all_jobs) >= total_count:
                        break

                    time.sleep(PAGE_DELAY)

                except Exception as e:
                    self.logger.error(f"  Failed on page {page}: {e}", exc_info=True)
                    break

            if all_jobs:
                identifier = keyword.replace(' ', '_')
                self.save_raw_data({'category': category_label, 'data': all_jobs}, identifier)
                self.logger.info(f"Saved {len(all_jobs)} jobs for '{keyword}'.")

    def _normalize(self, job: Dict[str, Any], category_label: str) -> Optional[Dict[str, Any]]:
        title = (job.get('title') or '').strip()
        if not title:
            return None

        job_url = (job.get('redirect_url') or '').strip()
        if not job_url:
            return None

        company = job.get('company') or {}
        facility_name = (company.get('display_name') or 'Unknown Facility').strip()

        # location.area is a list: ['Australia', 'State', 'Region', 'City', 'Suburb']
        area = (job.get('location') or {}).get('area', [])
        state = 'Unknown'
        city = ''
        if len(area) >= 2:
            state = STATE_NAME_MAP.get(area[1].lower(), area[1])
        if len(area) >= 2:
            city = area[-1] if area[-1].lower() != 'australia' else ''

        # created: "2026-03-12T09:50:44Z" → "2026-03-12"
        date_posted = (job.get('created') or '')[:10]

        return {
            # Preserve ALL raw API fields so nothing is lost in raw dumps
            **job,
            # Override / add canonical fields
            'id':            str(job.get('id', '')),
            'title':         title,
            'facility_name': facility_name,
            'category':      category_label,
            'state':         state,
            'city':          city,
            'date_posted':   date_posted,
            'url':           job_url,
        }


if __name__ == "__main__":
    scraper = AdzunaScraper(base_dir=".")
    scraper.run(['nurse', 'aged care', 'disability support', 'allied health', 'support worker'])
