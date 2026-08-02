import json
from typing import List
from src.base_scraper import JobScraper

class SeekScraper(JobScraper):
    def __init__(self, base_dir: str = "."):
        super().__init__("seek", base_dir)
        self.base_url = "https://www.seek.com.au/api/jobsearch/v5/search"
        self.jd_url = "https://www.seek.com.au/job/"
        
        # We will mimic a browser request 
        self.session.headers.update({
             'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15'
        })
        
        self.max_pages = 5 # Limit to 5 pages per keyword for POC to avoid overwhelming API

    def run(self, search_terms: List[str]) -> None:
        """
        Executes the scraping process for SEEK.
        """
        for term in search_terms:
            self.logger.info(f"Starting scrape for keyword: {term}")
            
            page = 1
            has_more = True
            
            while has_more and page <= self.max_pages:
                self.logger.info(f"Fetching page {page} for keyword: '{term}'")
                
                params = {
                    'siteKey': 'AU-Main',
                    'sourcesystem': 'houston',
                    'where': 'All Australia', # Using All Australia for broadest reach
                    'page': page,
                    'seekSelectAllPages': 'true',
                    'keywords': term,
                    'include': 'seodata',
                    'locale': 'en-AU'
                }
                
                try:
                    response = self._make_request('GET', self.base_url, params=params)
                    data = response.json()
                    
                    jobs = data.get('data', [])
                    total_count = data.get('totalCount', 0)
                    
                    if not jobs:
                        self.logger.info(f"No more jobs found for {term} on page {page}.")
                        has_more = False
                        break
                        
                    self.logger.info(f"Found {len(jobs)} jobs on page {page} (Total: {total_count})")
                    
                    # Save the raw JSON data immediately
                    # Prefix with term and page for easy identification
                    safe_term = term.lower().replace(" ", "_").replace("&", "and")
                    identifier = f"{safe_term}_p{page}"
                    self.save_raw_data(data, identifier)
                    
                    # Check pagination
                    items_per_page = data.get('solMetadata', {}).get('pageSize', 20) # Seek default is often 22
                    if not items_per_page:
                        items_per_page = 22 # Fallback
                        
                    total_pages = (total_count + items_per_page - 1) // items_per_page
                    
                    if page >= total_pages:
                        has_more = False
                    else:
                        page += 1
                        
                except Exception as e:
                    self.logger.error(f"Failed to scrape {term} page {page}: {str(e)}", exc_info=True)
                    has_more = False


if __name__ == "__main__":
    # Quick test for POC
    scraper = SeekScraper(base_dir=".")
    # Test with just a couple of keywords for POC
    scraper.run(["nurse", "support worker"])
