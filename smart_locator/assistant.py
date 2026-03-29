"""Tester-oriented interactive assistant utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .config import discover_config
from .file_manager import FileManager
from .project_generator import ProjectGenerator
from .render import format_chat_reply, format_operation_results, format_tester_workspace
from .test_runner import run_tests


EXIT_WORDS = {"exit", "quit", "q"}
ACTION_WORDS = ("create", "add", "generate", "run tests", "show project structure")


@dataclass
class SessionContext:
    """Conversation state for the tester assistant."""

    project_root: Optional[Path] = None
    framework: Optional[str] = None
    active_page: Optional[str] = None
    files_generated: List[str] = field(default_factory=list)


class SmartAssistant:
    """Intent-aware assistant for selectors and project automation."""

    def __init__(self, locator, workspace: Path) -> None:
        self.locator = locator
        self.workspace = workspace
        self.context = SessionContext()
        self._load_context()

    def answer(self, query: str, *, interactive: bool) -> str:
        intent = self._detect_intent(query)
        if intent == "selector":
            return self._selector_reply(query)
        if intent == "show_project_structure":
            return self._show_project_structure()
        if not interactive:
            return "This action changes project files. Start `smart-locator assist --url <url>` and confirm the action in chat."
        return self._handle_action(intent, query)

    def _selector_reply(self, query: str) -> str:
        payload = self.locator.assist(query, validate=True)
        workspace = format_tester_workspace(payload)
        reply = format_chat_reply(payload)
        return f"{workspace}\n\nChatbot\n{reply}".strip()

    def _handle_action(self, intent: str, query: str) -> str:
        if intent == "run_tests":
            return self._run_tests()
        if intent == "create_page":
            page_name = self._extract_page_name(query)
            return self._create_page(page_name)
        if intent == "add_field":
            field_name = self._extract_field_name(query)
            return self._add_field(field_name)
        if intent == "generate_test":
            page_name = self.context.active_page or self._extract_page_name(query)
            return self._generate_test(page_name)
        if intent == "create_story":
            return self._create_story(query)
        return self._selector_reply(query)

    def _create_page(self, page_name: str) -> str:
        generator = self._require_generator()
        page_class_name = self._class_name(page_name)
        explanation = (
            f"I can scaffold the `{page_name}` page object for the `{self.context.framework}` project. "
            "This will create or update the framework page file using the file manager."
        )
        if not self._confirm(explanation):
            return "Action canceled."
        steps = [
            {"keyword": "fill", "field_name": "username_field", "selector": '[name="username"]', "value": "demo@example.com"},
            {"keyword": "fill", "field_name": "password_field", "selector": '[name="password"]', "value": "password123"},
            {"keyword": "click", "field_name": "login_button", "selector": 'button[type="submit"]', "value": ""},
        ]
        result = generator.generate_story(
            page_name=page_name,
            page_class_name=page_class_name,
            test_name=page_name,
            steps=steps,
            strategy="ask",
        )
        self.context.active_page = page_name
        self._remember_operations(result.operations)
        return self._format_result(explanation, result.operations)

    def _add_field(self, field_name: str) -> str:
        generator = self._require_generator()
        page_name = self.context.active_page or "login"
        payload = self.locator.assist(field_name, validate=True)
        primary = payload["elements"][0]["primary_locator"] if payload.get("elements") else {}
        selector = str(primary.get("selector", f'[name="{field_name.replace("_field", "")}"]'))
        explanation = (
            f"I found `{selector}` for `{field_name}` and can merge it into `{page_name}`. "
            "If the page file already exists, I’ll ask whether to merge, overwrite, or skip."
        )
        if not self._confirm(explanation):
            return "Action canceled."
        operation = generator.merge_locator(page_name=page_name, field_name=field_name, selector=selector, strategy="ask")
        self._remember_operations([operation])
        return self._format_result(explanation, [operation])

    def _generate_test(self, page_name: str) -> str:
        generator = self._require_generator()
        explanation = (
            f"I can generate a `{page_name}` test from the active page context for `{self.context.framework}`. "
            "This will update the test file through the file manager."
        )
        if not self._confirm(explanation):
            return "Action canceled."
        steps = [
            {"keyword": "fill", "field_name": "username_field", "selector": '[name="username"]', "value": "demo@example.com"},
            {"keyword": "fill", "field_name": "password_field", "selector": '[name="password"]', "value": "password123"},
            {"keyword": "click", "field_name": "login_button", "selector": 'button[type="submit"]', "value": ""},
        ]
        result = generator.generate_story(
            page_name=page_name,
            page_class_name=self._class_name(page_name),
            test_name=page_name,
            steps=steps,
            strategy="ask",
        )
        self._remember_operations(result.operations)
        return self._format_result(explanation, result.operations)

    def _create_story(self, query: str) -> str:
        generator = self._require_generator()
        story = self._extract_story(query)
        steps = self._story_steps(story)
        explanation = (
            f"I parsed the story into {len(steps)} step(s) and will generate or update the matching page object and test. "
            "Selectors come from SmartLocator where possible, with safe fallbacks when no confident match exists."
        )
        if not self._confirm(explanation):
            return "Action canceled."
        page_name = self._extract_page_name(story)
        result = generator.generate_story(
            page_name=page_name,
            page_class_name=self._class_name(page_name),
            test_name=self._slugify(story),
            steps=steps,
            strategy="ask",
        )
        self.context.active_page = page_name
        self._remember_operations(result.operations)
        return self._format_result(explanation, result.operations)

    def _run_tests(self) -> str:
        if self.context.project_root is None:
            return "No generated project is active yet. Run `smart-locator init` first."
        explanation = f"I can run the `{self.context.framework}` suite from `{self.context.project_root}`."
        if not self._confirm(explanation):
            return "Action canceled."
        exit_code = run_tests(self.context.project_root)
        return f"{explanation}\nFinished with exit code {exit_code}."

    def _show_project_structure(self) -> str:
        if self.context.project_root is None:
            return "No generated project is active yet. Run `smart-locator init` first."
        generator = self._require_generator()
        tree = generator.show_project_structure()
        return f"Project structure for `{self.context.framework}`:\n{tree}"

    def _story_steps(self, story: str) -> List[Dict[str, str]]:
        lowered = story.lower()
        if "login" in lowered:
            return [
                self._selector_step("fill", "username field", "demo@example.com"),
                self._selector_step("fill", "password field", "password123"),
                self._selector_step("click", "login button", ""),
                self._selector_step("verify", "dashboard", ""),
            ]

        clauses = [segment.strip() for segment in re.split(r"\bthen\b|\band\b|,", lowered) if segment.strip()]
        steps = []
        for clause in clauses:
            keyword = self._keyword_for_clause(clause)
            noun = self._noun_for_clause(clause)
            value = self._quoted_value(clause)
            if keyword == "navigate":
                steps.append({"keyword": "navigate", "field_name": f"{self._slugify(noun)}_page", "selector": self.locator.current_url, "value": self.locator.current_url})
                continue
            steps.append(self._selector_step(keyword, noun, value))
        return steps or [self._selector_step("click", story, "")]

    def _selector_step(self, keyword: str, noun: str, value: str) -> Dict[str, str]:
        payload = self.locator.assist(noun, validate=False)
        primary = payload["elements"][0]["primary_locator"] if payload.get("elements") else {}
        field_name = self._field_name_for(keyword, noun)
        selector = str(primary.get("selector", f'[data-smart-locator="{self._slugify(noun)}"]'))
        return {"keyword": keyword, "field_name": field_name, "selector": selector, "value": value}

    def _keyword_for_clause(self, clause: str) -> str:
        mapping = {
            "navigate": "navigate",
            "open": "navigate",
            "click": "click",
            "press": "click",
            "fill": "fill",
            "type": "type",
            "enter": "type",
            "verify": "verify",
            "assert": "assert",
        }
        for token, keyword in mapping.items():
            if token in clause:
                return keyword
        return "click"

    def _noun_for_clause(self, clause: str) -> str:
        cleaned = re.sub(r"\b(navigate|open|click|press|fill|type|enter|verify|assert|with|valid|the|a|an)\b", " ", clause)
        result = " ".join(cleaned.split()).strip()
        return result or "target element"

    def _quoted_value(self, clause: str) -> str:
        match = re.search(r'"([^"]+)"', clause)
        if match:
            return match.group(1)
        return "sample value"

    def _field_name_for(self, keyword: str, noun: str) -> str:
        base = self._slugify(noun)
        if keyword in {"fill", "type"} and not base.endswith("_field"):
            return f"{base}_field"
        if keyword == "click" and not base.endswith("_button"):
            return f"{base}_button"
        return base or "target_element"

    def _extract_story(self, query: str) -> str:
        return re.sub(r"^create\s+", "", query, flags=re.IGNORECASE).strip()

    def _extract_page_name(self, text: str) -> str:
        lowered = text.lower()
        if "login" in lowered:
            return "login"
        match = re.search(r"(?:create|generate)\s+([a-z0-9 _-]+?)\s+(?:page|test)\b", lowered)
        if match:
            return self._slugify(match.group(1))
        return self.context.active_page or "login"

    def _extract_field_name(self, text: str) -> str:
        lowered = text.lower()
        match = re.search(r"add\s+([a-z0-9 _-]+?)\s+field", lowered)
        if match:
            base = self._slugify(match.group(1))
        else:
            base = self._slugify(lowered.replace("add", "").replace("field", ""))
        return base if base.endswith("_field") else f"{base}_field"

    def _class_name(self, page_name: str) -> str:
        return "".join(part.title() for part in page_name.split("_")) + "Page"

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "generated"

    def _detect_intent(self, query: str) -> str:
        lowered = query.strip().lower()
        if lowered == "run tests":
            return "run_tests"
        if lowered == "show project structure":
            return "show_project_structure"
        if lowered.startswith("create ") and " page" in lowered:
            return "create_page"
        if lowered.startswith("add ") and " field" in lowered:
            return "add_field"
        if lowered.startswith("generate ") and " test" in lowered:
            return "generate_test"
        if lowered.startswith("create "):
            return "create_story"
        return "selector"

    def _load_context(self) -> None:
        config = discover_config(self.workspace)
        if config is None:
            return
        self.context.project_root = config.project_root
        self.context.framework = config.framework
        self.context.files_generated = list(config.generated_files)

    def _require_generator(self) -> ProjectGenerator:
        if self.context.project_root is None:
            raise RuntimeError("No generated project is active. Run `smart-locator init` first.")
        def decision_callback(path: Path) -> str:
            answer = input(f"{path} exists. Choose Merge / Overwrite / Skip: ").strip().lower()
            mapping = {"merge": "merge", "overwrite": "overwrite", "skip": "skip"}
            return mapping.get(answer, "skip")

        return ProjectGenerator.from_project_root(
            self.context.project_root,
            file_manager=FileManager(self.context.project_root, decision_callback=decision_callback),
        )

    def _confirm(self, explanation: str) -> bool:
        answer = input(f"{explanation}\nProceed? [y/N]: ").strip().lower()
        return answer in {"y", "yes"}

    def _remember_operations(self, operations) -> None:
        for operation in operations:
            self.context.files_generated.append(str(operation.path))

    def _format_result(self, explanation: str, operations) -> str:
        payload = [
            {
                "status": operation.status,
                "path": str(operation.path),
                "message": operation.message,
            }
            for operation in operations
        ]
        return f"{explanation}\n{format_operation_results(payload)}"


def answer_query(locator, query: str, *, validate: bool = True) -> str:
    assistant = SmartAssistant(locator, Path.cwd())
    if validate and assistant._detect_intent(query) == "selector":
        return assistant._selector_reply(query)
    return assistant.answer(query, interactive=False)


def run_chat(locator) -> int:
    assistant = SmartAssistant(locator, Path.cwd())
    print("Tester assistant is ready. Ask for selectors or project actions like 'create login page'. Type 'exit' to leave.")
    while True:
        try:
            query = input("tester> ").strip()
        except EOFError:
            print()
            return 0
        if not query:
            print("Please describe the element or action you want.")
            continue
        if query.lower() in EXIT_WORDS:
            print("Closing tester assistant.")
            return 0
        try:
            print(assistant.answer(query, interactive=True))
        except RuntimeError as exc:
            print(str(exc))
        print()
