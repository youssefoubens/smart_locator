"""Generated async Playwright test for as a user i want to log in successfully using valid credentials."""

from __future__ import annotations

import pytest
from playwright.async_api import async_playwright, expect

from pages.login_page import LoginPage


@pytest.mark.asyncio
async def test_as_a_user_i_want_to_log_in_successfully_using_valid_credentials() -> None:
    """as a user i want to log in successfully using valid credentials"""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://site.com")
        page_object = LoginPage(page)



        username_field = await page_object.get_username_field()
        await username_field.fill("demo@example.com")




        password_field = await page_object.get_password_field()
        await password_field.fill("password123")




        submit_button = await page_object.get_submit_button()
        await submit_button.click()




        success_message = await page_object.get_success_message()
        await expect(success_message).to_be_visible()



        await browser.close()
