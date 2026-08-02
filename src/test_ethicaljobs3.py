import requests
from bs4 import BeautifulSoup

url = "https://www.ethicaljobs.com.au/jobs?keywords=healthcare"
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

print("ALL H2s:")
for i, h2 in enumerate(soup.find_all('h2')):
    print(f"[{i}] {h2.text}")
    
    # Let's inspect the 4th and 5th H2s specifically (usually where jobs start based on previous test)
    if i in [4, 5, 6]:
        company_div = h2.find_next_sibling('div')
        if company_div:
            print(f"    Company: {company_div.text}")
        
        # Check parents for A tag
        for p in h2.parents:
            if p.name == 'a':
                print(f"    URL: {p.get('href')}")
                break
        print("-" * 20)
