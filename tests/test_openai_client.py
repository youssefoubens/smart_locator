from unittest.mock import Mock, patch

import pytest

from smart_locator.errors import SmartLocatorError
from smart_locator.openai_client import build_prompt, interpret_query, parse_match_response


def test_build_prompt_includes_url_text_and_parent():
    prompt = build_prompt(
        url="https://example.test/login",
        query="login form",
        elements=[
            {
                "tag": "input",
                "text": "Username",
                "attributes": {"name": "username", "aria-label": "Username"},
                "parent": {"tag": "form", "text": "Login", "attributes": {"id": "login-form"}},
            }
        ],
    )
    assert "Page URL: https://example.test/login" in prompt
    assert "User query: login form" in prompt
    assert "parent tag='form'" in prompt
    assert "aria-label='Username'" in prompt


def test_parse_match_response_handles_json():
    matches = parse_match_response('{"matches":[{"index":1,"reason":"Best match"}]}')
    assert matches == [{"index": 1, "reason": "Best match"}]


@patch("smart_locator.openai_client.OpenAI")
def test_interpret_query_wraps_failures(mock_openai):
    mock_openai.side_effect = RuntimeError("boom")
    with pytest.raises(SmartLocatorError) as exc:
        interpret_query(
            api_key="secret",
            model="gpt-4o",
            url="https://example.test",
            query="login form",
            elements=[],
        )
    assert isinstance(exc.value.__cause__, RuntimeError)
