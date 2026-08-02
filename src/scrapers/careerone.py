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

# CareerOne search URL slugs per keyword
KEYWORD_URL_MAP = {
    'nurse':              '/nurse-jobs/in-australia',
    'aged care':          '/aged-care-jobs/in-australia',
    'disability support': '/disability-support-worker-jobs/in-australia',
    'allied health':      '/allied-health-jobs/in-australia',
    'support worker':     '/support-worker-jobs/in-australia',
}

BASE_URL    = "https://www.careerone.com.au"
SEARCH_API  = f"{BASE_URL}/api/v1/search-job"
CSRF_URL    = f"{BASE_URL}/csrf-cookie"
PAGE_DELAY  = 1.5
RESULTS_PER_PAGE = 20


class CareerOneScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("careerone", base_dir)
        self.max_pages = 5

        self.session.headers.update({
            'accept':          'application/json',
            'accept-language': 'en-AU,en;q=0.9',
            'platform-code':   'careerone',
            'site-code':       'careerone',
            'user-agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
        })

    def _establish_session(self) -> None:
        """
        Hits /csrf-cookie to get a fresh seekerapi_session.
        No credentials needed — the endpoint sets cookies automatically.
        """
        self.session.get(CSRF_URL, timeout=15)
        xsrf = self.session.cookies.get('XSRF-TOKEN', '')
        if xsrf:
            self.session.headers['x-xsrf-token'] = xsrf
        self.logger.info("CareerOne session established.")

    def run(self, search_terms: Optional[List[str]] = None) -> None:
        if search_terms is None:
            search_terms = list(KEYWORD_CATEGORY_MAP.keys())

        self._establish_session()

        for keyword in search_terms:
            category_label = KEYWORD_CATEGORY_MAP.get(keyword, 'Healthcare')
            search_url_slug = KEYWORD_URL_MAP.get(keyword, f'/{keyword.replace(" ", "-")}-jobs/in-australia')
            self.logger.info(f"Starting CareerOne scrape: '{keyword}' → {category_label}")

            all_jobs: List[Dict[str, Any]] = []
            total_count = None

            for page in range(1, self.max_pages + 1):
                self.logger.info(f"  Page {page} for '{keyword}'")
                try:
                    params = {
                        'url':           search_url_slug,
                        'locale':        'AU',
                        'allow_backfill': 'true',
                    }
                    if page > 1:
                        params['page'] = page

                    response = self._make_request('GET', SEARCH_API, params=params)
                    data = response.json()

                    search_results = data.get('search_results', {})
                    jobs_raw = search_results.get('jobs', [])

                    if total_count is None:
                        total_count = search_results.get('job_count', 0)
                        self.logger.info(f"  Total available: {total_count}")

                    if not jobs_raw:
                        self.logger.info(f"  No jobs on page {page}. Stopping.")
                        break

                    jobs = [self._normalize(j, category_label) for j in jobs_raw]
                    jobs = [j for j in jobs if j]
                    all_jobs.extend(jobs)
                    self.logger.info(f"  Got {len(jobs)} jobs (total: {len(all_jobs)})")

                    # Stop if we've fetched all available jobs
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
        title = (job.get('job_title') or '').strip()
        if not title:
            return None

        # company_name is the direct employer; account_name is sometimes the recruiter
        facility = (job.get('company_name') or job.get('account_name') or 'Unknown Facility').strip()

        state = (job.get('location_state_code') or 'Unknown').strip().upper()
        # location_level_1_label is the suburb/city; location_label has "Suburb STATE POSTCODE"
        city = (job.get('location_level_1_label') or '').strip()

        # activates_at = "2026-03-04 03:23:44" → "2026-03-04"
        raw_date = job.get('activates_at') or job.get('refreshed_at') or ''
        date_posted = raw_date[:10] if raw_date else ''

        # URL field is a relative slug like "job-title-slug/uuid"
        url_slug = (job.get('URL') or '').strip()
        job_url = f"{BASE_URL}/{url_slug}" if url_slug else ''
        if not job_url:
            return None

        return {
            # Preserve ALL raw API fields so nothing is lost in raw dumps
            **job,
            # Override / add canonical fields
            'id':            job.get('uuid') or job.get('id', ''),
            'title':         title,
            'facility_name': facility,
            'category':      category_label,
            'state':         state,
            'city':          city,
            'date_posted':   date_posted,
            'url':           job_url,
            'occupation':    (job.get('occupation_label') or '').strip(),
        }


if __name__ == "__main__":
    scraper = CareerOneScraper(base_dir=".")
    scraper.run(['nurse', 'aged care', 'disability support', 'allied health', 'support worker'])
