"""Typed models used across the package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class LocatorCandidate:
    strategy: str
    value: str
    score: int
    reason: str
    warning: Optional[str] = None
    tier: str = "GOOD"
    validation: Optional[str] = None


@dataclass
class ElementContext:
    tag: str
    text: str
    attributes: Dict[str, str]
    parent: Optional[Dict[str, str]] = None
    frame_path: List[str] = field(default_factory=list)
    shadow_path: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        for key in ("aria-label", "data-testid", "name", "id", "placeholder"):
            value = self.attributes.get(key)
            if value:
                return value.strip()
        if self.text.strip():
            return self.text.strip()
        return self.tag
