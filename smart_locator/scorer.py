"""Locator ranking heuristics."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .models import LocatorCandidate


DYNAMIC_ID_RE = re.compile(r"[a-z]+-[a-f0-9]{4,}", re.IGNORECASE)
LONG_DIGITS_RE = re.compile(r"\d{5,}")
CSS_IN_JS_RE = re.compile(r"(?:^| )(?:sc-[a-z0-9]+|css-[a-z0-9]+|Mui[A-Za-z0-9-]+-root-\d+|_[0-9]{3,})(?: |$)")
POSITIONAL_XPATH_RE = re.compile(r"\[\d+\]")


def _clamp(score: int) -> int:
    return max(0, min(100, score))


def _tier(score: int) -> str:
    if score >= 85:
        return "BEST"
    if score >= 50:
        return "GOOD"
    return "AVOID"


def build_locator_candidates(element: Dict[str, object]) -> List[LocatorCandidate]:
    attrs: Dict[str, str] = dict(element.get("attributes", {}))
    tag = str(element.get("tag", ""))
    text = str(element.get("text", "")).strip()
    css_path = str(element.get("css_path", ""))

    candidates: List[LocatorCandidate] = []

    if attrs.get("data-testid"):
        candidates.append(_candidate("data-testid", attrs["data-testid"], 98, "Explicit test hook intended to stay stable."))
    if attrs.get("aria-label"):
        candidates.append(_candidate("aria-label", attrs["aria-label"], 95, "Accessible name is descriptive and usually durable."))
    if attrs.get("role"):
        candidates.append(_candidate("role", attrs["role"], 90, "Semantic role aligns with accessibility-first locator strategy."))
    if attrs.get("name"):
        candidates.append(_candidate("name", attrs["name"], 84, "Form control names are usually stable across layout changes."))
    if attrs.get("id"):
        candidates.append(_score_id(attrs["id"]))
    if text:
        xpath = f"//{tag}[normalize-space()={_xpath_literal(text)}]"
        candidates.append(_candidate("xpath", xpath, 72, "Visible text is readable but can change with copy updates."))
    if attrs.get("href"):
        candidates.append(_candidate("css", f'{tag}[href="{attrs["href"]}"]', 70, "Href-based selector can be stable for navigation links."))
    if attrs.get("class"):
        candidates.append(_score_class(tag, attrs["class"]))
    if css_path:
        candidates.append(_score_css_path(css_path))

    candidates.append(_score_xpath(f"//body//{tag}[1]"))
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def _candidate(strategy: str, value: str, score: int, reason: str, warning: Optional[str] = None) -> LocatorCandidate:
    final_score = _clamp(score)
    return LocatorCandidate(
        strategy=strategy,
        value=value,
        score=final_score,
        reason=reason,
        warning=warning,
        tier=_tier(final_score),
    )


def _score_id(value: str) -> LocatorCandidate:
    score = 80
    reason = "ID selectors are concise and efficient when they are human-chosen."
    warning = None
    if DYNAMIC_ID_RE.search(value) or LONG_DIGITS_RE.search(value) or (len(value) >= 6 and sum(ch.isdigit() for ch in value) >= 3):
        score = 15
        reason = "ID looks generated and is likely to change between deployments."
        warning = "dynamic — will break on redeploy"
    return _candidate("id", value, score, reason, warning)


def _score_class(tag: str, class_value: str) -> LocatorCandidate:
    primary = class_value.split()[0]
    score = 55
    reason = "Class-based CSS can work, but styling hooks are often brittle."
    warning = None
    if CSS_IN_JS_RE.search(class_value):
        score = 18
        reason = "Framework-generated class name is unstable and likely to churn."
        warning = "generated class — brittle CSS hook"
    return _candidate("css", f"{tag}.{primary}", score, reason, warning)


def _score_css_path(value: str) -> LocatorCandidate:
    score = 42 if ":nth-of-type" in value else 62
    reason = "Structural CSS depends on DOM shape and may drift over time."
    return _candidate("css", value, score, reason)


def _score_xpath(value: str) -> LocatorCandidate:
    if POSITIONAL_XPATH_RE.search(value):
        return _candidate("xpath", value, 20, "position-based — breaks on DOM change")
    return _candidate("xpath", value, 60, "XPath is flexible but can become verbose and layout-coupled.")


def _xpath_literal(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'
