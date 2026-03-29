"""Command line interface for smart-locator."""

from __future__ import annotations

import argparse
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .assistant import answer_query, run_chat
from .core import SmartLocator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smart-locator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest = subparsers.add_parser("suggest")
    suggest.add_argument("--url", required=True)
    suggest.add_argument("--query", required=True)

    assist = subparsers.add_parser("assist")
    assist.add_argument("--url", required=True)
    assist.add_argument("--query")

    generate = subparsers.add_parser("generate")
    generate.add_argument("--url", required=True)
    generate.add_argument("--query", required=True)
    generate.add_argument("--class", dest="class_name", required=True)
    generate.add_argument("--out", required=True)

    return parser


def _build_driver():
    options = Options()
    options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    driver = _build_driver()
    try:
        driver.get(args.url)
        locator = SmartLocator(driver)
        if args.command == "suggest":
            print(locator.suggest(args.query))
            return 0
        if args.command == "assist":
            if args.query:
                print(answer_query(locator, args.query))
                return 0
            return run_chat(locator)
        output = locator.generate_page_object(args.class_name, args.query)
        destination = Path(args.out)
        destination.write_text(output, encoding="utf-8")
        count = len(locator.suggest(args.query, output="dict")["elements"])
        print(f"Wrote {destination} with {count} elements.")
        return 0
    finally:
        driver.quit()
