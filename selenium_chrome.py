import asyncio
import time
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


# Accept GDPR banner to access page
def accept_gdpr_banner(driver):
    """
    Accept the GDPR banner that appears on the website.
    Args:
        driver (WebDriver): The Selenium WebDriver instance.
    Returns:
        None
    """
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "usercentrics-root"))
        )
        time.sleep(0.5)
        shadow_host = driver.find_element(By.ID, "usercentrics-root")
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
        button = shadow_root.find_element(By.CSS_SELECTOR, "[data-testid=uc-accept-all-button]")
        button.click()
        print("GDPR banner accepted.")
    except Exception as e:
        print(f"An error occurred while accepting GDPR banner: {e}")


async def get_property_info(property_type, cookies, page_number, client):
    """
    Scrape property listing information from Immoweb for a specific property type.
    Args:
        property_type (str): The type of property to search for (e.g., 'house' or 'apartment').
        cookies (list): Cookies from Selenium for authenticated requests.
        page_number (int): Current page number to scrape.
        client (AsyncClient): The httpx client for making HTTP requests.
    Returns:
        list: A list of dictionaries containing property information.
    """
    params = {"countries": "BE", "page": page_number, "orderBy": "relevance"}
    root_url_bs = f"https://www.immoweb.be/en/search/{property_type}/for-sale"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    page_listings_list = []

    # Prepare cookies for httpx client
    cookie_jar = {cookie["name"]: cookie["value"] for cookie in cookies}

    retries = 3
    for attempt in range(retries):
        try:
            response = await client.get(
                root_url_bs,
                headers=headers,
                params=params,
                cookies=cookie_jar,
                timeout=10.0,
            )
            if response.status_code == 200:
                # Parse the content with BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")

                # Find all property listings (use the appropriate HTML class or ID)
                listings = soup.find_all("article", class_="card--result")
                for idx, listing in enumerate(listings):
                    listing_url = listing.find("a", class_="card__title-link")["href"]
                    if (
                        "new-real-estate-project" in listing_url
                        or "mixed-use-building" in listing_url
                        or "exceptional-property" in listing_url
                    ):
                        continue

                    for attempt_listing in range(retries):
                        try:
                            listing_response = await client.get(
                                listing_url,
                                headers=headers,
                                cookies=cookie_jar,
                                timeout=10.0,
                            )
                            if listing_response.status_code != 200:
                                print(f"Failed to retrieve listing at {listing_url}, Status code: {listing_response.status_code}")
                                continue

                            listing_soup = BeautifulSoup(listing_response.text, "html.parser")
                            listings_dict = {}

                            # Extracting property ID from the listing page
                            property_id = listing_soup.find("div", class_="classified__header--immoweb-code")
                            if property_id:
                                listings_dict["Property ID"] = property_id.contents[0].strip().split(":")[1]

                            # Extract locality information from the listing URL
                            listings_dict["Locality data"] = listing_url.split("/")[7]
                            listings_dict["Locality data"] = listing_url.split("/")[8]

                            # Extract price information and keep only digits
                            price = listing_soup.find("span", class_="sr-only").text
                            only_digits = re.sub(r"\D+", "", price)
                            listings_dict["Price"] = only_digits

                            # Extract property type from input
                            listings_dict["Property type"] = property_type

                            subtype = listing_url.split("/")[5]
                            subtype_cleaned = subtype.lower().strip()
                            listings_dict["Property subtype"] = subtype_cleaned

                            # Extract different details from the page using helper function get_page_table_info
                            listings_dict["Type of sale"] = get_page_table_info("Monthly annuity", listing_soup)
                            listings_dict["Number of bedrooms"] = get_page_table_info("Bedrooms", listing_soup)
                            listings_dict["Living area m²"] = get_page_table_info("Living area", listing_soup)
                            listings_dict["Equipped kitchen"] = (
                                1 if get_page_table_info("Kitchen type", listing_soup) == "Installed" else 0
                            )
                            listings_dict["Furnished"] = (
                                1 if get_page_table_info("Furnished", listing_soup) == "Yes" else 0
                            )
                            listings_dict["Open fire"] = (
                                1 if get_page_table_info("How many fireplaces?", listing_soup) else 0
                            )
                            listings_dict["Terrace surface m²"] = get_page_table_info("Terrace surface", listing_soup)
                            listings_dict["Garden area m²"] = get_page_table_info("Garden surface", listing_soup)
                            listings_dict["Number of facades"] = get_page_table_info("Number of frontages", listing_soup)
                            listings_dict["Swimming pool"] = (
                                1 if get_page_table_info("Swimming pool", listing_soup) == "Yes" else 0
                            )
                            listings_dict["Building condition"] = get_page_table_info("Building condition", listing_soup)

                            page_listings_list.append(listings_dict)
                            break  # Exit retry loop if successful
                        except (ConnectTimeout, httpx.RequestError) as e:
                            print(f"Retry {attempt_listing + 1} failed for listing URL {listing_url}: {e}")
                            await asyncio.sleep(2)  # Delay before retrying
                break  # Exit retry loop if successful
            else:
                print(f"Failed to retrieve the page. Status code: {response.status_code}")
                return []
        except (ConnectTimeout, httpx.RequestError) as e:
            print(f"Retry {attempt + 1} failed for page {page_number}: {e}")
            await asyncio.sleep(2)  # Delay before retrying

    return page_listings_list


async def fetch_all_pages(property_type, cookies, max_pages=13, batch_size=2):
    """
    Fetch all property listings for a given property type asynchronous.
    Starts with an empty list to store all property listings collected from each batch of pages. The pages to fetch are
    looped over in batches, starting from page 1 to max_pages in defined batch_size. batch_end is calculated to not
    exceed max_pages. tasks creates a list of 'tasks' to be done, where each task calls get_property_info() for specific
    page in batch. This function scrapes data from a page. This list allows to scrape multiple pages asynchronous.
    An empty list results[] stores collected data from each task in concurrent batch. For loop to run tasks as they finish,
    no specific order. await task_result waits for each task to complete, then appends result to results list.
    result_pages is extended with non-empty results from 'results' list.
    Args:
        property_type (str): The type of property to search for (e.g., 'house' or 'apartment').
        cookies (list): Cookies from Selenium for authenticated requests.
        max_pages (int, optional): Maximum number of pages to fetch. Defaults to 10.
        batch_size (int, optional): Number of pages to fetch in each batch. Defaults to 50.
    Returns:
        list (result_pages): A list containing all fetched property listings.
    """
    result_pages = []
    async with httpx.AsyncClient() as client:
        for batch_start in range(1, max_pages + 1, batch_size):
            # Batch end determines if i can add the batch size w/out going over max amount of pages. If not, the uses
            # max amount of pages.
            batch_end = min(batch_start + batch_size, max_pages + 1)
            # Create a list of tasks for each page number in the current batch
            tasks = [
                get_property_info(property_type, cookies, page_number, client)
                for page_number in range(batch_start, batch_end)
            ]
            results = []
            # Using tqdm to show progress of fetching pages asynchronously
            for task_result in tqdm(
                asyncio.as_completed(tasks),
                desc=f"Fetching {property_type} pages {batch_start} to {batch_end - 1}",
                total=len(tasks),
            ):
                # Await the result of each task as it completes
                result = await task_result
                results.append(result)
            # Extend the result_pages list with non-empty results
            result_pages.extend([result for result in results if result])
    return result_pages


def get_page_table_info(header, soup):
    """
    Extract specific information from the property listing page table.
    Args:
        header (str): The header text to search for in the table.
        soup (BeautifulSoup): BeautifulSoup object containing the parsed HTML content.
    Returns:
        str: The text content of the corresponding table data cell, or 'None' if not found.
    """
    # Locate the header in the classified table by using its text content
    header_tag = soup.find(
        "th",
        class_="classified-table__header",
        string=lambda x: x and header.lower() in x.strip().lower(),
    )
    if header_tag:
        # Get the data associated with the found header tag
        table_data = header_tag.find_next("td", class_="classified-table__data")
        if table_data:
            text_content = table_data.get_text(separator=" ", strip=True)
            match = re.search(r"\d+", text_content)
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

# This loop is iterating over a list that contains two elements: "house" and "apartment". Because the url will search for
# either house or apartment, and when it goes into the listing, the url of that listing can be a subtype. In each
# iteration, the property_type variable takes one of these values.
# Fetch all pages asynchronously. all_pages is a list of lists, where sublist is collected from specific or batch of pages.
# Result of calls from fetch_all_pages function. List comp. flattens multiple list structure into a single list.
all_pages = []
for property_type in ["house", "apartment"]:
    all_pages.extend(asyncio.run(fetch_all_pages(property_type, cookies, max_pages=200, batch_size=50)))
    total_items = sum(len(sublist) for sublist in all_pages)
    print(f"Collected {total_items} properties so far ...")
    if total_items > 10000:
        break

# Save results to CSV
# The result is a flattened list of all the property dictionaries, where each dictionary represents a single property.
# This flattening is necessary because all_pages initially contains a list of lists (one list per batch of pages),
# but pandas.DataFrame expects a flat list of dictionaries to create a DataFrame.
df = pd.DataFrame([item for sublist in all_pages for item in sublist])
df.to_csv("property_information.csv")