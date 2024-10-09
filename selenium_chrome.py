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

root_url = "https://www.immoweb.be/en/search/house/for-sale?countries=BE&page=1&orderBy=relevance"
# Setup Chrome options
chrome_options = Options() # Options class is used to set up various browser configurations,
chrome_options.add_argument("--disable-infobars")  # Optional: to disable some UI elements

# Uncomment this if you want it to be headless
# chrome_options.add_argument("--headless")

# Create a driver instance with the options
driver = webdriver.Chrome(options=chrome_options)

# Open the website
driver.get(root_url)

# Accept GDPR banner to access page
def accept_gdpr_banner(driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "usercentrics-root")))
        time.sleep(0.05)
        shadow_host = driver.find_element(By.ID, "usercentrics-root")
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
        button = shadow_root.find_element(By.CSS_SELECTOR, '[data-testid=uc-accept-all-button]')
        button.click()
        print("GDPR banner accepted.")
    except Exception as e:
        print(f"An error occurred while accepting GDPR banner: {e}")

def get_property_info(property_type, cookies):
    '''
    Scrapes property listing information from Immoweb for specific property type.
    Args:
        property_type which is a string and the type of property to search for e.g. 'house' or 'apartment'.
        cookies (list) from Selenium for authenticated requests.
    Returns:
        Dictionary of property information
    '''
    params = {
        "countries": "BE",
        "page": 1,
        "orderBy": "relevance"
    }
    root_url_bs = f"https://www.immoweb.be/en/search/{property_type}/for-sale"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    all_listings_list = []

    with Session() as session:
        # Prepare our session
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        response = session.get(root_url_bs, headers=headers, params=params)
        print(response)

        if response.status_code == 200:
        # Parse the content with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all property listings (use the appropriate HTML class or ID)
            listings = soup.find_all('article', class_='card--result')  # Example selector; adjust as needed

            apartment_types = ['ground-floor', 'triplex', 'duplex', 'studio', 'penthouse', 'loft', 'kot',
                               'service-flat']
            house_types = ['bungalow', 'chalet', 'castle', 'farmhouse', 'country-house', 'exceptional-property',
                           'apartment-block', 'mixed-use-building', 'town-house', 'mansion', 'villa',
                           'other-properties', 'manor-house', 'pavilion']
        listing_counter = 0


        for idx, listing in enumerate(listings):
                print(f"Processing listing {idx + 1} out of {len(listings)}")

                listing_url = listing.find('a', class_='card__title-link')['href']
                if "new-real-estate-project" in listing_url or "mixed-use-building" in listing_url or "exceptional-property" in listing_url:
                    continue
                # print(listing_url)
                listing_response = session.get(listing_url, headers=headers)

                listings_dict = {}

                if listing_response.status_code != 200:
                    print(f"Failed to retrieve listing at {listing_url}, Status code: {listing_response.status_code}")
                    continue

                listing_soup = BeautifulSoup(listing_response.text, 'html.parser')

                property_id = listing_soup.find('div', class_="classified__header--immoweb-code")
                if property_id:
                    listings_dict['Property ID'] = property_id.contents[0].strip().split(':')[1]

                locality_name = listing_url.split("/")[7]
                listings_dict["Locality data"] = locality_name

                postal_code = listing_url.split("/")[8]
                listings_dict["Locality data"] = postal_code

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

                type_of_sale = get_page_table_info("Monthly annuity", listing_soup)
                listings_dict["Type of sale"] = type_of_sale

                number_of_bedrooms = get_page_table_info("Bedrooms", listing_soup)
                listings_dict["Number of bedrooms"] = number_of_bedrooms

                living_area = get_page_table_info("Living area", listing_soup)
                listings_dict["Living area m²"] = living_area

                equipped_kitchen = 1 if get_page_table_info("Kitchen type", listing_soup) == "Installed" else 0
                listings_dict['Equipped kitchen'] = equipped_kitchen

                furnished = 1 if get_page_table_info("Furnished", listing_soup) == "Yes" else 0
                listings_dict['Furnished'] = furnished

                open_fire = 1 if get_page_table_info("How many fireplaces?", listing_soup) else 0
                listings_dict['Open fire'] = open_fire

                terrace_surface = get_page_table_info("Terrace surface", listing_soup)
                listings_dict['Terrace surface m²'] = terrace_surface

                garden_area = get_page_table_info("Garden surface", listing_soup)
                listings_dict['Garden area m²'] = garden_area

                number_frontages = get_page_table_info("Number of frontages", listing_soup)
                listings_dict['Number of facades'] = number_frontages

                swimming_pool = 1 if get_page_table_info("Swimming pool", listing_soup) == "Yes" else 0
                listings_dict['Swimming pool'] = swimming_pool

                building_state = get_page_table_info('Building condition', listing_soup)
                listings_dict['Building state'] = building_state

                all_listings_list.append(listings_dict)

        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")

        print(all_listings_list)
        df = pd.DataFrame(all_listings_list)
        df.to_csv("property_information.csv")
        return all_listings_list



def get_page_table_info(header, soup):
    """
       Extracts the numeric value from the <td> element corresponding to a specified <th> header in a table.
       This function searches for a table header (<th>) element with the specified `header` text, ignoring case
       and whitespace discrepancies. Once the header is found, the corresponding <td> element containing the
       data is located. The function then attempts to extract the first numeric value found within the <td> element.
       Args:
           header (str): The text of the header to search for (e.g., "Bedrooms"). The search is case-insensitive and ignores whitespace differences.
           soup (BeautifulSoup): A BeautifulSoup object representing the HTML content of the page to be parsed.
       Returns:
           str: The numeric value extracted from the <td> element associated with the given header.
                Returns None if the header or a numeric value within the <td> cannot be found
       Example:
           If the HTML contains:
           <th class="classified-table__header">Living area</th>
           <td class="classified-table__data">110 <span>m²</span></td>
           Calling get_page_table_info("Living area", soup) will return "110".
       """
    header_tag = soup.find('th', class_='classified-table__header',
                           string=lambda x: x and header.lower() in x.strip().lower())
    if header_tag:
        # Find the corresponding <td> element which contains the information
        table_data = header_tag.find_next('td', class_='classified-table__data')
        if table_data:
            # Extract the text content from the <td>
            text_content = table_data.get_text(separator=" ", strip=True)

            # Find the first numeric value in the text
            match = re.search(r'\d+', text_content)
            if match:
                return match.group()

            # If no number is found with regex, try extracting directly from .contents
            for content in table_data.contents: # Iterates over 'children' of <td> element in table_data
                if isinstance(content, str) and content.strip().isdigit(): # Checks if current 'child' (content) is a
                    # str and contains only numeric after removing leading and trailing whitespace
                    return content.strip() # If condition is True, returns numeric value as string w/out whitespace
    # If do not find header in article, returns None
    return None

accept_gdpr_banner(driver)
cookies = driver.get_cookies()
driver.quit()
get_property_info("house", cookies)




