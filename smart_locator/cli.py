"""Command line interface for smart-locator."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .assistant import answer_query, run_chat
from .config import ProjectConfig, discover_config, save_config
from .core import SmartLocator
from .file_manager import FileManager
from .project_generator import ProjectGenerator
from .test_runner import run_tests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smart-locator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest = subparsers.add_parser("suggest")
    suggest.add_argument("--url", required=True)
    suggest.add_argument("--query", required=True)

    assist = subparsers.add_parser("assist")
    assist.add_argument("--url", required=True)
    assist.add_argument("--query")

    init = subparsers.add_parser("init")
    init.add_argument("--project-root")
    init.add_argument("--install", action="store_true")

    run = subparsers.add_parser("run")
    run_subparsers = run.add_subparsers(dest="run_target", required=True)
    run_subparsers.add_parser("tests")

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


def _prompt(text: str, *, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    response = input(f"{text}{suffix}: ").strip()
    return response or (default or "")


def _install_dependencies(project_root: Path) -> int:
    requirements = project_root / "requirements.txt"
    command = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    return subprocess.call(command, cwd=Path.cwd())


def _run_init(args) -> int:
    project_name = _prompt("Project name", default="smart-locator-pom")
    target_url = _prompt("Target URL")
    framework = _prompt("Framework choice (selenium/playwright/robot)", default="selenium").lower()
    project_root = Path(args.project_root) if args.project_root else Path.cwd() / project_name
    install_dependencies = args.install or _prompt("Install dependencies now? (y/N)", default="n").lower() in {"y", "yes"}

    config = ProjectConfig(
        project_name=project_name,
        target_url=target_url,
        framework=framework,
        project_root=project_root,
        dependencies_installed=False,
    )
    save_config(config)
    file_manager = FileManager(
        project_root,
        decision_callback=lambda path: _prompt(f"{path} exists. Merge / Overwrite / Skip", default="skip").lower(),
    )
    result = ProjectGenerator(config, file_manager=file_manager).initialize_project(strategy="ask")
    for operation in result.operations:
        print(f"{operation.status}: {operation.path}")
    if install_dependencies:
        exit_code = _install_dependencies(project_root)
        config.dependencies_installed = exit_code == 0
        save_config(config)
        print(f"Dependency installation finished with exit code {exit_code}.")
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return _run_init(args)
    if args.command == "run" and args.run_target == "tests":
        config = discover_config(Path.cwd())
        if config is None:
            raise SystemExit("No smartlocator.config.json found. Run `smart-locator init` first.")
        return run_tests(config.project_root)
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
