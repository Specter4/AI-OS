import os
import sys
import time

import pytest

from core.tool_registry import Permission, registry
from tools.terminal import Terminal


def test_run_program_returns_stdout_stderr_and_exit_code():
    result = Terminal().run_program(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)"]
    )
    assert result["success"] is False
    assert result["exit_code"] == 7
    assert result["stdout"].strip() == "out"
    assert result["stderr"].strip() == "err"
    assert result["timed_out"] is False
    assert result["execution_mode"] == "process"


def test_run_program_uses_requested_working_directory(tmp_path):
    result = Terminal().run_program(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cwd=tmp_path,
    )
    assert result["success"] is True
    assert result["stdout"].strip() == str(tmp_path.resolve())


def test_run_program_bounds_output():
    result = Terminal().run_program(
        [sys.executable, "-c", "print('x' * 10000)"],
        max_output_chars=100,
    )
    assert len(result["stdout"]) <= 100
    assert result["stdout_truncated"] is True


def test_run_program_times_out_and_stops_process():
    started = time.monotonic()
    result = Terminal().run_program(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout=0.2,
    )
    assert result["timed_out"] is True
    assert result["success"] is False
    assert time.monotonic() - started < 5


def test_run_shell_executes_explicit_shell_command():
    terminal = Terminal()
    if os.name == "nt":
        shell = "powershell"
        command = "Write-Output 'shell-ok'"
    else:
        shell = "sh"
        command = "printf 'shell-ok\\n'"
    result = terminal.run_shell(command, shell=shell)
    assert result["success"] is True
    assert "shell-ok" in result["stdout"]
    assert result["execution_mode"] == "shell"
    assert result["shell"] == shell


@pytest.mark.parametrize("command", ["", "   ", "bad\x00command", 123])
def test_run_shell_rejects_invalid_command(command):
    with pytest.raises((TypeError, ValueError)):
        Terminal().run_shell(command)


def test_run_shell_rejects_unknown_or_platform_incompatible_shell():
    with pytest.raises(ValueError):
        Terminal().run_shell("echo ok", shell="fish")
    with pytest.raises((TypeError, ValueError)):
        Terminal().run_shell("echo ok", shell=123)
    if os.name != "nt":
        with pytest.raises(ValueError):
            Terminal().run_shell("echo ok", shell="cmd")


@pytest.mark.parametrize(
    "command",
    [
        [],
        [""],
        ["valid", "bad\x00arg"],
        ["valid", 1],
        [sys.executable] + ["x"] * 128,
    ],
)
def test_run_program_rejects_invalid_argv(command):
    with pytest.raises((TypeError, ValueError)):
        Terminal().run_program(command)


def test_run_program_rejects_invalid_cwd_and_limits(tmp_path):
    terminal = Terminal()
    with pytest.raises(NotADirectoryError):
        terminal.run_program([sys.executable, "-c", "pass"], cwd=tmp_path / "missing")
    with pytest.raises(ValueError):
        terminal.run_program([sys.executable, "-c", "pass"], timeout=301)
    with pytest.raises(ValueError):
        terminal.run_program([sys.executable, "-c", "pass"], max_output_chars=100001)


def test_terminal_tools_are_registered_as_destructive():
    import tools.registry  # noqa: F401 - registers built-in tools

    permissions = {tool.name: tool.permission for tool in registry.list()}
    assert permissions["terminal.run_program"] == Permission.DESTRUCTIVE
    assert permissions["terminal.run_shell"] == Permission.DESTRUCTIVE
