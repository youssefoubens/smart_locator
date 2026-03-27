from pathlib import Path
from unittest.mock import Mock, patch

from smart_locator.cli import build_parser, main


def test_build_parser_accepts_commands():
    parser = build_parser()
    args = parser.parse_args(["suggest", "--url", "https://example.test", "--query", "login form"])
    assert args.command == "suggest"


@patch("smart_locator.cli.SmartLocator")
@patch("smart_locator.cli._build_driver")
def test_main_generate_writes_file(mock_driver_factory, mock_locator_cls, tmp_path: Path):
    driver = Mock()
    mock_driver_factory.return_value = driver
    locator = Mock()
    locator.generate_page_object.return_value = "class LoginPage:\n    pass\n"
    locator.suggest.return_value = {"elements": [{"label": "Username"}]}
    mock_locator_cls.return_value = locator

    destination = tmp_path / "login_page.py"
    exit_code = main(
        ["generate", "--url", "https://example.test", "--query", "login form", "--class", "LoginPage", "--out", str(destination)]
    )

    assert exit_code == 0
    assert destination.read_text(encoding="utf-8").startswith("class LoginPage")
    driver.quit.assert_called_once()
