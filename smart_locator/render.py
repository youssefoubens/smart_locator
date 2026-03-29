"""Formatting helpers for terminal output and code generation."""

from __future__ import annotations

import keyword
import re
from typing import Dict, List, Sequence


ANSI = {
    "BEST": "\033[92m",
    "GOOD": "\033[93m",
    "AVOID": "\033[91m",
    "reset": "\033[0m",
}


def score_bar(score: int, width: int = 10) -> str:
    filled = round((score / 100) * width)
    return "#" * filled + "-" * (width - filled)


def format_suggestions(elements: List[Dict[str, object]]) -> str:
    lines = []
    if not elements:
        return "No relevant elements found."

    lines.append(_format_header())
    for element in elements:
        label = element["label"]
        for locator in element["locators"]:
            tier = locator["tier"]
            color = ANSI.get(tier, "")
            reason = _truncate(locator["reason"], 40)
            value = _truncate(locator["value"], 34)
            lines.append(
                f"{color}{tier:<5}{ANSI['reset']} "
                f"{_truncate(label, 18):<18} "
                f"{locator['strategy']:<12} "
                f"{value:<34} "
                f"{locator['score']:>3} "
                f"{score_bar(locator['score'], width=8):<8} "
                f"{reason}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def format_tester_workspace(payload: Dict[str, object]) -> str:
    elements = payload.get("elements", [])
    query = str(payload.get("query", "")).strip()
    url = str(payload.get("url", "")).strip()
    if not elements:
        return "\n".join(
            [
                "Tester Workspace",
                f"Query: {query or '(empty)'}",
                f"URL: {url or '(unknown)'}",
                "",
                "No relevant elements found.",
            ]
        )

    lines = [
        "Tester Workspace",
        f"Query: {query}",
        f"URL: {url}",
        "",
    ]
    for index, element in enumerate(elements, start=1):
        primary = element.get("primary_locator") or {}
        lines.extend(
            [
                f"{index}. {element['label']}",
                f"   Best match: {primary.get('strategy', '-')} | score={primary.get('score', '-')} | {primary.get('tier', '-')}",
                f"   Exact selector: {primary.get('exact', '-')}",
            ]
        )
        validation = primary.get("validation")
        if validation:
            lines.append(f"   Validation: {validation}")
        frame_path = element.get("frame_path") or []
        shadow_path = element.get("shadow_path") or []
        if frame_path:
            lines.append(f"   Frame path: {' > '.join(frame_path)}")
        if shadow_path:
            lines.append(f"   Shadow path: {' > '.join(shadow_path)}")
        reason = primary.get("reason")
        if reason:
            lines.append(f"   Why: {reason}")
        alternatives = [
            f"{locator['strategy']}={locator.get('selector') or locator.get('value', '-')}"
            for locator in element.get("locators", [])[1:]
        ]
        if alternatives:
            lines.append(f"   Fallbacks: {' | '.join(alternatives)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_chat_reply(payload: Dict[str, object]) -> str:
    elements = payload.get("elements", [])
    query = str(payload.get("query", "")).strip()
    if not elements:
        return f'I could not find a confident selector for "{query}". Try describing the element with visible text, role, or form label.'

    primary_element = elements[0]
    primary_locator = primary_element.get("primary_locator") or {}
    lines = [
        f'Best selector for "{query}":',
        f'- Element: {primary_element["label"]}',
        f'- Exact selector: {primary_locator.get("exact", "-")}',
        f'- Strategy: {primary_locator.get("strategy", "-")} (score={primary_locator.get("score", "-")}, tier={primary_locator.get("tier", "-")})',
    ]
    validation = primary_locator.get("validation")
    if validation:
        lines.append(f"- Validation: {validation}")
    reason = primary_locator.get("reason")
    if reason:
        lines.append(f"- Why this one: {reason}")

    alternatives = primary_element.get("locators", [])[1:3]
    if alternatives:
        lines.append("- Fallbacks:")
        for locator in alternatives:
            lines.append(f"  {locator['exact']}")
    return "\n".join(lines)


def format_operation_results(operations: Sequence[Dict[str, str]]) -> str:
    status_map = {
        "CREATE": "[\u2713 CREATE]",
        "MERGE": "[~ MERGE ]",
        "OVERWRITE": "[~ MERGE ]",
        "SKIP": "[! SKIP  ]",
        "ERROR": "[\u2717 ERROR ]",
    }
    lines = []
    for operation in operations:
        status = status_map.get(operation["status"], f"[{operation['status']}]")
        line = f"{status}   {operation['path']}"
        if operation.get("message"):
            line = f"{line}  {operation['message']}"
        lines.append(line)
    return "\n".join(lines)


def _format_header() -> str:
    return f"{'Tier':<5} {'Element':<18} {'Strategy':<12} {'Value':<34} {'Scr':>3} {'Bar':<8} Reason"


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: width - 3] + "..."


def snake_case(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_") or "element"
    if keyword.iskeyword(slug):
        slug = f"{slug}_field"
    return slug


def render_python_snippets(elements: List[Dict[str, object]]) -> str:
    lines = ["from selenium.webdriver.common.by import By", ""]
    for element in elements:
        locator = element["locators"][0]
        var_name = snake_case(element["label"])
        by_name = strategy_to_by(locator["strategy"])
        value = locator["value"]
        if locator["strategy"] == "aria-label":
            value = f'[aria-label="{value}"]'
        elif locator["strategy"] == "data-testid":
            value = f'[data-testid="{value}"]'
        elif locator["strategy"] == "role":
            value = f'[role="{value}"]'
        lines.append(f"{var_name} = driver.find_element(By.{by_name}, {value!r})  # score={locator['score']}")
    return "\n".join(lines)


def render_page_object(class_name: str, elements: List[Dict[str, object]]) -> str:
    lines = [
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.support import expected_conditions as EC",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "",
        f"class {class_name}:",
        "    def __init__(self, driver, timeout=10):",
        "        self.driver = driver",
        "        self.wait = WebDriverWait(driver, timeout)",
        "",
    ]
    for element in elements:
        locator = element["locators"][0]
        const_name = snake_case(element["label"]).upper()
        by_name = strategy_to_by(locator["strategy"])
        value = locator["value"]
        if locator["strategy"] == "aria-label":
            value = f'[aria-label="{value}"]'
        elif locator["strategy"] == "data-testid":
            value = f'[data-testid="{value}"]'
        elif locator["strategy"] == "role":
            value = f'[role="{value}"]'
        lines.append(f"    {const_name} = (By.{by_name}, {value!r})  # score={locator['score']}")
    if elements:
        lines.append("")
    for element in elements:
        const_name = snake_case(element["label"]).upper()
        method_name = f"get_{snake_case(element['label'])}"
        lines.extend(
            [
                f"    def {method_name}(self):",
                f"        return self.wait.until(EC.element_to_be_clickable(self.{const_name}))",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def strategy_to_by(strategy: str) -> str:
    mapping = {
        "id": "ID",
        "name": "NAME",
        "css": "CSS_SELECTOR",
        "xpath": "XPATH",
        "aria-label": "CSS_SELECTOR",
        "data-testid": "CSS_SELECTOR",
        "role": "CSS_SELECTOR",
    }
    return mapping.get(strategy, "CSS_SELECTOR")
