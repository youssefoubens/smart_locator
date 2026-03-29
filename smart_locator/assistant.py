"""Tester-oriented interactive assistant utilities."""

from __future__ import annotations

from .render import format_chat_reply, format_tester_workspace


EXIT_WORDS = {"exit", "quit", "q"}


def answer_query(locator, query: str, *, validate: bool = True) -> str:
    payload = locator.assist(query, validate=validate)
    workspace = format_tester_workspace(payload)
    reply = format_chat_reply(payload)
    return f"{workspace}\n\nChatbot\n{reply}".strip()


def run_chat(locator) -> int:
    print("Tester assistant is ready. Ask for a selector like 'login button' or type 'exit'.")
    while True:
        try:
            query = input("tester> ").strip()
        except EOFError:
            print()
            return 0
        if not query:
            print("Please describe the element you want to target.")
            continue
        if query.lower() in EXIT_WORDS:
            print("Closing tester assistant.")
            return 0
        print(answer_query(locator, query))
        print()
