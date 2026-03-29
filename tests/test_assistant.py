from pathlib import Path
from unittest.mock import Mock, patch

from smart_locator.assistant import SmartAssistant
from smart_locator.config import ProjectConfig, save_config
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


def test_noninteractive_action_requests_chat_mode(tmp_path: Path):
    locator = Mock()
    locator.assist.return_value = _selector_payload()
    assistant = SmartAssistant(locator, tmp_path)

    reply = assistant.answer("create login page", interactive=False)

    assert "Start `smart-locator assist" in reply


def test_story_generation_uses_project_context(tmp_path: Path):
    project_root = tmp_path / "demo"
    config = ProjectConfig(
        project_name="demo",
        target_url="https://example.test/login",
        framework="selenium",
        project_root=project_root,
    )
    save_config(config)
    ProjectGenerator(config).initialize_project(strategy="overwrite")
    locator = Mock()
    locator.assist.return_value = _selector_payload()
    locator.current_url = "https://example.test/login"

    assistant = SmartAssistant(locator, project_root)
    with patch("builtins.input", side_effect=["y", "overwrite", "overwrite"]):
        reply = assistant.answer("create Login with valid credentials", interactive=True)

    assert "[✓ CREATE]" in reply
    assert (project_root / "pages" / "login_page.py").exists()
    assert (project_root / "tests" / "test_login_with_valid_credentials.py").exists()
