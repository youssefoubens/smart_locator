"""Driver factory helpers for testdemo."""

from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver


def build_driver(headless: bool = True) -> WebDriver:
    """Create a Chrome WebDriver instance."""

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)
