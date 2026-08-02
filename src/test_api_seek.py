import requests

url = "https://www.seek.com.au/api/jobsearch/v5/search"
params = {
    'siteKey': 'AU-Main',
    'sourcesystem': 'houston',
    'where': 'All Australia',
    'page': 1,
    'seekSelectAllPages': 'true',
    'keywords': 'healthcare',
    'include': 'seodata',
    'locale': 'en-AU'
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15'
}

response = requests.get(url, params=params, headers=headers)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Total jobs: {data.get('totalCount')}")
    jobs = data.get('data', [])
    if jobs:
        print(f"First job title: {jobs[0].get('title')}")
        print(f"First job advertiser: {jobs[0].get('advertiser', {}).get('description')}")
else:
    print(response.text[:500])
