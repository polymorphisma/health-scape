import requests
from bs4 import BeautifulSoup

url = "https://www.ethicaljobs.com.au/members/cawls/domestic-family-and-sexual-violence-education-officer-alice-springs"
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

print("H1 (Title):")
h1 = soup.find('h1')
if h1:
    print(h1.text)

print("\nH2s:")
for h2 in soup.find_all('h2')[:10]:
    print(f"- {h2.text}")
    
print("\nLooking for specific job details (Location, Date, Category)...")
# Job details usually live in strong/span tag pairs or definition lists
for dl in soup.find_all('dl')[:3]:
    for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
        print(f"{dt.text}: {dd.text}")
        
# Often labels like "Location", "Category", "Closing Date" are strong tags
for strong in soup.find_all('strong')[:10]:
    parent = strong.parent
    if parent:
        text = parent.text.strip().replace('\n', ' ')
        if "location" in text.lower() or "categor" in text.lower() or "date" in text.lower():
            print(f"Detail Text: {text}")
