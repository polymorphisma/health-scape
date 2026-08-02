import cloudscraper
import json
import re

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
response = scraper.get('https://www.seek.com.au/healthcare-&-medical-jobs')

if response.status_code == 200:
    print("Success! Searching for SEEK_REDUX_DATA...")
    match = re.search(r'window\.SEEK_REDUX_DATA\s*=\s*(\{.*?\})\s*;?\s*(\n|$)', response.text, re.DOTALL)
    if match:
        data = json.loads(match.group(1))
        # Print the structure of the most important part
        jobs = data.get('results', {}).get('results', {}).get('jobs', [])
        print(f"Found {len(jobs)} jobs in Redux data snippet.")
        if jobs:
            job = jobs[0]
            print("\nFirst job keys:")
            print("\n".join(f"  - {k}: {type(job[k]).__name__}" for k in job.keys()))
    else:
        print("Could not find SEEK_REDUX_DATA match.")
else:
    print(f"Failed with status code: {response.status_code}")
