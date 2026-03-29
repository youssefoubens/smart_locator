"""Async Playwright page object for login."""

from __future__ import annotations

from playwright.async_api import Page


class LoginPage:
    """Page object with async locator helpers."""


    USERNAME_FIELD = "[name=\"username\"]"

    PASSWORD_FIELD = "[name=\"password\"]"

    SUBMIT_BUTTON = "button[type=\"submit\"]"


    def __init__(self, page: Page) -> None:
        self.page = page


    async def get_username_field(self):
        """Return the username field locator."""

        return self.page.locator(self.USERNAME_FIELD)


    async def get_password_field(self):
        """Return the password field locator."""

        return self.page.locator(self.PASSWORD_FIELD)


    async def get_submit_button(self):
        """Return the submit button locator."""

        return self.page.locator(self.SUBMIT_BUTTON)

"""Async Playwright page object for login."""

"""Async Playwright page object for login."""
