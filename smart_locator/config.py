"""Project configuration helpers for generated POM workspaces."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


CONFIG_FILE_NAME = "smartlocator.config.json"


@dataclass
class ProjectConfig:
    """Serializable project configuration."""

    project_name: str
    target_url: str
    framework: str
    project_root: Path
    dependencies_installed: bool = False
    generated_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["project_root"] = str(self.project_root)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ProjectConfig":
        return cls(
            project_name=str(payload["project_name"]),
            target_url=str(payload["target_url"]),
            framework=str(payload["framework"]),
            project_root=Path(str(payload["project_root"])),
            dependencies_installed=bool(payload.get("dependencies_installed", False)),
            generated_files=[str(item) for item in payload.get("generated_files", [])],
        )


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_FILE_NAME


def save_config(config: ProjectConfig) -> Path:
    destination = config_path(config.project_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    return destination


def load_config(project_root: Path) -> ProjectConfig:
    payload = json.loads(config_path(project_root).read_text(encoding="utf-8"))
    return ProjectConfig.from_dict(payload)


def discover_config(start: Path) -> Optional[ProjectConfig]:
    current = start.resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        path = config_path(candidate)
        if path.exists():
            return load_config(candidate)
    return None
