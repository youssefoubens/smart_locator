"""OpenAI request wrapper."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from openai import OpenAI

from .errors import MissingAPIKeyError, SmartLocatorError


def resolve_api_key(api_key: Optional[str]) -> str:
    resolved = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved:
        raise MissingAPIKeyError(
            "OpenAI API key is missing. Pass api_key= to SmartLocator(...) or set OPENAI_API_KEY."
        )
    return resolved


def build_prompt(url: str, query: str, elements: List[Dict[str, object]]) -> str:
    lines = [
        "You are helping pick robust Selenium locators.",
        f"Page URL: {url}",
        f"User query: {query}",
        "Return JSON with shape {\"matches\": [{\"index\": 1, \"reason\": \"...\"}]} using 1-based indexes.",
        "Interactive elements:",
    ]
    for index, element in enumerate(elements, start=1):
        attrs = ", ".join(f"{key}={value!r}" for key, value in dict(element.get("attributes", {})).items())
        parent = element.get("parent") or {}
        parent_desc = ""
        if parent:
            parent_attrs = ", ".join(f"{key}={value!r}" for key, value in dict(parent.get("attributes", {})).items())
            parent_desc = f" | parent tag={parent.get('tag', '')!r} text={str(parent.get('text', ''))!r} attrs=[{parent_attrs}]"
        lines.append(
            f"{index}. tag={element.get('tag')!r} text={str(element.get('text', ''))!r} "
            f"attrs=[{attrs}]{parent_desc}"
        )
    return "\n".join(lines)[:24000]


def parse_match_response(content: str) -> List[Dict[str, object]]:
    """Parse the model response into a list of matches."""

    if not content.strip():
        return []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []
    matches = payload.get("matches", [])
    if not isinstance(matches, list):
        return []
    parsed: List[Dict[str, object]] = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int):
            continue
        parsed.append({"index": index, "reason": str(item.get("reason", "")).strip()})
    return parsed


def interpret_query(
    *,
    api_key: str,
    model: str,
    url: str,
    query: str,
    elements: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Select the elements that best match the user's intent and explain why briefly.",
                },
                {
                    "role": "user",
                    "content": build_prompt(url=url, query=query, elements=elements),
                },
            ],
        )
        message = response.choices[0].message.content
        return parse_match_response(message or "")
    except Exception as exc:  # pragma: no cover
        raise SmartLocatorError(f"OpenAI request failed: {exc}") from exc
