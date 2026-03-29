"""Page object for the login page."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from pages.base_page import BasePage


class LoginPage(BasePage):
    """Page object with generated selectors."""


    USERNAME_FIELD = (By.CSS_SELECTOR, "[name=\"username\"]")

    PASSWORD_FIELD = (By.CSS_SELECTOR, "[name=\"password\"]")

    SUBMIT_BUTTON = (By.CSS_SELECTOR, "button[type=\"submit\"]")


    def __init__(self, driver: WebDriver, timeout: int = 10) -> None:
        super().__init__(driver, timeout=timeout)


    def get_username_field(self):
        """Return the username field element."""

        return self.driver.find_element(*self.USERNAME_FIELD)


    def get_password_field(self):
        """Return the password field element."""

        return self.driver.find_element(*self.PASSWORD_FIELD)


    def get_submit_button(self):
        """Return the submit button element."""

        return self.driver.find_element(*self.SUBMIT_BUTTON)
