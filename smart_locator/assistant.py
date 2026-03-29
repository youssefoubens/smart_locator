"""Tester-oriented interactive assistant utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .config import discover_config
from .errors import SmartLocatorError
from .file_manager import FileManager
from .project_generator import ProjectGenerator
from .render import format_chat_reply, format_operation_results, format_tester_workspace
from .story_parser import parse_story
from .test_runner import run_tests


EXIT_WORDS = {"exit", "quit", "q"}


@dataclass
class SessionContext:
    """Conversation state for the tester assistant."""

    project_root: Optional[Path] = None
    framework: Optional[str] = None
    active_page: Optional[str] = None
    files_generated: List[str] = field(default_factory=list)


@dataclass
class GuidedWorkflow:
    """Step-by-step scenario-building workflow state."""

    scenario: str
    suggested_page: str
    analyzed_steps: List[Dict[str, str]]
    analyzed_elements: List[str]
    analyzed_actions: List[str]
    stage: str = "create_page"
    create_page: bool = True
    page_name: Optional[str] = None
    selected_elements: List[str] = field(default_factory=list)
    use_pom: bool = True
    add_selectors: bool = True
    selector_mode: str = "auto"
    file_strategy: str = "ask"
    resolved_selectors: Dict[str, str] = field(default_factory=dict)
    selector_overrides: Dict[str, str] = field(default_factory=dict)


class SmartAssistant:
    """Intent-aware assistant for selectors and project automation."""

    def __init__(self, locator, workspace: Path) -> None:
        self.locator = locator
        self.workspace = workspace
        self.context = SessionContext()
        self.workflow: Optional[GuidedWorkflow] = None
        self._load_context()

    def answer(self, query: str, *, interactive: bool) -> str:
        clean_query = query.strip()
        if self.workflow is not None:
            return self._continue_workflow(clean_query)

        intent = self._detect_intent(clean_query)
        if intent == "selector":
            return self._selector_reply(clean_query)
        if intent == "show_project_structure":
            return self._show_project_structure()
        if intent == "run_tests":
            return self._run_tests()
        if intent == "start_workflow":
            if not interactive:
                return "Start `smart-locator assist --url <url>` and share the scenario there so I can guide you step by step."
            return self._start_workflow(clean_query)
        if not interactive:
            return "This action changes project files. Start `smart-locator assist --url <url>` and confirm the action in chat."
        return self._handle_direct_action(intent, clean_query)

    def _selector_reply(self, query: str) -> str:
        try:
            payload = self.locator.assist(query, validate=True)
        except SmartLocatorError as exc:
            return (
                f"I could not reach the selector service for `{query}`. "
                f"Reason: {exc}. You can still continue with guided generation using a scenario like "
                "`As a user, I want to log in successfully using valid credentials.`"
            )
        workspace = format_tester_workspace(payload)
        reply = format_chat_reply(payload)
        recommended = self._best_selector_for(query)
        recommendation = f"Automation recommendation: `{recommended}`"
        return f"{workspace}\n\nChatbot\n{reply}\n{recommendation}".strip()

    def _handle_direct_action(self, intent: str, query: str) -> str:
        if intent == "create_page":
            return self._create_page(self._extract_page_name(query))
        if intent == "add_field":
            return self._add_field(self._extract_field_name(query))
        if intent == "generate_test":
            page_name = self.context.active_page or self._extract_page_name(query)
            return self._generate_test(page_name)
        if intent == "create_story":
            return self._start_workflow(self._extract_story(query))
        return self._selector_reply(query)

    def _start_workflow(self, scenario: str) -> str:
        if self.context.project_root is None:
            return "No generated project is active. Run `smart-locator init`, then start the assistant from that project folder."
        story = self._extract_story(scenario)
        steps = self._story_steps(story)
        elements = []
        actions = []
        for step in steps:
            actions.append(step["keyword"])
            if step["field_name"] not in elements:
                elements.append(step["field_name"])
        page_name = self._extract_page_name(story)
        self.workflow = GuidedWorkflow(
            scenario=story,
            suggested_page=page_name,
            analyzed_steps=steps,
            analyzed_elements=elements,
            analyzed_actions=actions,
        )
        return (
            "Scenario analysis\n"
            f"- Suggested page: `{page_name}`\n"
            f"- Actions: {', '.join(actions)}\n"
            f"- Elements: {', '.join(elements)}\n"
            "Do you want to create a new page object for this? Reply `yes` or `no`."
        )

    def _continue_workflow(self, query: str) -> str:
        assert self.workflow is not None
        lowered = query.lower()

        if self.workflow.stage == "create_page":
            self.workflow.create_page = self._is_yes(query)
            self.workflow.stage = "page_name"
            return f"What is the name of the page? Press Enter meaningfully by replying with a name, or use `{self.workflow.suggested_page}`."

        if self.workflow.stage == "page_name":
            self.workflow.page_name = self._slugify(query or self.workflow.suggested_page)
            self.workflow.stage = "elements"
            suggested = ", ".join(self.workflow.analyzed_elements)
            return (
                f"Which elements should be included? Suggested: {suggested}. "
                "Reply with comma-separated names or `suggested`."
            )

        if self.workflow.stage == "elements":
            if lowered == "suggested":
                self.workflow.selected_elements = list(self.workflow.analyzed_elements)
            else:
                self.workflow.selected_elements = [
                    self._slugify(item) for item in query.split(",") if self._slugify(item)
                ] or list(self.workflow.analyzed_elements)
            self.workflow.resolved_selectors = self._resolve_selectors(self.workflow.selected_elements)
            self.workflow.stage = "pom"
            return "Do you want to use POM structure? Reply `yes` or `no`."

        if self.workflow.stage == "pom":
            self.workflow.use_pom = self._is_yes(query)
            self.workflow.stage = "selectors"
            return "Do you want to add selectors now? Reply `yes` or `no`."

        if self.workflow.stage == "selectors":
            self.workflow.add_selectors = self._is_yes(query)
            if not self.workflow.add_selectors:
                self.workflow.stage = "file_strategy"
                return "Before modifying files, choose a file strategy: `merge`, `overwrite`, or `ask`."
            self.workflow.stage = "selector_mode"
            selector_lines = "\n".join(
                f"- {field_name}: {selector}" for field_name, selector in self.workflow.resolved_selectors.items()
            )
            return (
                "I selected the best selectors automatically for the current elements:\n"
                f"{selector_lines}\n"
                "Do you want to keep them as-is (`auto`) or review and modify them (`manual`)?"
            )

        if self.workflow.stage == "selector_mode":
            self.workflow.selector_mode = "manual" if lowered == "manual" else "auto"
            if self.workflow.selector_mode == "manual":
                self.workflow.stage = "selector_review"
                return self._selector_review_prompt()
            self.workflow.stage = "file_strategy"
            return (
                "Great, I will add those selectors automatically during generation.\n"
                "Before modifying files, choose a file strategy: `merge`, `overwrite`, or `ask`."
            )

        if self.workflow.stage == "selector_review":
            if lowered != "accept":
                for part in query.split(","):
                    if "=" not in part:
                        continue
                    name, selector = part.split("=", 1)
                    key = self._slugify(name)
                    self.workflow.selector_overrides[key] = selector.strip()
            self.workflow.stage = "file_strategy"
            return "Before modifying files, choose a file strategy: `merge`, `overwrite`, or `ask`."

        if self.workflow.stage == "file_strategy":
            chosen = lowered if lowered in {"merge", "overwrite", "ask"} else "ask"
            self.workflow.file_strategy = chosen
            self.workflow.stage = "confirm"
            return self._workflow_summary()

        if self.workflow.stage == "confirm":
            if not self._is_yes(query):
                self.workflow = None
                return "Workflow canceled. Share another scenario whenever you want to start again."
            return self._execute_workflow()

        if self.workflow.stage == "done":
            self.workflow = None
            if lowered == "run tests":
                return self._run_tests()
            if "new" in lowered or "another" in lowered:
                return "Share the next user story or test scenario and I’ll guide you through it."
            if "edit" in lowered:
                return "Tell me what you want to change, for example `add remember me field` or `generate checkout test`."
            return "Your scenario is fully implemented. You can `run tests`, start another scenario, or edit an existing one."

        return "I lost the workflow state. Please share the scenario again."

    def _workflow_summary(self) -> str:
        assert self.workflow is not None
        selectors = "auto-generated" if self.workflow.selector_mode == "auto" else "manual confirmation"
        return (
            "Workflow summary\n"
            f"- Scenario: {self.workflow.scenario}\n"
            f"- Page: {self.workflow.page_name or self.workflow.suggested_page}\n"
            f"- Elements: {', '.join(self.workflow.selected_elements)}\n"
            f"- POM structure: {'yes' if self.workflow.use_pom else 'no'}\n"
            f"- Selectors: {'included' if self.workflow.add_selectors else 'skipped'} ({selectors})\n"
            f"- Resolved selectors: {self._selector_summary()}\n"
            f"- File strategy: {self.workflow.file_strategy}\n"
            "Do you want me to generate the page object and test now? Reply `yes` or `no`."
        )

    def _execute_workflow(self) -> str:
        assert self.workflow is not None
        generator = self._require_generator()
        page_name = self.workflow.page_name or self.workflow.suggested_page
        steps = self._workflow_steps(page_name)
        result = generator.generate_story(
            page_name=page_name,
            page_class_name=self._class_name(page_name),
            test_name=self._slugify(self.workflow.scenario),
            steps=steps,
            strategy=self.workflow.file_strategy,
        )
        self.context.active_page = page_name
        self._remember_operations(result.operations)
        self.workflow.stage = "done"
        return (
            f"{self._format_result('Your scenario is fully implemented.', result.operations)}\n"
            "Do you want to proceed to execution or start another scenario?"
        )

    def _workflow_steps(self, page_name: str) -> List[Dict[str, str]]:
        assert self.workflow is not None
        selected = set(self.workflow.selected_elements)
        final_steps = []
        for step in self.workflow.analyzed_steps:
            if step["field_name"] not in selected:
                continue
            item = dict(step)
            if self.workflow.add_selectors:
                item["selector"] = self.workflow.selector_overrides.get(
                    step["field_name"],
                    self.workflow.resolved_selectors.get(step["field_name"], self._best_selector_for(step["field_name"])),
                )
            final_steps.append(item)
        if not final_steps:
            for field_name in self.workflow.selected_elements:
                final_steps.append(
                    {
                        "keyword": "fill",
                        "field_name": field_name,
                        "selector": self.workflow.selector_overrides.get(
                            field_name,
                            self.workflow.resolved_selectors.get(field_name, self._best_selector_for(field_name)),
                        ),
                        "value": "sample value",
                    }
                )
        return final_steps

    def _selector_review_prompt(self) -> str:
        assert self.workflow is not None
        lines = [
            "Selector review",
            "Reply `accept` to keep these suggestions, or send overrides like `username_field=[name=\"username\"], login_button=button[type=\"submit\"]`.",
        ]
        for field_name in self.workflow.selected_elements:
            lines.append(f"- {field_name}: {self.workflow.resolved_selectors.get(field_name, self._best_selector_for(field_name))}")
        return "\n".join(lines)

    def _best_selector_for(self, description: str) -> str:
        try:
            payload = self.locator.assist(description.replace("_", " "), validate=False)
        except SmartLocatorError:
            return f'[data-smart-locator="{self._slugify(description)}"]'
        candidate = self._pick_best_locator(payload, description)
        if candidate is not None:
            return candidate
        return f'[data-smart-locator="{self._slugify(description)}"]'

    def _pick_best_locator(self, payload: Dict[str, object], description: str) -> Optional[str]:
        elements = payload.get("elements", [])
        tokens = self._meaningful_tokens(description)
        best_selector: Optional[str] = None
        best_score = -10**9
        for element in elements:
            label = str(element.get("label", "")).lower()
            for locator in element.get("locators", []):
                strategy = str(locator.get("strategy", ""))
                value = str(locator.get("value", locator.get("selector", "")))
                selector = self._framework_safe_selector(strategy, value)
                if selector is None:
                    continue
                score = self._selector_priority(strategy, selector)
                score += int(locator.get("score", 0))
                score += self._label_match_bonus(label, tokens)
                if strategy == "css" and ":nth-of-type" in selector:
                    score -= 80
                if "button" in tokens and any(word in label for word in ("login", "submit", "sign in")):
                    score += 20
                if "field" in tokens and any(word in label for word in ("user", "pass", "email", "name")):
                    score += 10
                if best_selector is None or score > best_score:
                    best_selector = selector
                    best_score = score
        return best_selector

    def _framework_safe_selector(self, strategy: str, value: str) -> Optional[str]:
        if not value:
            return None
        if strategy == "data-testid":
            return f'[data-testid="{value}"]'
        if strategy == "aria-label":
            return f'[aria-label="{value}"]'
        if strategy == "name":
            return f'[name="{value}"]'
        if strategy == "id":
            return f'#{value}'
        if strategy == "role":
            return f'[role="{value}"]'
        if strategy == "css":
            if ":nth-of-type" in value and "#" not in value and "[" not in value and "." not in value:
                return None
            return value
        return None

    def _selector_priority(self, strategy: str, selector: str) -> int:
        priorities = {
            "data-testid": 500,
            "aria-label": 450,
            "name": 430,
            "id": 420,
            "role": 390,
            "css": 320,
        }
        score = priorities.get(strategy, 0)
        if selector.startswith("#"):
            score += 10
        if "[name=" in selector:
            score += 20
        return score

    def _label_match_bonus(self, label: str, tokens: List[str]) -> int:
        score = 0
        for token in tokens:
            if token in label:
                score += 25
        return score

    def _meaningful_tokens(self, value: str) -> List[str]:
        tokens = [token for token in re.sub(r"[^a-z0-9]+", " ", value.lower()).split() if token]
        stop_words = {"a", "an", "the", "i", "want", "to", "using", "valid"}
        return [token for token in tokens if token not in stop_words]

    def _resolve_selectors(self, field_names: List[str]) -> Dict[str, str]:
        return {field_name: self._best_selector_for(field_name) for field_name in field_names}

    def _selector_summary(self) -> str:
        assert self.workflow is not None
        if not self.workflow.add_selectors:
            return "none"
        pairs = []
        for field_name in self.workflow.selected_elements:
            selector = self.workflow.selector_overrides.get(
                field_name,
                self.workflow.resolved_selectors.get(field_name, "-"),
            )
            pairs.append(f"{field_name}={selector}")
        return ", ".join(pairs)

    def _create_page(self, page_name: str) -> str:
        return self._start_workflow(f"create {page_name} page")

    def _add_field(self, field_name: str) -> str:
        generator = self._require_generator()
        page_name = self.context.active_page or "login"
        selector = self._best_selector_for(field_name)
        operation = generator.merge_locator(page_name=page_name, field_name=field_name, selector=selector, strategy="ask")
        self._remember_operations([operation])
        return self._format_result(f"I added `{field_name}` to `{page_name}` using selector `{selector}`.", [operation])

    def _generate_test(self, page_name: str) -> str:
        return self._start_workflow(f"create {page_name} test")

    def _run_tests(self) -> str:
        if self.context.project_root is None:
            return "No generated project is active yet. Run `smart-locator init` first."
        exit_code = run_tests(self.context.project_root)
        return (
            "Running your test suite...\n"
            "Use this command: smart-locator run tests\n"
            f"Finished running the `{self.context.framework}` suite with exit code {exit_code}."
        )

    def _show_project_structure(self) -> str:
        if self.context.project_root is None:
            return "No generated project is active yet. Run `smart-locator init` first."
        generator = self._require_generator()
        tree = generator.show_project_structure()
        return f"Project structure for `{self.context.framework}`:\n{tree}"

    def _story_steps(self, story: str) -> List[Dict[str, str]]:
        semantic_actions = parse_story(story, llm_fallback=self._llm_story_fallback)
        steps = []
        for field_name, action in semantic_actions.items():
            if action == "goto":
                steps.append(
                    {
                        "keyword": "goto",
                        "field_name": field_name,
                        "selector": self.locator.current_url,
                        "value": self.locator.current_url,
                    }
                )
                continue
            default_value = "sample_value"
            if field_name == "username_field":
                default_value = "demo@example.com"
            elif "password" in field_name:
                default_value = "password123"
            elif action == "select":
                default_value = "option1"
            elif action == "upload":
                default_value = "path/to/test_file.txt"
            elif action in {"click", "assert_visible"}:
                default_value = ""
            steps.append(
                {
                    "keyword": action,
                    "field_name": field_name,
                    "selector": self._best_selector_for(field_name),
                    "value": default_value,
                }
            )
        return steps or [self._selector_step("click", story, "")]

    def _selector_step(self, keyword: str, noun: str, value: str) -> Dict[str, str]:
        field_name = self._field_name_for(keyword, noun)
        selector = self._best_selector_for(field_name)
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
        if any(phrase in lowered for phrase in ("run test", "run tests", "execute test", "execute tests")):
            return "run_tests"
        if lowered == "show project structure":
            return "show_project_structure"
        if self._looks_like_story(lowered):
            return "start_workflow"
        if lowered.startswith("create ") and " page" in lowered:
            return "create_page"
        if lowered.startswith("add ") and " field" in lowered:
            return "add_field"
        if lowered.startswith("generate ") and " test" in lowered:
            return "generate_test"
        if lowered.startswith("create "):
            return "create_story"
        return "selector"

    def _looks_like_story(self, query: str) -> bool:
        return "as a " in query or "i want to" in query or query.startswith("scenario:")

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

    def _is_yes(self, value: str) -> bool:
        return value.strip().lower() in {"y", "yes", "true", "ok", "continue"}

    def _llm_story_fallback(self, story: str) -> Dict[str, str]:
        payload = self.locator.assist(story, validate=False)
        elements = payload.get("elements", [])
        if not elements:
            return {}
        actions: Dict[str, str] = {}
        for element in elements[:3]:
            label = str(element.get("label", "target")).lower()
            field_name = self._field_name_for("click", label)
            if "input" in label or "field" in label or "password" in label:
                field_name = self._field_name_for("fill", label)
                actions[field_name] = "fill"
                continue
            actions[field_name] = "click"
        return actions


def answer_query(locator, query: str, *, validate: bool = True) -> str:
    assistant = SmartAssistant(locator, Path.cwd())
    if validate and assistant._detect_intent(query) == "selector":
        return assistant._selector_reply(query)
    return assistant.answer(query, interactive=False)


def run_chat(locator) -> int:
    assistant = SmartAssistant(locator, Path.cwd())
    print(
        "Tester assistant is ready. Share a user story or use commands like `create login page`. "
        "Type `exit` to leave."
    )
    while True:
        try:
            query = input("tester> ").strip()
        except EOFError:
            print()
            return 0
        if not query:
            print("Please describe the scenario, selector, or action you want.")
            continue
        if query.lower() in EXIT_WORDS:
            print("Closing tester assistant.")
            return 0
        try:
            print(assistant.answer(query, interactive=True))
        except RuntimeError as exc:
            print(str(exc))
        print()
