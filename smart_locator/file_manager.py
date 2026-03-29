"""Safe file writing helpers with backup and merge support."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional


DecisionCallback = Callable[[Path], str]


@dataclass
class FileOperationResult:
    """Describes the result of a file write attempt."""

    status: str
    path: Path
    message: str


class FileManager:
    """Coordinates safe writes for generated files."""

    def __init__(self, project_root: Path, decision_callback: Optional[DecisionCallback] = None) -> None:
        self.project_root = project_root
        self.backup_root = project_root / ".backup"
        self.decision_callback = decision_callback

    def write_file(self, relative_path: str, content: str, *, strategy: str = "ask") -> FileOperationResult:
        destination = self.project_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_text(content, encoding="utf-8")
            return FileOperationResult("CREATE", destination, "created new file")

        decision = strategy.lower()
        if decision == "ask":
            decision = self._prompt_for_existing_file(destination)

        if decision == "skip":
            return FileOperationResult("SKIP", destination, "kept existing file")
        if decision == "overwrite":
            self._backup_file(destination)
            destination.write_text(content, encoding="utf-8")
            return FileOperationResult("OVERWRITE", destination, "replaced existing file")
        if decision == "merge":
            self._backup_file(destination)
            merged = self._merge_content(destination, content)
            destination.write_text(merged, encoding="utf-8")
            return FileOperationResult("MERGE", destination, "merged generated changes")
        return FileOperationResult("ERROR", destination, f"unsupported decision: {decision}")

    def _prompt_for_existing_file(self, path: Path) -> str:
        if self.decision_callback is not None:
            return self.decision_callback(path).strip().lower() or "skip"
        return "skip"

    def _backup_file(self, path: Path) -> None:
        relative = path.relative_to(self.project_root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_name = relative.as_posix().replace("/", "__")
        destination = self.backup_root / f"{stamp}__{backup_name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    def _merge_content(self, path: Path, incoming: str) -> str:
        if path.suffix == ".py":
            return self._merge_python(path.read_text(encoding="utf-8"), incoming)
        if path.suffix == ".robot":
            return self._merge_robot(path.read_text(encoding="utf-8"), incoming)
        return incoming

    def _merge_python(self, existing: str, incoming: str) -> str:
        try:
            existing_tree = ast.parse(existing)
            incoming_tree = ast.parse(incoming)
        except SyntaxError:
            return incoming

        existing_names = self._top_level_names(existing_tree)
        existing_lines = existing.splitlines()
        incoming_lines = incoming.splitlines()

        imports: List[str] = []
        additions: List[str] = []
        for node in incoming_tree.body:
            segment = ast.get_source_segment(incoming, node)
            if not segment:
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if segment not in existing:
                    imports.append(segment)
                continue
            name = getattr(node, "name", None)
            if name and name in existing_names:
                continue
            additions.append(segment)

        merged_parts = [existing.rstrip()]
        if imports:
            merged_parts.insert(0, "\n".join(imports).rstrip())
        if additions:
            merged_parts.append("\n\n".join(additions).rstrip())
        merged = "\n\n".join(part for part in merged_parts if part).rstrip() + "\n"
        if merged == "\n":
            return existing if existing.endswith("\n") else existing + "\n"
        return merged

    def _top_level_names(self, tree: ast.AST) -> Dict[str, str]:
        names: Dict[str, str] = {}
        for node in getattr(tree, "body", []):
            name = getattr(node, "name", None)
            if name:
                names[name] = name
        return names

    def _merge_robot(self, existing: str, incoming: str) -> str:
        existing_sections = self._robot_sections(existing)
        incoming_sections = self._robot_sections(incoming)
        for name, lines in incoming_sections.items():
            if name not in existing_sections:
                existing_sections[name] = lines
                continue
            for line in lines:
                if line not in existing_sections[name]:
                    existing_sections[name].append(line)
        blocks = []
        for name, lines in existing_sections.items():
            blocks.append(name)
            blocks.extend(lines)
            blocks.append("")
        return "\n".join(blocks).rstrip() + "\n"

    def _robot_sections(self, content: str) -> Dict[str, List[str]]:
        sections: Dict[str, List[str]] = {}
        current = "*** Keywords ***"
        sections[current] = []
        for line in content.splitlines():
            if line.startswith("***"):
                current = line
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(line)
        return sections
