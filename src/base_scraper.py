import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

class JobScraper:
    def __init__(self, platform_name: str, base_dir: str = "."):
        self.platform_name = platform_name.lower().strip()
        self.base_dir = base_dir
        self.session = requests.Session()
        
        # Setup paths
        self.raw_dumps_dir = os.path.join(self.base_dir, "raw_dumps")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.raw_dumps_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        log_file = os.path.join(self.logs_dir, f"{self.platform_name}_{datetime.now().strftime('%Y%m%d')}.log")
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        self.logger = logging.getLogger(self.platform_name)
        self.logger.setLevel(logging.INFO)
        # Avoid duplicate handlers if instantiated multiple times
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def save_raw_data(self, data: Any, identifier: str) -> str:
        """Saves raw JSON/HTML data to the raw_dumps directory with a timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.platform_name}_raw_{identifier}_{timestamp}.json"
        filepath = os.path.join(self.raw_dumps_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            if isinstance(data, (dict, list)):
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                f.write(str(data))
                
        self.logger.info(f"Saved raw data to {filepath}")
        return filepath

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Wrapper around requests to provide retry logic."""
        self.logger.debug(f"Making {method} request to {url}")
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def run(self, search_terms: List[str]) -> None:
        """
        Main entry point for the scraper. Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the run() method.")
