import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

def fetch_listings():
    url = "https://boosty.to/historipi"
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(url, headers=headers, timeout=10).text
    soup = BeautifulSoup(html, "lxml")

    listings = []

    for item in soup.select('article div[data-post-id] a[data-test-id="COMMON_CREATEDAT:ROOT"]'):
        title = item.get_text(strip=True)
        listings.append({
            "title": title
        })

    return listings

def main():
    listings = fetch_listings()

    print("Найдено объявлений:", len(listings))

    for item in listings:
        print("\n--- Объявление ---")
        print(item)
        print("\n--- Анализ ---")

if __name__ == "__main__":
    main()
