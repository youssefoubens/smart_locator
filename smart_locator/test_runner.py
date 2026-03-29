"""Framework-aware test execution helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

from .config import load_config
from .frameworks import get_framework


ANSI = {
    "pass": "\033[92m",
    "fail": "\033[91m",
    "info": "\033[96m",
    "reset": "\033[0m",
}


def detect_command(project_root: Path) -> List[str]:
    config = load_config(project_root)
    framework = get_framework(config.framework)
    return framework.test_command(config)


def colorize_test_output(line: str) -> str:
    lowered = line.lower()
    if any(token in lowered for token in ("passed", "ok", "green")):
        return f"{ANSI['pass']}{line}{ANSI['reset']}"
    if any(token in lowered for token in ("failed", "error", "red")):
        return f"{ANSI['fail']}{line}{ANSI['reset']}"
    return f"{ANSI['info']}{line}{ANSI['reset']}"


def run_tests(project_root: Path) -> int:
    command = detect_command(project_root)
    process = subprocess.Popen(
        command,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(colorize_test_output(line.rstrip()))
    return process.wait()
