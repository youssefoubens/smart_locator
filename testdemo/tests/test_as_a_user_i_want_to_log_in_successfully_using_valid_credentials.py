"""Generated Selenium test for as a user i want to log in successfully using valid credentials."""

from __future__ import annotations

from pages.login_page import LoginPage


def test_as_a_user_i_want_to_log_in_successfully_using_valid_credentials(driver) -> None:
    """Execute the generated test story."""

    page = LoginPage(driver)


    page.get_login().send_keys("sample value")
