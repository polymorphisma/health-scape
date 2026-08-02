import requests
from bs4 import BeautifulSoup
import re

url = "https://www.ethicaljobs.com.au/members/cawls/domestic-family-and-sexual-violence-education-officer-alice-springs"
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

print("Looking for dt/dd groups:")
for i, dt in enumerate(soup.find_all('dt')):
    dd = dt.find_next_sibling('dd')
    if dd:
        print(f"  {dt.text.strip()}: {dd.text.strip()}")
        
print("\nChecking any div with specific class patterns commonly used for metadata:")
metadata_divs = soup.find_all('div', string=re.compile(r'Location|Categor|Close', re.IGNORECASE))
for div in metadata_divs:
    print(f"Found keyword div: {div.text}")
    sibling = div.find_next_sibling('div')
    if sibling:
        print(f"  Sibling value: {sibling.text}")
