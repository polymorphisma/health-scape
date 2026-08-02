"""
Indeed AU scraper using the internal GraphQL API (sourced from JobSpy open-source project).
API key: hardcoded mobile app key (public, widely known in the scraping community).
"""
import time
import warnings
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.base_scraper import JobScraper

warnings.filterwarnings('ignore')  # suppress SSL verify=False warning

# Keyword → canonical client category label
KEYWORD_CATEGORY_MAP = {
    'nurse':              'Nursing',
    'aged care':          'Aged Care',
    'disability support': 'Disability Support',
    'allied health':      'Allied Health',
    'support worker':     'Disability Support',
}

RESULTS_PER_PAGE = 100   # Indeed GraphQL max
PAGE_DELAY       = 1.5   # seconds between pages

GRAPHQL_URL = "https://apis.indeed.com/graphql"

# Public API key extracted from the Indeed iOS app (well-known in open-source scrapers)
INDEED_API_KEY = "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8"

JOB_SEARCH_QUERY = """
query {{
    jobSearch(
        what: "{keyword}"
        location: {{where: "Australia", radius: 100, radiusUnit: MILES}}
        limit: {limit}
        sort: DATE
        {cursor_clause}
    ) {{
        pageInfo {{ nextCursor }}
        results {{
            job {{
                key
                title
                datePublished
                location {{ admin1Code city countryCode }}
                employer {{ name }}
            }}
        }}
    }}
}}
"""


class IndeedScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("indeed", base_dir)
        self.max_pages = 5

        self.session.headers.update({
            'content-type':    'application/json',
            'indeed-api-key':  INDEED_API_KEY,
            'indeed-co':       'AU',
            'indeed-locale':   'en-AU',
            'accept':          'application/json',
            'user-agent':      (
                'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) '
                'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
                'Indeed App 193.1'
            ),
            'indeed-app-info': (
                'appv=193.1; appid=com.indeed.jobsearch; '
                'osv=16.6.1; os=ios; dtype=phone'
            ),
        })

    def run(self, search_terms: Optional[List[str]] = None) -> None:
        if search_terms is None:
            search_terms = list(KEYWORD_CATEGORY_MAP.keys())

        for keyword in search_terms:
            category_label = KEYWORD_CATEGORY_MAP.get(keyword, 'Healthcare')
            self.logger.info(f"Starting Indeed AU scrape: '{keyword}' → {category_label}")

            all_jobs: List[Dict[str, Any]] = []
            cursor: Optional[str] = None
            page = 1

            while page <= self.max_pages:
                self.logger.info(f"  Fetching page {page} for '{keyword}'")
                try:
                    jobs, cursor = self._fetch_page(keyword, cursor)
                    if not jobs:
                        self.logger.info(f"  No jobs on page {page}. Stopping.")
                        break

                    all_jobs.extend(jobs)
                    self.logger.info(f"  Got {len(jobs)} jobs (total: {len(all_jobs)})")

                    if not cursor:
                        self.logger.info("  No next cursor. Stopping.")
                        break

                    page += 1
                    time.sleep(PAGE_DELAY)

                except Exception as e:
                    self.logger.error(f"  Failed on page {page}: {e}", exc_info=True)
                    break

            if all_jobs:
                identifier = keyword.replace(' ', '_')
                self.save_raw_data({'category': category_label, 'data': all_jobs}, identifier)
                self.logger.info(f"Saved {len(all_jobs)} jobs for '{keyword}'.")

    def _fetch_page(
        self, keyword: str, cursor: Optional[str]
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        cursor_clause = f'cursor: "{cursor}"' if cursor else ''
        query = JOB_SEARCH_QUERY.format(
            keyword=keyword.replace('"', '\\"'),
            limit=RESULTS_PER_PAGE,
            cursor_clause=cursor_clause,
        )

        response = self._make_request(
            'POST', GRAPHQL_URL,
            json={'query': query},
            verify=False,
        )
        data = response.json()

        if 'errors' in data:
            raise RuntimeError(f"GraphQL error: {data['errors'][0]['message']}")

        job_search = data['data']['jobSearch']
        raw_results = job_search.get('results', [])
        next_cursor = job_search.get('pageInfo', {}).get('nextCursor')

        jobs = [self._normalize(r['job'], keyword) for r in raw_results]
        jobs = [j for j in jobs if j]
        return jobs, next_cursor

    def _normalize(self, job: Dict[str, Any], keyword: str) -> Optional[Dict[str, Any]]:
        key = job.get('key')
        if not key:
            return None

        title = (job.get('title') or '').strip()
        if not title:
            return None

        employer = job.get('employer') or {}
        facility_name = (employer.get('name') or 'Unknown Facility').strip()

        loc = job.get('location') or {}
        city = (loc.get('city') or '').strip()
        state = (loc.get('admin1Code') or 'Unknown').strip().upper()
        country = (loc.get('countryCode') or '').upper()

        # Filter to AU only (API may return non-AU results)
        if country and country not in ('AU', 'AUS', ''):
            return None

        ts = job.get('datePublished')
        date_posted = (
            datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d') if ts else ''
        )

        return {
            'key':           key,
            'title':         title,
            'facility_name': facility_name,
            'state':         state,
            'city':          city,
            'date_posted':   date_posted,
            'url':           f'https://au.indeed.com/viewjob?jk={key}',
        }


if __name__ == "__main__":
    scraper = IndeedScraper(base_dir=".")
    scraper.run(['nurse', 'aged care', 'disability support', 'allied health', 'support worker'])
