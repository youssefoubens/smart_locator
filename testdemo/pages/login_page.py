"""Page object for the login page."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from pages.base_page import BasePage


class LoginPage(BasePage):
    """Page object with generated selectors."""


    LOGIN = (By.CSS_SELECTOR, "[data-smart-locator=\"login\"]")


    def __init__(self, driver: WebDriver, timeout: int = 10) -> None:
        super().__init__(driver, timeout=timeout)


    def get_login(self):
        """Return the login element."""

        return self.driver.find_element(*self.LOGIN)
