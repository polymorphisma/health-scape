import requests
from bs4 import BeautifulSoup
import json

url = "https://www.ethicaljobs.com.au/jobs?keywords=healthcare"
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# Let's see what a job listing looks like
# The user's snippet showed:
# <div class="sc-b49ecd0e-3 ddmNFP">
#   <div class="sc-b49ecd0e-6 jSyPHC">
#     <h2 class="sc-b49ecd0e-7 jHYTWx">Domestic, Family and Sexual Violence Education Officer - Alice Springs</h2>
#     <div class="sc-b49ecd0e-8 amqkD">Central Australian Women 's Legal Service</div>
#   </div>

# Let's find all h2s and check their parents and siblings
for h2 in soup.find_all('h2')[4:6]: # skip navigation headers
    print(f"Job Title: {h2.text}")
    print(f"  Parent tag: {h2.parent.name}")
    
    # Try to find the company which seems to be the next div
    company_div = h2.find_next_sibling('div')
    if company_div:
        print(f"  Company: {company_div.text}")
        
    # See if there's an 'a' tag wrapping this to get the URL
    a_tag = h2.find_parent('a')
    if a_tag:
        print(f"  URL: {a_tag.get('href')}")
    else:
        # Search upwards for an 'a' tag
        for parent in h2.parents:
            if parent.name == 'a':
                print(f"  URL (up tree): {parent.get('href')}")
                break
    print("---")
    
