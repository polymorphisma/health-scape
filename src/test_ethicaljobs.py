import requests
from bs4 import BeautifulSoup
import json

url = "https://www.ethicaljobs.com.au/jobs?keywords=healthcare"
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}

print(f"Fetching {url}")
response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Modern Next.js apps often embed the initial state in a JSON script tag
    script_tag = soup.find('script', id='__NEXT_DATA__')
    if script_tag:
        print("Found __NEXT_DATA__ script tag! Extracting JSON...")
        try:
            data = json.loads(script_tag.string)
            # Just print the top-level keys to inspect
            print("Top level keys:", data.keys())
            if 'props' in data:
                print("Props keys:", data['props'].keys())
                if 'pageProps' in data['props']:
                    print("PageProps keys:", data['props']['pageProps'].keys())
        except Exception as e:
            print("Error parsing JSON:", e)
    else:
        print("Could not find __NEXT_DATA__")
        
    # Let's also look for job titles in the HTML just in case
    print("\nLooking for job titles in HTML...")
    h2_tags = soup.find_all('h2')
    for h2 in h2_tags[:5]:
        print(f"Found H2: {h2.text}")
        
    # See if there's any other large JSON blobs
    for script in soup.find_all('script'):
        if script.string and ('window.__' in script.string or 'INITIAL_STATE' in script.string or 'window.App' in script.string):
            print("Found potential alternate state blob:", script.string[:200])
