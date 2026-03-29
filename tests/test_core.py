from pathlib import Path
from unittest.mock import Mock, patch
import os

import pytest

from smart_locator import MissingAPIKeyError, SmartLocator


def _driver(elements=None):
    driver = Mock()
    driver.current_url = "https://example.test/login"
    driver.execute_script.return_value = elements or [
        {
            "tag": "input",
            "text": "",
            "attributes": {
                "name": "username",
                "aria-label": "Username",
                "data-testid": "login-username",
                "placeholder": "Email",
            },
            "parent": {"tag": "form", "text": "Login", "attributes": {}},
            "frame_path": [],
            "shadow_path": [],
            "css_path": "form > input",
        }
    ]
    driver.find_elements.return_value = [object()]
    return driver


def test_constructor_requires_driver():
    with pytest.raises(ValueError):
        SmartLocator(None)


@patch("smart_locator.core.interpret_query", return_value=[])
@patch("smart_locator.core.resolve_api_key", return_value="secret")
def test_suggest_returns_dict(mock_key, mock_query, tmp_path: Path):
    locator = SmartLocator(_driver(), cache_path=tmp_path / "cache.db")
    result = locator.suggest("login form", output="dict")
    assert result["elements"][0]["label"] == "Username"
    assert result["elements"][0]["locators"][0]["strategy"] == "data-testid"


def test_missing_api_key_error_message():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(MissingAPIKeyError):
            from smart_locator.openai_client import resolve_api_key

            resolve_api_key(None)


@patch("smart_locator.core.interpret_query", return_value=[])
@patch("smart_locator.core.resolve_api_key", return_value="secret")
def test_generate_code(mock_key, mock_query, tmp_path: Path):
    locator = SmartLocator(_driver(), cache_path=tmp_path / "cache.db")
    code = locator.generate_code("login form")
    assert "By.CSS_SELECTOR" in code
    assert "username" in code


@patch("smart_locator.core.interpret_query", return_value=[])
@patch("smart_locator.core.resolve_api_key", return_value="secret")
def test_suggest_filters_to_relevant_elements(mock_key, mock_query, tmp_path: Path):
    driver = _driver(
        [
            {
                "tag": "input",
                "text": "",
                "attributes": {"name": "username", "id": "username"},
                "parent": {"tag": "form", "text": "Login", "attributes": {}},
                "frame_path": [],
                "shadow_path": [],
                "css_path": "form > input:nth-of-type(1)",
            },
            {
                "tag": "input",
                "text": "",
                "attributes": {"name": "password", "id": "password", "type": "password"},
                "parent": {"tag": "form", "text": "Login", "attributes": {}},
                "frame_path": [],
                "shadow_path": [],
                "css_path": "form > input:nth-of-type(2)",
            },
            {
                "tag": "input",
                "text": "",
                "attributes": {"name": "oauth_token"},
                "parent": {"tag": "form", "text": "Metadata", "attributes": {}},
                "frame_path": [],
                "shadow_path": [],
                "css_path": "form > input:nth-of-type(3)",
            },
        ]
    )
    locator = SmartLocator(driver, cache_path=tmp_path / "cache.db")
    result = locator.suggest("login form", output="dict")
    labels = [item["label"] for item in result["elements"]]
    assert "password" in labels
    assert "username" in labels
    assert len(result["elements"]) <= 5
    assert all(len(item["locators"]) <= 3 for item in result["elements"])


@patch("smart_locator.core.interpret_query", return_value=[{"index": 1, "reason": "Best query match"}])
@patch("smart_locator.core.resolve_api_key", return_value="secret")
def test_validate_and_wait_suggestions(mock_key, mock_query, tmp_path: Path):
    driver = _driver()
    driver.find_elements.return_value = [object(), object()]
    locator = SmartLocator(driver, cache_path=tmp_path / "cache.db")

    validated = locator.validate("login form")
    wait_payload = locator.suggest_wait("login form")

    assert validated["elements"][0]["locators"][0]["validation"].startswith("MULTIPLE")
    assert wait_payload["elements"][0]["timeout"] == 10


@patch("smart_locator.core.interpret_query", return_value=[])
@patch("smart_locator.core.resolve_api_key", return_value="secret")
def test_assist_enriches_exact_selector(mock_key, mock_query, tmp_path: Path):
    locator = SmartLocator(_driver(), cache_path=tmp_path / "cache.db")
    result = locator.assist("username field")

    primary = result["elements"][0]["primary_locator"]
    assert primary["selenium_by"]
    assert primary["selector"] == '[data-testid="login-username"]'
    assert "->" in primary["exact"]


@patch("smart_locator.core.interpret_query", return_value=[])
@patch("smart_locator.core.resolve_api_key", return_value="secret")
def test_invalidate_cache_forces_refresh(mock_key, mock_query, tmp_path: Path):
    locator = SmartLocator(_driver(), cache_path=tmp_path / "cache.db")
    locator.suggest("login form", output="dict")
    locator.invalidate_cache("login form")
    locator.suggest("login form", output="dict")
    assert mock_query.call_count == 2
