"""Pytest fixtures for Selenium tests."""

from __future__ import annotations

import pytest

from utils.driver_factory import build_driver


@pytest.fixture()
def driver():
    """Launch a browser session for each test."""

    instance = build_driver()
    instance.get("https://site.com")
    try:
        yield instance
    finally:
        instance.quit()
