from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

import time

root_url = "https://www.immoweb.be/en/search/house/for-sale?countries=BE&page=1&orderBy=relevance"
geckodriver_path = r"/Users/kelligriffin/immoeliza_scraping/geckodriver"
service = Service(geckodriver_path) # Create a Service object with the path to geckodriver
driver = webdriver.Firefox(service=service)
driver.get(root_url)

# Accept GDPR banner to access page
def get_shadow_root(element):
    return driver.execute_script('return arguments[0].shadowRoot', element)

shadow_host = driver.find_element(By.ID, "usercentrics-root")
button = get_shadow_root(shadow_host).find_element(By.CSS_SELECTOR, '[data-testid=uc-accept-all-button]')
button.click()

# Don't forget to quit the driver once you're done
# driver.quit()
