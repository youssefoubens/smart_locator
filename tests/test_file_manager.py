from pathlib import Path

from smart_locator.file_manager import FileManager


def test_python_merge_creates_backup_and_appends_new_symbols(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = project_root / "pages" / "login_page.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from selenium.webdriver.common.by import By\n\n"
        "class LoginPage:\n"
        "    USERNAME_FIELD = (By.CSS_SELECTOR, '[name=\"username\"]')\n",
        encoding="utf-8",
    )

    manager = FileManager(project_root, decision_callback=lambda _: "merge")
    incoming = (
        "from selenium.webdriver.common.by import By\n\n"
        "class LoginPage:\n"
        "    PASSWORD_FIELD = (By.CSS_SELECTOR, '[name=\"password\"]')\n\n"
        "def helper():\n"
        "    return 'ok'\n"
    )
    result = manager.write_file("pages/login_page.py", incoming, strategy="ask")

    merged = target.read_text(encoding="utf-8")
    assert result.status == "MERGE"
    assert "helper" in merged
    assert ".backup" in str(next((project_root / ".backup").iterdir()))


def test_robot_merge_combines_sections(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = project_root / "pages" / "login_page.robot"
    target.parent.mkdir(parents=True)
    target.write_text("*** Keywords ***\nGet Username Field\n    [Return]    css:[name=\"username\"]\n", encoding="utf-8")

    manager = FileManager(project_root, decision_callback=lambda _: "merge")
    incoming = "*** Keywords ***\nGet Password Field\n    [Return]    css:[name=\"password\"]\n"
    manager.write_file("pages/login_page.robot", incoming, strategy="ask")

    merged = target.read_text(encoding="utf-8")
    assert "Get Username Field" in merged
    assert "Get Password Field" in merged
