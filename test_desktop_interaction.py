from pathlib import Path
from types import SimpleNamespace

import pytest

from core.tool_registry import Permission, registry
from tools.computer import Computer


class FakeScreenshot:
    def save(self, path):
        Path(path).write_bytes(b"fake-image")


class FakeDriver:
    def __init__(self, width=100, height=80):
        self.width = width
        self.height = height
        self.calls = []

    def size(self):
        return SimpleNamespace(width=self.width, height=self.height)

    def click(self, **kwargs):
        self.calls.append(("click", kwargs))

    def moveTo(self, x, y):
        self.calls.append(("moveTo", x, y))

    def write(self, text, interval=0):
        self.calls.append(("write", text, interval))

    def press(self, key):
        self.calls.append(("press", key))

    def screenshot(self):
        self.calls.append(("screenshot",))
        return FakeScreenshot()


def test_screen_size_and_click_use_validated_coordinates():
    driver = FakeDriver()
    computer = Computer(driver)

    assert computer.screen_size() == {"width": 100, "height": 80}
    result = computer.click(99, 79)

    assert result == {
        "success": True,
        "action": "click",
        "x": 99,
        "y": 79,
        "button": "left",
    }
    assert driver.calls[0] == ("click", {"x": 99, "y": 79, "button": "left"})


@pytest.mark.parametrize("x,y", [(-1, 0), (100, 0), (0, 80), (1.5, 2), (True, 2)])
def test_click_rejects_invalid_coordinates(x, y):
    driver = FakeDriver()
    with pytest.raises((ValueError, TypeError)):
        Computer(driver).click(x, y)
    assert driver.calls == []


def test_click_rejects_unsupported_button():
    driver = FakeDriver()
    with pytest.raises(ValueError, match="button"):
        Computer(driver).click(1, 2, "double")
    assert driver.calls == []


def test_type_text_validates_input_and_limits_length():
    driver = FakeDriver()
    computer = Computer(driver)

    assert computer.type_text("Hello")["characters"] == 5
    with pytest.raises(ValueError):
        computer.type_text("")
    with pytest.raises(TypeError):
        computer.type_text(123)
    with pytest.raises(ValueError, match="5000"):
        computer.type_text("x" * 5001)


def test_press_key_only_allows_single_safe_key_names():
    driver = FakeDriver()
    computer = Computer(driver)

    assert computer.press_key("ENTER")["key"] == "enter"
    with pytest.raises(ValueError, match="not allowed"):
        computer.press_key("ctrl+c")
    with pytest.raises(ValueError):
        computer.press_key("")

    assert driver.calls == [("press", "enter")]


def test_screenshot_refuses_overwrite_unless_explicitly_allowed(tmp_path):
    driver = FakeDriver()
    computer = Computer(driver)
    target = tmp_path / "screen.png"
    target.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        computer.screenshot(str(target))
    assert target.read_bytes() == b"existing"

    result = computer.screenshot(str(target), overwrite=True)
    assert result["success"] is True
    assert target.read_bytes() == b"fake-image"


def test_screenshot_rejects_empty_path_before_driver_call():
    driver = FakeDriver()
    with pytest.raises(ValueError):
        Computer(driver).screenshot("  ")
    assert driver.calls == []


def test_desktop_tools_are_registered_with_permission_boundaries():
    import tools.registry  # noqa: F401 - importing registers built-in tools

    permissions = {tool.name: tool.permission for tool in registry.list()}
    assert permissions["desktop.screen_size"] == Permission.READ
    for name in (
        "desktop.click",
        "desktop.move_mouse",
        "desktop.type_text",
        "desktop.press_key",
        "desktop.screenshot",
    ):
        assert permissions[name] == Permission.WRITE
