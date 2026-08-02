"""
Exploration script: parse Next.js RSC (__next_f) flight data from EthicalJobs
to see what structured job data is embedded in the search results page.
"""
import re
import json
import requests
from bs4 import BeautifulSoup

url = "https://www.ethicaljobs.com.au/jobs?keywords=healthcare"
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

soup = BeautifulSoup(response.text, 'html.parser')

# Collect all __next_f push payloads
all_chunks = []
for script in soup.find_all('script'):
    text = script.string or ''
    # Match __next_f.push([1, "..."]) — the RSC data chunks
    matches = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', text, re.DOTALL)
    for m in matches:
        # Unescape the JS string
        try:
            chunk = m.encode('utf-8').decode('unicode_escape')
        except Exception:
            chunk = m
        all_chunks.append(chunk)

print(f"\nTotal RSC chunks found: {len(all_chunks)}")

# Join all chunks and split by line — each line is one RSC record
full_payload = ''.join(all_chunks)
lines = full_payload.split('\n')
print(f"Total RSC lines: {len(lines)}")

# Look for lines that contain job-like data
print("\n--- Lines containing 'title' or 'jobTitle' or 'advertiser' ---")
for i, line in enumerate(lines):
    if any(kw in line for kw in ['"title"', '"jobTitle"', '"advertiser"', '"location"', '"closingDate"', '"category"', '"sector"']):
        preview = line[:300]
        print(f"[Line {i}] {preview}")
        print()

# Also try to find any JSON-looking chunks that have job arrays
print("\n--- Attempting to find JSON arrays that look like job listings ---")
for i, line in enumerate(lines):
    # RSC lines start with an ID like: 4a:, bf:, etc.
    # Strip the ID prefix and try to parse as JSON
    json_part = re.sub(r'^[0-9a-f]+:', '', line.strip())
    if not json_part or json_part[0] not in ('{', '['):
        continue
    try:
        parsed = json.loads(json_part)
        # Check if it looks like job data
        text_repr = json.dumps(parsed)
        if any(kw in text_repr for kw in ['title', 'location', 'advertiser', 'closingDate', 'category']):
            print(f"[Line {i}] Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else f'list[{len(parsed)}]'}")
            print(json.dumps(parsed, indent=2)[:800])
            print("---")
    except Exception:
        pass
