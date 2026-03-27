"""Primary SmartLocator implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from selenium.webdriver.common.by import By

from .cache import SmartLocatorCache
from .models import LocatorCandidate
from .openai_client import interpret_query, resolve_api_key
from .parser import parse_dom, truncate_context
from .render import format_suggestions, render_page_object, render_python_snippets
from .scorer import build_locator_candidates


class SmartLocator:
    def __init__(
        self,
        driver,
        *,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        use_cache: bool = True,
        default_timeout: int = 10,
        cache_path=None,
    ) -> None:
        if driver is None:
            raise ValueError("SmartLocator requires a live Selenium WebDriver instance.")
        self.driver = driver
        self._api_key = api_key
        self.model = model
        self.use_cache = use_cache
        self.default_timeout = default_timeout
        self.cache = SmartLocatorCache(cache_path)

    @property
    def current_url(self) -> str:
        return getattr(self.driver, "current_url", "") or ""

    def suggest(self, query: str, *, output: str = "table") -> Any:
        payload = self._get_or_build_payload(query)
        if output == "dict":
            return payload
        return format_suggestions(payload["elements"])

    def generate_code(self, query: str) -> str:
        payload = self._get_or_build_payload(query)
        return render_python_snippets(payload["elements"])

    def generate_page_object(self, class_name: str, query: str) -> str:
        payload = self._get_or_build_payload(query)
        return render_page_object(class_name, payload["elements"])

    def invalidate_cache(self, query: str) -> None:
        self.cache.invalidate(self.current_url, query)

    def clear_cache(self) -> int:
        return self.cache.clear()

    def validate(self, query: str) -> Dict[str, object]:
        payload = self._get_or_build_payload(query)
        for element in payload["elements"]:
            for locator in element["locators"]:
                by, selector = self._locator_to_selenium(locator["strategy"], locator["value"])
                matches = self.driver.find_elements(by, selector)
                count = len(matches)
                if count == 1:
                    locator["validation"] = "FOUND"
                elif count > 1:
                    locator["validation"] = f"MULTIPLE ({count})"
                    locator["score"] = min(locator["score"], 40)
                    locator["reason"] = f"ambiguous — {count} elements matched"
                else:
                    locator["validation"] = "NOT FOUND"
                    locator["score"] = min(locator["score"], 10)
            element["locators"].sort(key=lambda item: item["score"], reverse=True)
        return payload

    def repair(self, by: str, value: str, description: str) -> Tuple[Tuple[str, str], str]:
        payload = self._get_or_build_payload(description, fresh=True)
        best = payload["elements"][0]["locators"][0]
        replacement = self._locator_to_selenium(best["strategy"], best["value"])
        diff = f'OLD: {by} "{value}" -> NEW: {replacement[0]} "{replacement[1]}" (score={best["score"]})'
        return replacement, diff

    def suggest_wait(self, query: str) -> Dict[str, object]:
        payload = self._get_or_build_payload(query)
        waits = []
        for element in payload["elements"]:
            top = element["locators"][0]
            label = element["label"]
            tag = element.get("tag", "")
            condition = "visibility_of_element_located"
            timeout = self.default_timeout
            if tag == "button":
                condition = "element_to_be_clickable"
                timeout = 10
            if "checkbox" in label.lower():
                condition = "element_to_be_selected"
            if "toast" in label.lower() or "snackbar" in label.lower():
                timeout = 5
            if "page" in label.lower() or "redirect" in label.lower():
                timeout = 15
            by, selector = self._locator_to_selenium(top["strategy"], top["value"])
            waits.append(
                {
                    "label": label,
                    "condition": condition,
                    "timeout": timeout,
                    "snippet": f"WebDriverWait(driver, {timeout}).until(EC.{condition}(({by}, {selector!r})))",
                }
            )
        return {"elements": waits}

    def _get_or_build_payload(self, query: str, *, fresh: bool = False) -> Dict[str, object]:
        url = self.current_url
        if self.use_cache and not fresh:
            cached = self.cache.get(url, query)
            if cached:
                return cached

        elements = truncate_context(parse_dom(self.driver))
        matches = interpret_query(
            api_key=resolve_api_key(self._api_key),
            model=self.model,
            url=url,
            query=query,
            elements=elements,
        )
        payload = {"elements": self._rank_elements(elements, query, matches)}
        if self.use_cache:
            self.cache.set(url, query, payload)
        return payload

    def _rank_elements(
        self,
        elements: List[Dict[str, object]],
        query: str,
        matches: Optional[List[Dict[str, object]]] = None,
    ) -> List[Dict[str, object]]:
        match_lookup = {item["index"]: item.get("reason", "") for item in (matches or [])}
        ranked = []
        for index, element in enumerate(elements, start=1):
            locators = build_locator_candidates(element)
            relevance_score = self._relevance_score(query, element)
            if index in match_lookup:
                for locator in locators:
                    locator.score = min(locator.score + 5, 100)
                    if locator.score >= 85:
                        locator.tier = "BEST"
                    elif locator.score >= 50:
                        locator.tier = "GOOD"
                    else:
                        locator.tier = "AVOID"
                    locator.reason = match_lookup[index] or locator.reason
            elif relevance_score > 0:
                for locator in locators:
                    locator.score = min(locator.score + min(relevance_score * 5, 15), 100)
                    if locator.score >= 85:
                        locator.tier = "BEST"
                    elif locator.score >= 50:
                        locator.tier = "GOOD"
                    else:
                        locator.tier = "AVOID"
                    locator.reason = f"Matches query keywords ({relevance_score} hit{'s' if relevance_score != 1 else ''})."
            ranked.append(
                {
                    "label": self._label_for_element(element),
                    "tag": element.get("tag", ""),
                    "locators": [self._serialize_locator(locator) for locator in locators[:3]],
                    "frame_path": element.get("frame_path", []),
                    "shadow_path": element.get("shadow_path", []),
                    "relevance": relevance_score + (100 if index in match_lookup else 0),
                }
            )
        ranked.sort(
            key=lambda item: (
                item.get("relevance", 0),
                item["locators"][0]["score"] if item["locators"] else 0,
            ),
            reverse=True,
        )
        filtered = [item for item in ranked if item.get("relevance", 0) > 0]
        selected = filtered or ranked
        return selected[:5]

    def _label_for_element(self, element: Dict[str, object]) -> str:
        attrs = dict(element.get("attributes", {}))
        for key in ("aria-label", "data-testid", "name", "id", "placeholder"):
            if attrs.get(key):
                return attrs[key]
        text = str(element.get("text", "")).strip()
        return text or str(element.get("tag", "element"))

    def _serialize_locator(self, locator: LocatorCandidate) -> Dict[str, object]:
        result = {
            "strategy": locator.strategy,
            "value": locator.value,
            "score": locator.score,
            "reason": locator.reason,
            "tier": locator.tier,
        }
        if locator.warning:
            result["warning"] = locator.warning
        return result

    def _relevance_score(self, query: str, element: Dict[str, object]) -> int:
        tokens = [token for token in self._tokenize(query) if token not in {"the", "a", "an", "form", "field", "button"}]
        if not tokens:
            return 0
        attrs = dict(element.get("attributes", {}))
        haystack_parts = [
            str(element.get("tag", "")),
            str(element.get("text", "")),
            str((element.get("parent") or {}).get("text", "")),
            " ".join(str(value) for value in attrs.values()),
        ]
        haystack = " ".join(haystack_parts).lower()
        score = 0
        for token in tokens:
            if token in haystack:
                score += 1
        if "login" in tokens and attrs.get("type") == "password":
            score += 1
        if "login" in tokens and attrs.get("name") in {"username", "password", "login"}:
            score += 1
        return score

    def _tokenize(self, value: str) -> List[str]:
        return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if token]

    def _locator_to_selenium(self, strategy: str, value: str) -> Tuple[str, str]:
        if strategy == "id":
            return (By.ID, value)
        if strategy == "name":
            return (By.NAME, value)
        if strategy == "xpath":
            return (By.XPATH, value)
        if strategy == "aria-label":
            return (By.CSS_SELECTOR, f'[aria-label="{value}"]')
        if strategy == "data-testid":
            return (By.CSS_SELECTOR, f'[data-testid="{value}"]')
        if strategy == "role":
            return (By.CSS_SELECTOR, f'[role="{value}"]')
        return (By.CSS_SELECTOR, value)
