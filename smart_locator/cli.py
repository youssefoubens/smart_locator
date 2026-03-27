"""Command line interface for smart-locator."""

from __future__ import annotations

import argparse
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .core import SmartLocator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smart-locator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest = subparsers.add_parser("suggest")
    suggest.add_argument("--url", required=True)
    suggest.add_argument("--query", required=True)

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
        output = locator.generate_page_object(args.class_name, args.query)
        destination = Path(args.out)
        destination.write_text(output, encoding="utf-8")
        count = len(locator.suggest(args.query, output="dict")["elements"])
        print(f"Wrote {destination} with {count} elements.")
        return 0
    finally:
        driver.quit()
