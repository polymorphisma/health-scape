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

print("Looking for all text blocks containing 'Location', 'Sector', 'Categor', or Date formats:")
for element in soup.find_all(['div', 'span', 'p', 'li']):
    text = element.get_text(strip=True)
    if not text or len(text) > 100: continue
    
    if any(keyword in text.lower() for keyword in ['location', 'sector', 'categor', 'closes', 'closing']):
        print(f"[{element.name}] {text}")
