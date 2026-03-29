"""Generated async Playwright test for login with valid credentials."""

from __future__ import annotations

import pytest
from playwright.async_api import async_playwright

from pages.login_page import LoginPage


@pytest.mark.asyncio
async def test_login_with_valid_credentials() -> None:
    """Execute the generated Playwright scenario."""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto("/")
        page_object = LoginPage(page)


        await (await page_object.get_username_field()).fill("demo@example.com")



        await (await page_object.get_password_field()).fill("password123")



        await (await page_object.get_submit_button()).click()


        await browser.close()
