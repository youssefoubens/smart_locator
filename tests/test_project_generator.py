from pathlib import Path

from smart_locator.config import ProjectConfig, load_config
from smart_locator.file_manager import FileManager
from smart_locator.project_generator import ProjectGenerator


def test_initialize_project_creates_selenium_structure(tmp_path: Path):
    project_root = tmp_path / "demo"
    config = ProjectConfig(
        project_name="demo",
        target_url="https://example.test/login",
        framework="selenium",
        project_root=project_root,
    )

    generator = ProjectGenerator(config, file_manager=FileManager(project_root, decision_callback=lambda _: "overwrite"))
    result = generator.initialize_project(strategy="overwrite")

    assert result.operations
    assert (project_root / "smartlocator.config.json").exists()
    assert (project_root / "pages" / "base_page.py").exists()
    assert (project_root / "tests" / "test_login.py").exists()
    saved = load_config(project_root)
    assert "pages/base_page.py" in saved.generated_files


def test_generate_story_updates_page_and_test(tmp_path: Path):
    project_root = tmp_path / "demo"
    config = ProjectConfig(
        project_name="demo",
        target_url="https://example.test/login",
        framework="selenium",
        project_root=project_root,
    )
    generator = ProjectGenerator(config, file_manager=FileManager(project_root, decision_callback=lambda _: "overwrite"))
    generator.initialize_project(strategy="overwrite")

    result = generator.generate_story(
        page_name="checkout",
        page_class_name="CheckoutPage",
        test_name="checkout_flow",
        steps=[
            {"keyword": "fill", "field_name": "email_field", "selector": '[name="email"]', "value": "demo@example.com"},
            {"keyword": "click", "field_name": "continue_button", "selector": 'button[type="submit"]', "value": ""},
        ],
        strategy="overwrite",
    )

    assert (project_root / "pages" / "checkout_page.py").exists()
    assert (project_root / "tests" / "test_checkout_flow.py").exists()
    assert any(operation.status == "CREATE" for operation in result.operations)
