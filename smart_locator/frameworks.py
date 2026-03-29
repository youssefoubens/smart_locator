"""Framework adapters and registry for project generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from .config import ProjectConfig


@dataclass(frozen=True)
class TemplateSpec:
    """Maps a package template to a generated project file."""

    template_name: str
    output_path: str
    context: Dict[str, object]


class BaseFramework:
    """Adapter contract for framework-specific generation."""

    name = "base"

    def template_dir(self) -> str:
        return self.name

    def requirements(self) -> List[str]:
        raise NotImplementedError

    def init_templates(self, config: ProjectConfig) -> Sequence[TemplateSpec]:
        raise NotImplementedError

    def story_templates(
        self,
        config: ProjectConfig,
        page_name: str,
        page_class_name: str,
        test_name: str,
        steps: Sequence[Dict[str, str]],
    ) -> Sequence[TemplateSpec]:
        raise NotImplementedError

    def merge_target_for_locator(self, page_name: str) -> str:
        raise NotImplementedError

    def merge_snippet(self, page_name: str, field_name: str, selector: str) -> str:
        raise NotImplementedError

    def test_command(self, config: ProjectConfig) -> List[str]:
        raise NotImplementedError

    def display_tree(self) -> Iterable[str]:
        raise NotImplementedError

    def page_file_name(self, page_name: str) -> str:
        return f"{page_name}_page"


class SeleniumFramework(BaseFramework):
    name = "selenium"

    def requirements(self) -> List[str]:
        return ["selenium>=4.14", "pytest>=8.3"]

    def init_templates(self, config: ProjectConfig) -> Sequence[TemplateSpec]:
        page_name = "login"
        page_class_name = "LoginPage"
        return [
            TemplateSpec("base_page.py.j2", "pages/base_page.py", {"project_name": config.project_name}),
            TemplateSpec("driver_factory.py.j2", "utils/driver_factory.py", {"project_name": config.project_name}),
            TemplateSpec("conftest.py.j2", "tests/conftest.py", {"target_url": config.target_url}),
            TemplateSpec(
                "page.py.j2",
                f"pages/{page_name}_page.py",
                {
                    "page_class_name": page_class_name,
                    "page_name": page_name,
                    "locators": [
                        {"field_name": "username_field", "selector": '[name="username"]'},
                        {"field_name": "password_field", "selector": '[name="password"]'},
                        {"field_name": "submit_button", "selector": 'button[type="submit"]'},
                    ],
                },
            ),
            TemplateSpec(
                "test_file.py.j2",
                "tests/test_login.py",
                {
                    "class_name": page_class_name,
                    "page_name": page_name,
                    "scenario_name": "login with valid credentials",
                    "test_function_name": "login_with_valid_credentials",
                    "elements": self._step_actions(
                        {"keyword": "fill", "field_name": "username_field", "value": "demo@example.com"},
                        {"keyword": "fill", "field_name": "password_field", "value": "password123"},
                        {"keyword": "click", "field_name": "submit_button", "value": ""},
                    ),
                    "test_data": {
                        "username_field": "demo@example.com",
                        "password_field": "password123",
                    },
                    "base_url": config.target_url,
                },
            ),
        ]

    def story_templates(
        self,
        config: ProjectConfig,
        page_name: str,
        page_class_name: str,
        test_name: str,
        steps: Sequence[Dict[str, str]],
    ) -> Sequence[TemplateSpec]:
        locators = [step for step in steps if step["keyword"] != "goto"]
        return [
            TemplateSpec(
                "page.py.j2",
                f"pages/{self.page_file_name(page_name)}.py",
                {"page_class_name": page_class_name, "page_name": page_name, "locators": locators},
            ),
            TemplateSpec(
                "test_file.py.j2",
                f"tests/test_{test_name}.py",
                {
                    "class_name": page_class_name,
                    "page_name": page_name,
                    "scenario_name": test_name.replace("_", " "),
                    "test_function_name": test_name,
                    "elements": self._step_actions(*steps),
                    "test_data": self._step_values(*steps),
                    "base_url": config.target_url,
                },
            ),
        ]

    def merge_target_for_locator(self, page_name: str) -> str:
        return f"pages/{self.page_file_name(page_name)}.py"

    def merge_snippet(self, page_name: str, field_name: str, selector: str) -> str:
        class_name = "".join(part.title() for part in page_name.split("_")) + "Page"
        method_name = f"get_{field_name}"
        constant_name = field_name.upper()
        return "\n".join(
            [
                "from selenium.webdriver.common.by import By",
                "",
                f"class {class_name}:",
                f"    {constant_name} = (By.CSS_SELECTOR, {selector!r})",
                "",
                f"    def {method_name}(self):",
                f"        return self.driver.find_element(*self.{constant_name})",
                "",
            ]
        )

    def test_command(self, config: ProjectConfig) -> List[str]:
        return ["pytest", "-q"]

    def display_tree(self) -> Iterable[str]:
        return [
            "pages/",
            "pages/base_page.py",
            "pages/login_page.py",
            "tests/",
            "tests/conftest.py",
            "tests/test_login.py",
            "utils/",
            "utils/driver_factory.py",
            "requirements.txt",
        ]

    def _step_actions(self, *steps: Dict[str, str]) -> Dict[str, str]:
        return {step["field_name"]: self._normalize_action(step["keyword"]) for step in steps}

    def _step_values(self, *steps: Dict[str, str]) -> Dict[str, str]:
        return {step["field_name"]: step.get("value", "") for step in steps if step.get("value")}

    def _normalize_action(self, action: str) -> str:
        if action in {"verify", "assert"}:
            return "assert_visible"
        return action


class PlaywrightFramework(BaseFramework):
    name = "playwright"

    def requirements(self) -> List[str]:
        return ["playwright>=1.51", "pytest>=8.3", "pytest-asyncio>=0.24"]

    def init_templates(self, config: ProjectConfig) -> Sequence[TemplateSpec]:
        page_name = "login"
        return [
            TemplateSpec("playwright.config.py.j2", "playwright.config.py", {"target_url": config.target_url}),
            TemplateSpec(
                "page.py.j2",
                f"pages/{self.page_file_name(page_name)}.py",
                {
                    "page_class_name": "LoginPage",
                    "page_name": page_name,
                    "locators": [
                        {"field_name": "username_field", "selector": '[name="username"]'},
                        {"field_name": "password_field", "selector": '[name="password"]'},
                        {"field_name": "submit_button", "selector": 'button[type="submit"]'},
                    ],
                },
            ),
            TemplateSpec(
                "test_file.py.j2",
                "tests/test_login.py",
                {
                    "class_name": "LoginPage",
                    "page_name": page_name,
                    "scenario_name": "login with valid credentials",
                    "test_function_name": "login_with_valid_credentials",
                    "elements": self._step_actions(
                        {"keyword": "fill", "field_name": "username_field", "value": "demo@example.com"},
                        {"keyword": "fill", "field_name": "password_field", "value": "password123"},
                        {"keyword": "click", "field_name": "submit_button", "value": ""},
                    ),
                    "test_data": {
                        "username_field": "demo@example.com",
                        "password_field": "password123",
                    },
                    "base_url": config.target_url,
                },
            ),
        ]

    def story_templates(
        self,
        config: ProjectConfig,
        page_name: str,
        page_class_name: str,
        test_name: str,
        steps: Sequence[Dict[str, str]],
    ) -> Sequence[TemplateSpec]:
        locators = [step for step in steps if step["keyword"] != "goto"]
        return [
            TemplateSpec(
                "page.py.j2",
                f"pages/{self.page_file_name(page_name)}.py",
                {"page_class_name": page_class_name, "page_name": page_name, "locators": locators},
            ),
            TemplateSpec(
                "test_file.py.j2",
                f"tests/test_{test_name}.py",
                {
                    "class_name": page_class_name,
                    "page_name": page_name,
                    "scenario_name": test_name.replace("_", " "),
                    "test_function_name": test_name,
                    "elements": self._step_actions(*steps),
                    "test_data": self._step_values(*steps),
                    "base_url": config.target_url,
                },
            ),
        ]

    def merge_target_for_locator(self, page_name: str) -> str:
        return f"pages/{self.page_file_name(page_name)}.py"

    def merge_snippet(self, page_name: str, field_name: str, selector: str) -> str:
        class_name = "".join(part.title() for part in page_name.split("_")) + "Page"
        return "\n".join(
            [
                f"class {class_name}:",
                f"    {field_name.upper()} = {selector!r}",
                "",
                f"    async def get_{field_name}(self):",
                f"        return self.page.locator(self.{field_name.upper()})",
                "",
            ]
        )

    def test_command(self, config: ProjectConfig) -> List[str]:
        return ["playwright", "test"]

    def display_tree(self) -> Iterable[str]:
        return [
            "pages/",
            "pages/login_page.py",
            "tests/",
            "tests/test_login.py",
            "playwright.config.py",
            "requirements.txt",
        ]

    def _step_actions(self, *steps: Dict[str, str]) -> Dict[str, str]:
        return {step["field_name"]: self._normalize_action(step["keyword"]) for step in steps}

    def _step_values(self, *steps: Dict[str, str]) -> Dict[str, str]:
        return {step["field_name"]: step.get("value", "") for step in steps if step.get("value")}

    def _normalize_action(self, action: str) -> str:
        if action in {"verify", "assert"}:
            return "assert_visible"
        return action


class RobotFrameworkAdapter(BaseFramework):
    name = "robot"

    def requirements(self) -> List[str]:
        return ["robotframework>=7.0", "seleniumlibrary>=6.2"]

    def init_templates(self, config: ProjectConfig) -> Sequence[TemplateSpec]:
        return [
            TemplateSpec("variables.robot.j2", "resources/variables.robot", {"target_url": config.target_url}),
            TemplateSpec("keywords.robot.j2", "resources/keywords.robot", {"project_name": config.project_name}),
            TemplateSpec("page_object.robot.j2", "pages/login_page.robot", {"page_name": "login"}),
            TemplateSpec(
                "test_file.robot.j2",
                "tests/login.robot",
                {
                    "scenario_name": "Login with valid credentials",
                    "steps": [
                        {"keyword": "fill", "field_name": "username_field", "selector": '[name="username"]', "value": "demo@example.com"},
                        {"keyword": "fill", "field_name": "password_field", "selector": '[name="password"]', "value": "password123"},
                        {"keyword": "click", "field_name": "submit_button", "selector": 'button[type="submit"]', "value": ""},
                    ],
                    "base_url": config.target_url,
                    "test_data": {
                        "username_field": "demo@example.com",
                        "password_field": "password123",
                    },
                },
            ),
        ]

    def story_templates(
        self,
        config: ProjectConfig,
        page_name: str,
        page_class_name: str,
        test_name: str,
        steps: Sequence[Dict[str, str]],
    ) -> Sequence[TemplateSpec]:
        return [
            TemplateSpec("page_object.robot.j2", f"pages/{page_name}_page.robot", {"page_name": page_name}),
            TemplateSpec(
                "test_file.robot.j2",
                f"tests/{test_name}.robot",
                {
                    "scenario_name": test_name.replace("_", " ").title(),
                    "steps": list(steps),
                    "base_url": config.target_url,
                    "test_data": self._step_values(*steps),
                },
            ),
        ]

    def merge_target_for_locator(self, page_name: str) -> str:
        return f"pages/{page_name}_page.robot"

    def merge_snippet(self, page_name: str, field_name: str, selector: str) -> str:
        keyword_name = field_name.replace("_", " ").title()
        return "\n".join(
            [
                "*** Keywords ***",
                f"Get {keyword_name}",
                f"    [Return]    {selector}",
                "",
            ]
        )

    def test_command(self, config: ProjectConfig) -> List[str]:
        return ["robot", "tests"]

    def display_tree(self) -> Iterable[str]:
        return [
            "pages/",
            "pages/login_page.robot",
            "resources/",
            "resources/keywords.robot",
            "resources/variables.robot",
            "tests/",
            "tests/login.robot",
            "requirements.txt",
        ]

    def _step_values(self, *steps: Dict[str, str]) -> Dict[str, str]:
        return {step["field_name"]: step.get("value", "") for step in steps if step.get("value")}


FRAMEWORKS = {
    "selenium": SeleniumFramework,
    "playwright": PlaywrightFramework,
    "robot": RobotFrameworkAdapter,
}


def get_framework(name: str) -> BaseFramework:
    try:
        return FRAMEWORKS[name.lower()]()
    except KeyError as exc:
        raise ValueError(f"Unsupported framework: {name}") from exc
