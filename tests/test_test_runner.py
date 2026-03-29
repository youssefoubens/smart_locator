from pathlib import Path
from unittest.mock import Mock, patch

from smart_locator.config import ProjectConfig, save_config
from smart_locator.test_runner import colorize_test_output, detect_command, run_tests


def test_detect_command_uses_framework_config(tmp_path: Path):
    project_root = tmp_path / "demo"
    save_config(
        ProjectConfig(
            project_name="demo",
            target_url="https://example.test/login",
            framework="selenium",
            project_root=project_root,
        )
    )

    assert detect_command(project_root) == ["pytest", "-q"]


def test_colorize_test_output_marks_failures():
    assert "\033[91m" in colorize_test_output("1 failed")
    assert "\033[92m" in colorize_test_output("1 passed")


@patch("smart_locator.test_runner.subprocess.Popen")
def test_run_tests_streams_output(mock_popen, tmp_path: Path):
    project_root = tmp_path / "demo"
    save_config(
        ProjectConfig(
            project_name="demo",
            target_url="https://example.test/login",
            framework="selenium",
            project_root=project_root,
        )
    )
    process = Mock()
    process.stdout = iter(["1 passed\n"])
    process.wait.return_value = 0
    mock_popen.return_value = process

    assert run_tests(project_root) == 0
