from selenium import webdriver
from smart_locator import SmartLocator

driver = webdriver.Chrome()
driver.get("https://site.com/login")

sl = SmartLocator(driver)
print(sl.suggest("login form"))

driver.quit()