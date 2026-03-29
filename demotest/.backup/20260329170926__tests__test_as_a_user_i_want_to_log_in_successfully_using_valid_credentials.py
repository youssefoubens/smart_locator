"""Generated async Playwright test for as a user i want to log in successfully using valid credentials."""

from __future__ import annotations

import pytest
from playwright.async_api import async_playwright

from pages.login_page import LoginPage


@pytest.mark.asyncio
async def test_as_a_user_i_want_to_log_in_successfully_using_valid_credentials() -> None:
    """Execute the generated Playwright scenario."""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto("/")
        page_object = LoginPage(page)


        await (await page_object.get_selector()).fill("sample value")


        await browser.close()
