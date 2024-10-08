import time
from requests import Session
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

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
        time.sleep(1)
        shadow_host = driver.find_element(By.ID, "usercentrics-root")
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
        button = shadow_root.find_element(By.CSS_SELECTOR, '[data-testid=uc-accept-all-button]')
        button.click()
        print("GDPR banner accepted.")
    except Exception as e:
        print(f"An error occurred while accepting GDPR banner: {e}")

def get_property_info(property_type, cookies):
    params = {
        "countries": "BE",
        "page": 1,
        "orderBy": "relevance"
    }
    root_url_bs = f"https://www.immoweb.be/en/search/{property_type}/for-sale"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
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

            for listing in listings:
                # Extract the details if not project
                listing_url = listing.find('a', class_='card__title-link')['href']
                if "new-real-estate-project" in listing_url:
                    continue
                print(listing_url)
                listing_response = session.get(listing_url, headers=headers)
                listing_soup = BeautifulSoup(listing_response.text, 'html.parser')
                # Property ID
                property_id = listing_soup.find('div', class_="classified__header--immoweb-code").contents[0].strip().split(':')[1]
                # Locality name
                locality_name = listing_url.split("/")[7]
                # Postal code
                postal_code = listing_url.split("/")[8]
                print(postal_code, locality_name, sep=" ")
                # Price
                price = listing_soup.find('span', class_='sr-only').contents
                # Type of property (house or apartment)
                subtype = listing_url.split("/")[5]
                print(property_type, subtype, sep=" ")
                # Subtype of property (bungalow, chalet, mansion, ...)
                # Type of sale (note: exclude life sales) if not available for house, then can be ignored
                # Number of rooms
                number_of_bedrooms = get_page_table_info("Bedrooms", listing_soup)
                # Living area (area in m²)
                living_area = get_page_table_info("Living area ", listing_soup)
                # Equipped kitchen (0/1)
                equipped_kitchen = 1 if get_page_table_info("Kitchen type", listing_soup) == "Installed" else 0
                # Furnished (0/1)
                furnished = 1 if get_page_table_info("Furnished", listing_soup) == "Yes" else 0
                # Open fire (0/1) How many fireplaces?
                open_fire = 1 if get_page_table_info("How many fireplaces?", listing_soup) else 0
                # Terrace (area in m² or null if no terrace)
                terrace_surface = get_page_table_info("Terrace surface", listing_soup)
                # Garden (area in m² or null if no garden)
                garden_area = get_page_table_info("Garden surface", listing_soup)
                # Number of facades
                number_frontages = get_page_table_info("Number of frontages", listing_soup)
                # Swimming pool (0/1)
                swimming_pool = 1 if get_page_table_info("Swimming pool", listing_soup) == "Yes" else 0
                # State of building (new, to be renovated, ...)
                building_state = get_page_table_info('Building condition', listing_soup)

        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")

def get_page_table_info(header, soup):
    # Find the <th> tag with a loose match to the header text
    header_tag = soup.find('th', class_='classified-table__header', text=lambda x: x and header.lower() in x.strip().lower())
    if header_tag:
        # Find the corresponding <td> element which contains the information
        table_data = header_tag.find_next('td', class_='classified-table__data')
        if table_data:
            return table_data.get_text(strip=True)
    return None


accept_gdpr_banner(driver)
cookies = driver.get_cookies()
driver.quit()
get_property_info("house", cookies)


