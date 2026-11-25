import os
from pathlib import Path

import pytest

from core.tool_registry import Permission, registry
from tools.applications import Applications, WindowsApplicationDriver


class FakeApplicationDriver:
    def __init__(self):
        self.calls = []

    def list_installed_applications(self, limit):
        self.calls.append(("installed", limit))
        return [{"name": "Editor"}]

    def list_running_applications(self, limit):
        self.calls.append(("running", limit))
        return [{"pid": 123, "name": "editor.exe"}]

    def list_application_windows(self, limit):
        self.calls.append(("windows", limit))
        return [{"window_handle": 10, "title": "Editor", "pid": 123}]

    def launch_application(self, application, args, working_directory):
        self.calls.append(("launch", application, args, working_directory))
        return {"success": True, "application": application, "pid": 456}

    def focus_window(self, window_handle):
        self.calls.append(("focus", window_handle))
        return True

    def minimize_window(self, window_handle):
        self.calls.append(("minimize", window_handle))
        return True

    def maximize_window(self, window_handle):
        self.calls.append(("maximize", window_handle))
        return True

    def restore_window(self, window_handle):
        self.calls.append(("restore", window_handle))
        return True

    def close_window(self, window_handle):
        self.calls.append(("close", window_handle))
        return True

    def terminate_application(self, pid, expected_name, force):
        self.calls.append(("terminate", pid, expected_name, force))
        return {"success": True, "pid": pid, "name": expected_name, "force": force}


def test_discovery_methods_delegate_with_validated_limits():
    driver = FakeApplicationDriver()
    apps = Applications(driver)

    assert apps.list_installed_applications(10) == [{"name": "Editor"}]
    assert apps.list_running_applications(20)[0]["pid"] == 123
    assert apps.list_application_windows(30)[0]["window_handle"] == 10
    assert driver.calls == [("installed", 10), ("running", 20), ("windows", 30)]


@pytest.mark.parametrize("limit", [0, -1, True, 5001, "10"])
def test_discovery_rejects_invalid_limit_before_backend(limit):
    driver = FakeApplicationDriver()
    with pytest.raises(ValueError):
        Applications(driver).list_running_applications(limit)
    assert driver.calls == []


def test_launch_validates_arguments_and_working_directory(tmp_path):
    driver = FakeApplicationDriver()
    apps = Applications(driver)
    cwd = tmp_path / "work"
    cwd.mkdir()

    result = apps.launch_application("editor", ["--safe", "document.txt"], str(cwd))
    assert result["pid"] == 456
    assert driver.calls == [("launch", "editor", ["--safe", "document.txt"], str(cwd.resolve()))]

    with pytest.raises(ValueError):
        apps.launch_application("")
    with pytest.raises(TypeError):
        apps.launch_application("editor", "--unsafe")
    with pytest.raises(TypeError):
        apps.launch_application("editor", ["valid", 123])
    with pytest.raises(ValueError):
        apps.launch_application("editor", ["bad\x00arg"])
    with pytest.raises(NotADirectoryError):
        apps.launch_application("editor", working_directory=str(tmp_path / "missing"))


def test_launch_rejects_argument_count_and_size():
    apps = Applications(FakeApplicationDriver())
    with pytest.raises(ValueError, match="100"):
        apps.launch_application("editor", ["x"] * 101)
    with pytest.raises(ValueError, match="4096"):
        apps.launch_application("editor", ["x" * 4097])
    with pytest.raises(ValueError, match="32000"):
        apps.launch_application("editor", ["x" * 4000] * 9)


@pytest.mark.parametrize(
    "method,action",
    [
        ("focus_window", "focus"),
        ("minimize_window", "minimize"),
        ("maximize_window", "maximize"),
        ("restore_window", "restore"),
        ("close_window", "close"),
    ],
)
def test_window_actions_validate_handle_and_delegate(method, action):
    driver = FakeApplicationDriver()
    apps = Applications(driver)

    result = getattr(apps, method)(10)
    assert result == {"success": True, "window_handle": 10, "action": action}
    assert driver.calls == [(action, 10)]

    driver.calls.clear()
    for invalid in (0, -1, True, "10", 1.5):
        with pytest.raises(ValueError):
                getattr(apps, method)(invalid)
    assert driver.calls == []


def test_terminate_requires_pid_name_guard_and_boolean_force():
    driver = FakeApplicationDriver()
    apps = Applications(driver)

    result = apps.terminate_application(123, "editor.exe", force=True)
    assert result["force"] is True
    assert driver.calls == [("terminate", 123, "editor.exe", True)]

    with pytest.raises(TypeError):
        apps.terminate_application(123, "editor.exe", force="yes")
    with pytest.raises(ValueError):
        apps.terminate_application(123, "", force=False)


def test_application_tools_are_registered_with_risk_permissions():
    import tools.registry  # noqa: F401 - importing registers built-in tools

    permissions = {tool.name: tool.permission for tool in registry.list()}
    for name in (
        "applications.list_installed",
        "applications.list_running",
        "applications.list_windows",
    ):
        assert permissions[name] == Permission.READ
    assert permissions["applications.launch"] == Permission.WRITE
    for name in (
        "applications.focus_window",
        "applications.minimize_window",
        "applications.maximize_window",
        "applications.restore_window",
    ):
        assert permissions[name] == Permission.WRITE
    assert permissions["applications.close_window"] == Permission.DESTRUCTIVE
    assert permissions["applications.terminate"] == Permission.DESTRUCTIVE


def test_executable_launch_uses_argument_array_without_shell(tmp_path, monkeypatch):
    executable = tmp_path / "fake.exe"
    executable.write_text("test binary")
    executable.chmod(0o755)
    calls = []

    class FakeProcess:
        pid = 9876

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr("tools.applications.subprocess.Popen", fake_popen)
    backend = WindowsApplicationDriver()
    result = backend.launch_application(str(executable), ["--open", "file.txt"], str(tmp_path))

    assert result["pid"] == 9876
    assert calls[0][0] == [str(executable.resolve()), "--open", "file.txt"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["cwd"] == str(tmp_path)


def test_executable_launch_rejects_non_executable_file(tmp_path):
    executable = tmp_path / "not-executable"
    executable.write_text("data")
    executable.chmod(0o644)
    backend = WindowsApplicationDriver()

    if os.name == "nt":
        with pytest.raises(ValueError):
            backend.launch_application(str(executable), [], None)
    else:
        with pytest.raises(PermissionError):
            backend.launch_application(str(executable), [], None)
