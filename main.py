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
from datetime import datetime
from zoneinfo import ZoneInfo
# ========== CONFIG ========== #
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1360983185231581204/nRSSOwRgRoCSK0K4o9_eu8vpeQsRswLNyjUAZb6pTtrVGksrEjVw9RteyUA04xP3aNIv"
COMBINED_CSV_FILENAME = "combined_output.csv"
EXCEL_FILENAME = "urllist_250.xlsx"
PICKLE_FILENAME = "previous_results.pkl"

keywords = [
    "Analyst", "business", "information", "technology", "supply", "chain",
    "Informatics", "data", "data science", "Analytics", "Research"
]

# ========== DISCORD ========== #
def send_discord_message(content, file_path=None):
    data = {"content": content}
    files = []

    if file_path and os.path.exists(file_path):
        try:
            files.append(("file", (os.path.basename(file_path), open(file_path, "rb"))))
        except Exception as e:
            print(f"Error attaching file {file_path}: {e}")

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

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

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
    combined_rows = []
    updated_count = 0
    error_count = 0

    try:
        for url in urls:
            found_keywords = find_keywords_in_website(driver, url)

            timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")

            if found_keywords is None:
                combined_rows.append([url, "", "Error", timestamp])
                error_count += 1
                continue

            keywords_str = ", ".join(sorted(found_keywords)) if found_keywords else ""
            content_hash = hashlib.md5(keywords_str.encode()).hexdigest()

            if url not in previous_results or previous_results[url] != content_hash:
                if found_keywords:
                    updated_count += 1
                    print(f"✅ {url} – {keywords_str}")
                else:
                    print(f"No keywords found in {url} (updated)")
                current_results[url] = content_hash
                combined_rows.append([url, keywords_str, "Updated", timestamp])

        # Save only updated rows
        if combined_rows:
            with open(COMBINED_CSV_FILENAME, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Website", "Found Keywords", "Status", "Timestamp"])
                writer.writerows(combined_rows)
            print(f"✅ Updated results saved to {COMBINED_CSV_FILENAME}")

            # Send Discord message with CSV
            message = ""
            message += f"🔍 **Keyword Updates Found!**\nTotal updated: {updated_count}\n"
            message += f"⚠️ Total errors: {error_count}\n"
            message += f"📎 See attached CSV for details."
            send_discord_message(message.strip(), COMBINED_CSV_FILENAME)
        else:
            print("No new updates detected. CSV not created.")
            send_discord_message("✅ No updates detected in the latest run.")

        previous_results.update(current_results)
        save_results(previous_results)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
