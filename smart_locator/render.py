"""Formatting helpers for terminal output and code generation."""

from __future__ import annotations

import keyword
import re
from typing import Dict, List


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
