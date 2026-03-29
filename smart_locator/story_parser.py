"""Semantic story parsing for scenario generation."""

from __future__ import annotations

from typing import Callable, Dict, Optional


INTENT_MAP = {
    "log in|login|sign in|signin|authenticate": {
        "elements": ["username_field", "password_field", "submit_button"],
        "actions": {"username_field": "fill", "password_field": "fill", "submit_button": "click"},
    },
    "register|sign up|signup|create account": {
        "elements": ["username_field", "email_field", "password_field", "confirm_password_field", "submit_button"],
        "actions": {
            "username_field": "fill",
            "email_field": "fill",
            "password_field": "fill",
            "confirm_password_field": "fill",
            "submit_button": "click",
        },
    },
    "logout|log out|sign out": {
        "elements": ["logout_button"],
        "actions": {"logout_button": "click"},
    },
    "search": {
        "elements": ["search_input", "search_button"],
        "actions": {"search_input": "fill", "search_button": "click"},
    },
    "checkout|place order|complete purchase": {
        "elements": ["first_name_field", "last_name_field", "address_field", "card_number_field", "submit_button"],
        "actions": {
            "first_name_field": "fill",
            "last_name_field": "fill",
            "address_field": "fill",
            "card_number_field": "fill",
            "submit_button": "click",
        },
    },
    "add to cart|add item": {
        "elements": ["add_to_cart_button"],
        "actions": {"add_to_cart_button": "click"},
    },
    "verify|assert|check|confirm|see|should": {
        "elements": ["success_message"],
        "actions": {"success_message": "assert_visible"},
    },
    "navigate|go to|open|visit": {
        "elements": [],
        "actions": {"_page": "goto"},
    },
    "upload|attach file": {
        "elements": ["file_input"],
        "actions": {"file_input": "upload"},
    },
    "delete|remove": {
        "elements": ["delete_button", "confirm_button"],
        "actions": {"delete_button": "click", "confirm_button": "click"},
    },
    "edit|update|modify": {
        "elements": ["edit_button", "save_button"],
        "actions": {"edit_button": "click", "save_button": "click"},
    },
    "filter|sort": {
        "elements": ["filter_dropdown", "apply_button"],
        "actions": {"filter_dropdown": "select", "apply_button": "click"},
    },
}

ASSERTION_KEYWORDS = ["verify", "assert", "check", "confirm", "see", "should", "expect", "successful", "successfully"]


def detect_intent(story: str) -> Dict[str, str]:
    story_lower = story.lower()
    matched_elements: Dict[str, str] = {}
    for pattern, config in INTENT_MAP.items():
        keywords = pattern.split("|")
        if any(keyword in story_lower for keyword in keywords):
            matched_elements.update(config["actions"])
    if any(keyword in story_lower for keyword in ASSERTION_KEYWORDS):
        matched_elements["success_message"] = "assert_visible"
    return matched_elements


def parse_story(
    story: str,
    *,
    llm_fallback: Optional[Callable[[str], Dict[str, str]]] = None,
) -> Dict[str, str]:
    result = detect_intent(story)
    if result:
        return result
    if llm_fallback is not None:
        return llm_fallback(story)
    return {}
