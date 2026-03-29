"""Generated Selenium test for login with valid credentials."""

from __future__ import annotations

from pages.login_page import LoginPage


def test_login_with_valid_credentials(driver) -> None:
    """Execute the generated test story."""

    page = LoginPage(driver)


    page.get_username_field().send_keys("demo@example.com")



    page.get_password_field().send_keys("password123")



    page.get_submit_button().click()
