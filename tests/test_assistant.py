from pathlib import Path
from unittest.mock import Mock, patch

from smart_locator.assistant import SmartAssistant
from smart_locator.config import ProjectConfig, save_config
from smart_locator.errors import SmartLocatorError
from smart_locator.project_generator import ProjectGenerator


def _selector_payload(selector='[data-testid="login-button"]'):
    return {
        "query": "login button",
        "url": "https://example.test/login",
        "elements": [
            {
                "label": "Login",
                "primary_locator": {
                    "strategy": "data-testid",
                    "score": 98,
                    "tier": "BEST",
                    "reason": "Stable hook.",
                    "selector": selector,
                    "exact": f"css selector -> {selector}",
                    "validation": "FOUND",
                },
                "locators": [
                    {
                        "strategy": "data-testid",
                        "selector": selector,
                        "exact": f"css selector -> {selector}",
                    }
                ],
            }
        ],
    }


def _project_root(tmp_path: Path) -> Path:
    project_root = tmp_path / "demo"
    config = ProjectConfig(
        project_name="demo",
        target_url="https://example.test/login",
        framework="selenium",
        project_root=project_root,
    )
    save_config(config)
    ProjectGenerator(config).initialize_project(strategy="overwrite")
    return project_root


def test_noninteractive_action_requests_chat_mode(tmp_path: Path):
    locator = Mock()
    locator.assist.return_value = _selector_payload()
    assistant = SmartAssistant(locator, tmp_path)

    reply = assistant.answer("create login page", interactive=False)

    assert "Start `smart-locator assist" in reply


def test_guided_workflow_generates_story_assets(tmp_path: Path):
    project_root = _project_root(tmp_path)
    locator = Mock()
    locator.assist.return_value = _selector_payload()
    locator.current_url = "https://example.test/login"

    assistant = SmartAssistant(locator, project_root)

    reply = assistant.answer("As a user, I want to log in successfully using valid credentials.", interactive=True)
    assert "Scenario analysis" in reply

    reply = assistant.answer("yes", interactive=True)
    assert "What is the name of the page?" in reply

    reply = assistant.answer("login", interactive=True)
    assert "Which elements should be included?" in reply

    reply = assistant.answer("suggested", interactive=True)
    assert "Do you want to use POM structure?" in reply

    reply = assistant.answer("yes", interactive=True)
    assert "Do you want to add selectors now?" in reply

    reply = assistant.answer("yes", interactive=True)
    assert "auto-generated or manually confirmed" in reply

    reply = assistant.answer("auto", interactive=True)
    assert "file strategy" in reply

    reply = assistant.answer("overwrite", interactive=True)
    assert "Workflow summary" in reply

    with patch("builtins.input", side_effect=["overwrite", "overwrite"]):
        reply = assistant.answer("yes", interactive=True)

    assert "Your scenario is fully implemented." in reply
    assert (project_root / "pages" / "login_page.py").exists()
    assert (project_root / "tests" / "test_as_a_user_i_want_to_log_in_successfully_using_valid_credentials.py").exists()


def test_manual_selector_review_accepts_overrides(tmp_path: Path):
    project_root = _project_root(tmp_path)
    locator = Mock()
    locator.assist.return_value = _selector_payload('[name="username"]')
    locator.current_url = "https://example.test/login"

    assistant = SmartAssistant(locator, project_root)
    assistant.answer("As a user, I want to log in successfully using valid credentials.", interactive=True)
    assistant.answer("yes", interactive=True)
    assistant.answer("login", interactive=True)
    assistant.answer("suggested", interactive=True)
    assistant.answer("yes", interactive=True)
    assistant.answer("yes", interactive=True)
    reply = assistant.answer("manual", interactive=True)

    assert "Selector review" in reply
    reply = assistant.answer('username_field=[data-testid="login-username"]', interactive=True)
    assert "file strategy" in reply


def test_selector_reply_handles_locator_service_failure(tmp_path: Path):
    locator = Mock()
    locator.assist.side_effect = SmartLocatorError("Connection error.")
    assistant = SmartAssistant(locator, tmp_path)

    reply = assistant.answer("login button", interactive=True)

    assert "could not reach the selector service" in reply.lower()
