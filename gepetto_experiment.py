from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time

root_url = "https://www.immoweb.be/en/search/house/for-sale?countries=BE&page=1&orderBy=relevance"

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-infobars")  # Optional: to disable some UI elements
chrome_options.add_argument("--start-maximized")   # Optional: to start maximized

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
        shadow_host = driver.find_element(By.ID, "usercentrics-root")
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
        button = shadow_root.find_element(By.CSS_SELECTOR, '[data-testid=uc-accept-all-button]')
        button.click()
        print("GDPR banner accepted.")
    except Exception as e:
        print(f"An error occurred while accepting GDPR banner: {e}")

accept_gdpr_banner(driver)

# Extract listing information
def extract_listings(driver):
    listings_extracted = 0
    while listings_extracted < 100:
        try:
            # Wait for listings to load
            listings = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[class*='card--result__body']"))
            )
            for listing in listings:
                if listings_extracted >= 100:
                    break
                
                # Extract title or description
                title_element = listing.find_element(By.CSS_SELECTOR, "h2.card__title a")
                title = title_element.text if title_element else "N/A"
                
                # Extract price
                price_element = listing.find_element(By.CSS_SELECTOR, "p.card--result__price span[aria-hidden='true']")
                price = price_element.text if price_element else "N/A"
                
                # Extract location
                location_element = listing.find_element(By.CSS_SELECTOR, "p.card__information.card--results__information--locality")
                location = location_element.text.strip() if location_element else "N/A"
                
                # Extract URL (link to listing)
                url = title_element.get_attribute('href') if title_element else "N/A"
                
                # Open the listing for extra data
                driver.execute_script("window.open(arguments[0], '_blank');", url)
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2)  # Let the page load
                try:
                    description_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "p[class*='classified__description']"))
                    )
                    description = description_element.text if description_element else "N/A"
                except Exception as e:
                    description = "N/A"
                    print(f"An error occurred while extracting description: {e}")
                
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                
                # Print the extracted information
                print(f"Title: {title}")
                print(f"Price: {price}")
                print(f"Location: {location}")
                print(f"URL: {url}")
                print(f"Description: {description}\n")
                
                listings_extracted += 1
            
            # Click the next page button
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.pagination__link.pagination__link--next"))
            )
            next_button.click()
            time.sleep(2)  # Wait for the next page to load
        except Exception as e:
            print(f"An error occurred while extracting listings: {e}")
            break

# Call the function to extract listings
extract_listings(driver)

# Keep the browser open for you to observe or quit when done
time.sleep(10)  # Let it stay open for a while to observe, adjust as necessary
driver.quit()