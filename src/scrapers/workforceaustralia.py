import time
from typing import List, Dict, Any, Optional
from src.base_scraper import JobScraper


# Keyword → canonical client category label
KEYWORD_CATEGORY_MAP = {
    'nurse':              'Nursing',
    'aged care':          'Aged Care',
    'disability support': 'Disability Support',
    'allied health':      'Allied Health',
    'support worker':     'Disability Support',
}

RESULTS_PER_PAGE = 20
PAGE_DELAY       = 1.0   # seconds between requests

API_URL     = "https://www.workforceaustralia.gov.au/api/v1/global/vacancies/"
JOB_URL_TPL = "https://www.workforceaustralia.gov.au/individuals/jobs/{vacancy_id}"


class WorkforceAustraliaScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("workforceaustralia", base_dir)
        self.max_pages = 5  # POC cap

        self.session.headers.update({
            'Accept':           'application/json, text/plain, */*',
            'Accept-Language':  'en-AU,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'cache-control':    'no-cache',
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
        })

    def run(self, search_terms: Optional[List[str]] = None) -> None:
        """Fetches jobs from the Workforce Australia JSON API by keyword."""
        if search_terms is None:
            search_terms = list(KEYWORD_CATEGORY_MAP.keys())

        for keyword in search_terms:
            category_label = KEYWORD_CATEGORY_MAP.get(keyword, 'Healthcare')
            self.logger.info(f"Starting WorkforceAustralia scrape: '{keyword}' → {category_label}")

            all_jobs: List[Dict[str, Any]] = []
            page = 0

            while page < self.max_pages:
                skip = page * RESULTS_PER_PAGE
                self.logger.info(f"  Fetching page {page + 1} (skip={skip}) for '{keyword}'")

                try:
                    response = self._make_request(
                        'GET', API_URL,
                        params={'searchText': keyword, 'skip': skip},
                    )
                    data = response.json()

                    results = data.get('results', [])
                    if not results:
                        self.logger.info(f"  No results on page {page + 1}. Stopping.")
                        break

                    jobs = [self._normalize(r['result'], category_label) for r in results]
                    jobs = [j for j in jobs if j]  # filter None
                    all_jobs.extend(jobs)

                    self.logger.info(f"  Got {len(jobs)} jobs (total so far: {len(all_jobs)})")

                    total_count = data.get('totalCount', 0)
                    if skip + RESULTS_PER_PAGE >= total_count:
                        self.logger.info(f"  Reached end of results ({total_count} total).")
                        break

                    page += 1
                    time.sleep(PAGE_DELAY)

                except Exception as e:
                    self.logger.error(f"  Failed on page {page + 1}: {e}", exc_info=True)
                    break

            if all_jobs:
                identifier = keyword.replace(' ', '_')
                self.save_raw_data({'category': category_label, 'data': all_jobs}, identifier)
                self.logger.info(f"Saved {len(all_jobs)} jobs for '{keyword}'.")

    def _normalize(self, job: Dict[str, Any], category_label: str) -> Optional[Dict[str, Any]]:
        """Normalizes a single API result into our standard schema."""
        vacancy_id = job.get('vacancyId')
        if not vacancy_id:
            return None

        title = (job.get('title') or '').strip()
        if not title:
            return None

        employer = (job.get('employerName') or 'Unknown Facility').strip()

        # suburb comes in ALL CAPS (e.g. "GERALDTON") — convert to title case
        suburb = (job.get('suburb') or '').strip().title()

        raw_state = (job.get('state') or '').strip().upper()
        state = raw_state if raw_state else 'Unknown'

        # creationDate: "2026-02-27T17:44:16.42" → "2026-02-27"
        creation_date = job.get('creationDate') or ''
        date_posted = creation_date[:10] if creation_date else ''

        return {
            # Preserve ALL raw API fields so nothing is lost in raw dumps
            **job,
            # Override / add canonical fields
            'vacancyId':     vacancy_id,
            'title':         title,
            'facility_name': employer,
            'category':      category_label,
            'state':         state,
            'city':          suburb,
            'date_posted':   date_posted,
            'url':           JOB_URL_TPL.format(vacancy_id=vacancy_id),
            'occupation':    (job.get('occupation') or {}).get('label', ''),
        }


if __name__ == "__main__":
    scraper = WorkforceAustraliaScraper(base_dir=".")
    scraper.run(['nurse', 'aged care', 'disability support', 'allied health', 'support worker'])
