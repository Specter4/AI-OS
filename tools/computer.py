"""
AI-OS Computer Interaction Tool

A bounded, optional adapter for basic desktop interaction. The PyAutoGUI
dependency is loaded only when a real desktop action is requested, so tests
and headless installations can use an injected driver without touching a GUI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.logger import log


class Computer:
    """Validated desktop actions backed by a PyAutoGUI-compatible driver."""

    def __init__(self, driver: Any | None = None) -> None:
        self._driver = driver

    def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                import pyautogui
            except ImportError as exc:
                raise RuntimeError(
                    "Desktop interaction is unavailable. Install the optional "
                    "dependency with: python -m pip install pyautogui"
                ) from exc
            self._driver = pyautogui
        return self._driver

    def screen_size(self) -> dict[str, int]:
        size = self._get_driver().size()
        width, height = int(size.width), int(size.height)
        if width <= 0 or height <= 0:
            raise RuntimeError("Desktop driver returned an invalid screen size")
        return {"width": width, "height": height}

    def _validate_coordinates(self, x: int, y: int) -> tuple[int, int]:
        if isinstance(x, bool) or not isinstance(x, int):
            raise TypeError("x must be an integer")
        if isinstance(y, bool) or not isinstance(y, int):
            raise TypeError("y must be an integer")
        size = self.screen_size()
        if not (0 <= x < size["width"] and 0 <= y < size["height"]):
            raise ValueError(
                f"Coordinates must be inside the screen (0..{size['width'] - 1}, "
                f"0..{size['height'] - 1})"
            )
        return x, y

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        x, y = self._validate_coordinates(x, y)
        if button not in {"left", "right", "middle"}:
            raise ValueError("button must be left, right, or middle")
        self._get_driver().click(x=x, y=y, button=button)
        log(f"Desktop click: ({x}, {y}), button={button}")
        return {"success": True, "action": "click", "x": x, "y": y, "button": button}

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        x, y = self._validate_coordinates(x, y)
        self._get_driver().moveTo(x, y)
        log(f"Desktop mouse moved: ({x}, {y})")
        return {"success": True, "action": "move_mouse", "x": x, "y": y}

    def type_text(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if not text:
            raise ValueError("text must not be empty")
        if len(text) > 5000:
            raise ValueError("text exceeds the 5000-character safety limit")
        self._get_driver().write(text, interval=0.01)
        log(f"Desktop text entered ({len(text)} characters)")
        return {"success": True, "action": "type_text", "characters": len(text)}

    def press_key(self, key: str) -> dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("A non-empty key name is required")
        normalized = key.strip().lower()
        # Deliberately disallow arbitrary hotkey/chord execution in this step.
        allowed = {
            "enter", "tab", "esc", "escape", "space", "backspace", "delete",
            "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10",
            "f11", "f12",
        }
        if normalized not in allowed:
            raise ValueError(f"Key is not allowed for direct press: {normalized}")
        self._get_driver().press(normalized)
        log(f"Desktop key pressed: {normalized}")
        return {"success": True, "action": "press_key", "key": normalized}

    def screenshot(self, path: str, overwrite: bool = False) -> dict[str, Any]:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("A non-empty screenshot path is required")
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        target = Path(path).expanduser().resolve()
        if target.exists() and not overwrite:
            raise FileExistsError(f"Screenshot already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._get_driver().screenshot().save(str(target))
        log(f"Desktop screenshot saved: {target}")
        return {"success": True, "action": "screenshot", "path": str(target)}


computer = Computer()
