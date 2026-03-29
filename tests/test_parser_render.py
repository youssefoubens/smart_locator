from unittest.mock import Mock

from smart_locator.parser import PARSER_SCRIPT, parse_dom, truncate_context
from smart_locator.render import (
    format_chat_reply,
    format_tester_workspace,
    render_page_object,
    render_python_snippets,
    score_bar,
    snake_case,
)


def test_parse_dom_executes_script():
    driver = Mock()
    driver.execute_script.return_value = [{"tag": "button"}]
    assert parse_dom(driver) == [{"tag": "button"}]
    driver.execute_script.assert_called_once_with(PARSER_SCRIPT)


def test_truncate_context_limits_elements():
    items = [{"index": 1}, {"index": 2}, {"index": 3}]
    assert truncate_context(items, limit=2) == [{"index": 1}, {"index": 2}]


def test_render_helpers_generate_python():
    elements = [
        {
            "label": "Username",
            "locators": [{"strategy": "data-testid", "value": "login-username", "score": 98}],
        }
    ]
    snippet = render_python_snippets(elements)
    page_object = render_page_object("LoginPage", elements)
    assert "By.CSS_SELECTOR" in snippet
    assert "LOGINPAGE" not in page_object
    assert "class LoginPage" in page_object
    assert "get_username" in page_object


def test_snake_case_and_score_bar():
    assert snake_case("User Name") == "user_name"
    assert score_bar(50, width=4) == "##--"


def test_format_suggestions_renders_table():
    from smart_locator.render import format_suggestions

    output = format_suggestions(
        [
            {
                "label": "Username",
                "locators": [
                    {
                        "strategy": "name",
                        "value": "username",
                        "score": 84,
                        "reason": "Matches query keywords (2 hits).",
                        "tier": "GOOD",
                    }
                ],
            }
        ]
    )
    assert "Element" in output
    assert "Username" in output
    assert "Matches query keywords" in output


def test_tester_workspace_and_chat_reply_render_exact_selector():
    payload = {
        "query": "username field",
        "url": "https://example.test/login",
        "elements": [
            {
                "label": "Username",
                "frame_path": [],
                "shadow_path": [],
                "primary_locator": {
                    "strategy": "data-testid",
                    "score": 98,
                    "tier": "BEST",
                    "reason": "Stable test hook.",
                    "exact": 'css selector -> [data-testid="login-username"]',
                    "validation": "FOUND",
                },
                "locators": [
                    {
                        "strategy": "data-testid",
                        "selector": '[data-testid="login-username"]',
                        "exact": 'css selector -> [data-testid="login-username"]',
                    },
                    {
                        "strategy": "name",
                        "selector": "username",
                        "exact": "name -> username",
                    },
                ],
            }
        ],
    }

    workspace = format_tester_workspace(payload)
    reply = format_chat_reply(payload)

    assert "Tester Workspace" in workspace
    assert "Exact selector" in workspace
    assert '[data-testid="login-username"]' in workspace
    assert 'Best selector for "username field"' in reply
    assert "Fallbacks:" in reply
