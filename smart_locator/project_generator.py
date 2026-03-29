"""Generate framework-specific POM projects from package templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from jinja2 import Environment, FileSystemLoader

from .config import ProjectConfig, load_config, save_config
from .file_manager import FileManager, FileOperationResult
from .frameworks import BaseFramework, TemplateSpec, get_framework


@dataclass
class GenerationResult:
    """Summarizes generated files and framework context."""

    config: ProjectConfig
    operations: List[FileOperationResult]


class ProjectGenerator:
    """Scaffolds and updates framework-specific test projects."""

    def __init__(self, config: ProjectConfig, file_manager: Optional[FileManager] = None) -> None:
        self.config = config
        self.framework = get_framework(config.framework)
        self.file_manager = file_manager or FileManager(config.project_root)
        templates_root = Path(__file__).resolve().parent / "templates" / self.framework.template_dir()
        self.environment = Environment(loader=FileSystemLoader(str(templates_root)), autoescape=False)

    @classmethod
    def from_project_root(cls, project_root: Path, file_manager: Optional[FileManager] = None) -> "ProjectGenerator":
        return cls(load_config(project_root), file_manager=file_manager)

    def initialize_project(self, *, strategy: str = "ask") -> GenerationResult:
        operations = self._render_specs(self.framework.init_templates(self.config), strategy=strategy)
        requirements = "\n".join(self.framework.requirements()) + "\n"
        operations.append(self.file_manager.write_file("requirements.txt", requirements, strategy=strategy))
        self._update_generated_files(operations)
        return GenerationResult(self.config, operations)

    def generate_story(
        self,
        *,
        page_name: str,
        page_class_name: str,
        test_name: str,
        steps: Sequence[Dict[str, str]],
        strategy: str = "ask",
    ) -> GenerationResult:
        specs = self.framework.story_templates(self.config, page_name, page_class_name, test_name, steps)
        operations = self._render_specs(specs, strategy=strategy)
        self._update_generated_files(operations)
        return GenerationResult(self.config, operations)

    def merge_locator(self, *, page_name: str, field_name: str, selector: str, strategy: str = "ask") -> FileOperationResult:
        relative_path = self.framework.merge_target_for_locator(page_name)
        snippet = self.framework.merge_snippet(page_name, field_name, selector)
        result = self.file_manager.write_file(relative_path, snippet, strategy=strategy)
        self._update_generated_files([result])
        return result

    def show_project_structure(self) -> str:
        return "\n".join(self.framework.display_tree())

    def _render_specs(self, specs: Sequence[TemplateSpec], *, strategy: str) -> List[FileOperationResult]:
        operations: List[FileOperationResult] = []
        for spec in specs:
            content = self._render_template(spec)
            operations.append(self.file_manager.write_file(spec.output_path, content, strategy=strategy))
        return operations

    def _render_template(self, spec: TemplateSpec) -> str:
        template = self.environment.get_template(spec.template_name)
        content = template.render(**spec.context)
        return content.rstrip() + "\n"

    def _update_generated_files(self, operations: Sequence[FileOperationResult]) -> None:
        generated = {Path(item).as_posix() for item in self.config.generated_files}
        for operation in operations:
            if operation.status != "ERROR":
                relative = operation.path.relative_to(self.config.project_root).as_posix()
                generated.add(relative)
        self.config.generated_files = sorted(generated)
        save_config(self.config)
