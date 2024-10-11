import asyncio
import time
from requests import Session
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import pandas as pd
import httpx
from httpx import ConnectTimeout
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import threading


# Accept GDPR banner to access page
def accept_gdpr_banner(driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "usercentrics-root")))
        time.sleep(0.5)
        shadow_host = driver.find_element(By.ID, "usercentrics-root")
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
        button = shadow_root.find_element(By.CSS_SELECTOR, '[data-testid=uc-accept-all-button]')
        button.click()
        print("GDPR banner accepted.")
    except Exception as e:
        print(f"An error occurred while accepting GDPR banner: {e}")


def get_property_info(property_type, cookies, page_number):
    '''
    Scrapes property listing information from Immoweb for specific property type.
    Args:
        property_type which is a string and the type of property to search for e.g. 'house' or 'apartment'.
        cookies (list) from Selenium for authenticated requests.
        page_number (int) current page number.
    Returns:
        Dictionary of property information
    '''
    params = {
        "countries": "BE",
        "page": page_number,
        "orderBy": "relevance"
    }
    root_url_bs = f"https://www.immoweb.be/en/search/{property_type}/for-sale"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    page_listings_list = []

    # Prepare cookies for httpx client
    cookie_jar = {cookie['name']: cookie['value'] for cookie in cookies}

    retries = 3
    with httpx.Client() as client:
        for attempt in range(retries):
            try:
                response = client.get(root_url_bs, headers=headers, params=params, cookies=cookie_jar, timeout=10.0)
                if response.status_code == 200:
                    # Parse the content with BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find all property listings (use the appropriate HTML class or ID)
                    listings = soup.find_all('article', class_='card--result')

                    apartment_types = ['ground-floor', 'triplex', 'duplex', 'studio', 'penthouse', 'loft', 'kot',
                                       'service-flat']
                    house_types = ['bungalow', 'chalet', 'castle', 'farmhouse', 'country-house', 'exceptional-property',
                                   'apartment-block', 'mixed-use-building', 'town-house', 'mansion', 'villa',
                                   'other-properties', 'manor-house', 'pavilion']

                    for idx, listing in enumerate(listings):
                        listing_url = listing.find('a', class_='card__title-link')['href']
                        if "new-real-estate-project" in listing_url or "mixed-use-building" in listing_url or "exceptional-property" in listing_url:
                            continue

                        for attempt_listing in range(retries):
                            try:
                                listing_response = client.get(listing_url, headers=headers, cookies=cookie_jar,
                                                              timeout=10.0)
                                if listing_response.status_code != 200:
                                    print(
                                        f"Failed to retrieve listing at {listing_url}, Status code: {listing_response.status_code}")
                                    continue

                                listing_soup = BeautifulSoup(listing_response.text, 'html.parser')
                                listings_dict = {}

                                property_id = listing_soup.find('div', class_="classified__header--immoweb-code")
                                if property_id:
                                    listings_dict['Property ID'] = property_id.contents[0].strip().split(':')[1]

                                listings_dict["Locality data"] = listing_url.split("/")[7]
                                listings_dict["Locality data"] = listing_url.split("/")[8]

                                price = listing_soup.find('span', class_='sr-only').text
                                only_digits = re.sub(r'\D+', '', price)
                                listings_dict["Price"] = only_digits

                                property_type = listing_url.split("/")[5]
                                listings_dict["Property type"] = property_type

                                subtype = listing_url.split("/")[5]
                                subtype_cleaned = subtype.lower().strip()
                                if subtype_cleaned in apartment_types:
                                    listings_dict['Sub type'] = subtype_cleaned
                                elif subtype in house_types:
                                    listings_dict['Sub type'] = subtype_cleaned
                                else:
                                    listings_dict['Sub type'] = None

                                listings_dict["Type of sale"] = get_page_table_info("Monthly annuity", listing_soup)
                                listings_dict["Number of bedrooms"] = get_page_table_info("Bedrooms", listing_soup)
                                listings_dict["Living area m²"] = get_page_table_info("Living area", listing_soup)
                                listings_dict['Equipped kitchen'] = 1 if get_page_table_info("Kitchen type",
                                                                                             listing_soup) == "Installed" else 0
                                listings_dict['Furnished'] = 1 if get_page_table_info("Furnished",
                                                                                      listing_soup) == "Yes" else 0
                                listings_dict['Open fire'] = 1 if get_page_table_info("How many fireplaces?",
                                                                                      listing_soup) else 0
                                listings_dict['Terrace surface m²'] = get_page_table_info("Terrace surface",
                                                                                          listing_soup)
                                listings_dict['Garden area m²'] = get_page_table_info("Garden surface", listing_soup)
                                listings_dict['Number of facades'] = get_page_table_info("Number of frontages",
                                                                                         listing_soup)
                                listings_dict['Swimming pool'] = 1 if get_page_table_info("Swimming pool",
                                                                                          listing_soup) == "Yes" else 0
                                listings_dict['Building condition'] = get_page_table_info('Building condition',
                                                                                          listing_soup)

                                page_listings_list.append(listings_dict)
                                break  # Exit retry loop if successful
                            except (ConnectTimeout, httpx.RequestError) as e:
                                print(f"Retry {attempt_listing + 1} failed for listing URL {listing_url}: {e}")
                                time.sleep(2)  # Delay before retrying
                    break  # Exit retry loop if successful
                else:
                    print(f"Failed to retrieve the page. Status code: {response.status_code}")
                    return []
            except (ConnectTimeout, httpx.RequestError) as e:
                print(f"Retry {attempt + 1} failed for page {page_number}: {e}")
                time.sleep(2)  # Delay before retrying

    return page_listings_list


def fetch_all_pages(property_type, cookies, max_pages=10, batch_size=50):
    all_pages = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        lock = threading.Lock()
        futures = []
        for batch_start in range(1, max_pages + 1, batch_size):
            batch_end = min(batch_start + batch_size, max_pages + 1)
            for page_number in range(batch_start, batch_end):
                futures.append(executor.submit(get_property_info, property_type, cookies, page_number))

        for future in tqdm(futures, desc="Fetching pages", total=len(futures)):
            result = future.result()
            if result:
                with lock:
                    all_pages.extend(result)
    return all_pages


def get_page_table_info(header, soup):
    header_tag = soup.find('th', class_='classified-table__header',
                           string=lambda x: x and header.lower() in x.strip().lower())
    if header_tag:
        table_data = header_tag.find_next('td', class_='classified-table__data')
        if table_data:
            text_content = table_data.get_text(separator=" ", strip=True)
            match = re.search(r'\d+', text_content)
            if match:
                return match.group()
            for content in table_data.contents:
                if isinstance(content, str) or content.strip().isdigit():
                    return content.strip()
    return "None"


# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-infobars")

# Uncomment this if you want it to be headless
# chrome_options.add_argument("--headless")

# Create a driver instance with the options
driver = webdriver.Chrome(options=chrome_options)

# Open the website
root_url = "https://www.immoweb.be/en/search/house/for-sale?countries=BE&page=1&orderBy=relevance"
driver.get(root_url)

accept_gdpr_banner(driver)
cookies = driver.get_cookies()
driver.quit()

# Fetch all pages using multithreading
all_pages = fetch_all_pages("house", cookies, max_pages=300)

# Save results to CSV
df = pd.DataFrame([item for sublist in all_pages for item in sublist])
df.to_csv("property_information.csv")