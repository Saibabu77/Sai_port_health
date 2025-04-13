import time
import re
import csv
import requests
import hashlib
import pickle
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ========== CONFIG ========== #
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1360983185231581204/nRSSOwRgRoCSK0K4o9_eu8vpeQsRswLNyjUAZb6pTtrVGksrEjVw9RteyUA04xP3aNIv"
CSV_FILENAME = "keyword_search_results.csv"
ERROR_CSV_FILENAME = "error_urls.csv"
EXCEL_FILENAME = "urllist_250.xlsx"
PICKLE_FILENAME = "previous_results.pkl"

keywords = [
    "Analyst", "business", "information", "technology", "supply", "chain",
    "Informatics", "data", "data science", "Analytics", "Research"
]

# ========== DISCORD ========== #
def send_discord_message(content, file_paths=None):
    data = {"content": content}
    files = []

    if file_paths:
        for path in file_paths:
            if os.path.exists(path):
                try:
                    files.append(("file", (os.path.basename(path), open(path, "rb"))))
                except Exception as e:
                    print(f"Error attaching file {path}: {e}")

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=data, files=files if files else None)
        if response.status_code not in [200, 204]:
            print(f"Failed to send Discord message: {response.text}")
    except Exception as e:
        print(f"Error sending to Discord: {e}")
    finally:
        for _, (_, f) in files:
            f.close()

# ========== DRIVER SETUP ========== #
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# ========== DATA LOAD/SAVE ========== #
def load_previous_results(filename=PICKLE_FILENAME):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}

def save_results(results, filename=PICKLE_FILENAME):
    with open(filename, 'wb') as f:
        pickle.dump(results, f)

# ========== SCRAPER ========== #
def find_keywords_in_website(driver, url):
    try:
        print(f"Checking {url}...")
        driver.get(url)

        # Wait until <body> is present
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Use full page HTML source
        page_text = driver.page_source.lower()

        if not page_text.strip():
            print(f"Empty page text for {url}")
            return None

        return [kw for kw in keywords if re.search(r'\b' + re.escape(kw.lower()) + r'\b', page_text)]

    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

# ========== MAIN ========== #
def main():
    df = pd.read_excel(EXCEL_FILENAME)
    urls = df["Orginal website"]

    driver = setup_driver()
    previous_results = load_previous_results()
    current_results = {}
    updated_results = []
    error_urls = []

    try:
        for url in urls:
            found_keywords = find_keywords_in_website(driver, url)

            if found_keywords is None:
                error_urls.append([url])
                continue

            keywords_str = ", ".join(sorted(found_keywords)) if found_keywords else ""
            content_hash = hashlib.md5(keywords_str.encode()).hexdigest()

            if url not in previous_results or previous_results[url] != content_hash:
                if found_keywords:
                    updated_results.append([url, keywords_str])
                    print(f"✅ {url} – {keywords_str}")
                else:
                    print(f"No keywords found in {url} (updated)")
                current_results[url] = content_hash
            else:
                print(f"No changes in {url}")

        file_paths_to_send = []

        # Save updated results
        if updated_results:
            with open(CSV_FILENAME, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Website", "Found Keywords"])
                writer.writerows(updated_results)
            print(f"\n✅ Saved to {CSV_FILENAME}")
            file_paths_to_send.append(CSV_FILENAME)

        # Always save error file (even if empty)
        with open(ERROR_CSV_FILENAME, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Website with Error"])
            if error_urls:
                writer.writerows(error_urls)
                print(f"⚠️ Errors saved to {ERROR_CSV_FILENAME}")
            else:
                writer.writerow(["No errors encountered."])
                print("✅ No scraping errors.")
        file_paths_to_send.append(ERROR_CSV_FILENAME)

        # Short message to stay under 2000 character Discord limit
        message = ""

        if updated_results:
            message += f"🔍 **Keyword Updates Found!**\nTotal: {len(updated_results)}\n📎 See attached CSV.\n"
        else:
            message += "✅ No keyword updates found.\n"

        if error_urls:
            message += f"⚠️ {len(error_urls)} URLs failed during scraping."
        else:
            message += "✅ No failed URLs."

        send_discord_message(message.strip(), file_paths_to_send)

        previous_results.update(current_results)
        save_results(previous_results)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
