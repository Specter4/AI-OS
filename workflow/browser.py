"""Safe browser/web actions for the JARVIS execution layer.

The Playwright dependency is imported lazily so the registry and tests remain
usable when browser automation is not installed. Browser side-effect actions
are registered as approval-gated actions by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from core.tool_registry import Permission
from workflow.action_registry import ActionRegistry, ActionSpec


class BrowserPage(Protocol):
    def goto(self, url: str, **kwargs: Any) -> Any: ...
    def title(self) -> str: ...
    def content(self) -> str: ...
    def click(self, selector: str, **kwargs: Any) -> Any: ...
    def fill(self, selector: str, value: str, **kwargs: Any) -> Any: ...
    def press(self, selector: str, key: str, **kwargs: Any) -> Any: ...


class BrowserContext(Protocol):
    def new_page(self) -> BrowserPage: ...
    def close(self) -> Any: ...


@dataclass(frozen=True)
class BrowserPageState:
    url: str
    title: str


class BrowserController:
    """Controlled Playwright browser session with a single active page."""

    def __init__(
        self,
        *,
        headless: bool = True,
        allowed_hosts: set[str] | None = None,
        timeout_ms: int = 30_000,
    ) -> None:
        self.headless = headless
        self.allowed_hosts = {host.lower() for host in allowed_hosts} if allowed_hosts else None
        self.timeout_ms = timeout_ms
        self._playwright: Any = None
        self._browser: Any = None
        self._context: BrowserContext | None = None
        self._page: BrowserPage | None = None

    def _validate_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Browser URLs must use http:// or https://")
        if self.allowed_hosts is not None and parsed.hostname and parsed.hostname.lower() not in self.allowed_hosts:
            raise PermissionError(f"Browser host is not allowed: {parsed.hostname}")
        return url.strip()

    def _require_page(self) -> BrowserPage:
        if self._page is None:
            raise RuntimeError("Browser session is not started")
        return self._page

    def start(self) -> BrowserPageState:
        if self._page is not None:
            return self.state()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for browser automation. Install it with "
                "'pip install playwright' and then run 'playwright install'."
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms) if hasattr(self._page, "set_default_timeout") else None
        return self.state()

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def navigate(self, url: str) -> BrowserPageState:
        page = self._require_page()
        safe_url = self._validate_url(url)
        page.goto(safe_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        return self.state()

    def state(self) -> BrowserPageState:
        page = self._require_page()
        return BrowserPageState(url=str(getattr(page, "url", "")), title=page.title())

    def read_page(self) -> dict[str, str]:
        page = self._require_page()
        return {"url": str(getattr(page, "url", "")), "title": page.title(), "content": page.content()}

    def click(self, selector: str) -> BrowserPageState:
        page = self._require_page()
        page.click(selector, timeout=self.timeout_ms)
        return self.state()

    def fill(self, selector: str, value: str) -> BrowserPageState:
        page = self._require_page()
        page.fill(selector, value, timeout=self.timeout_ms)
        return self.state()

    def press(self, selector: str, key: str) -> BrowserPageState:
        page = self._require_page()
        page.press(selector, key, timeout=self.timeout_ms)
        return self.state()


def register_browser_actions(registry: ActionRegistry, controller: BrowserController) -> None:
    """Register browser actions without starting a browser or performing I/O."""
    registry.register(ActionSpec(
        "browser_start",
        "Start the controlled JARVIS browser session.",
        handler=controller.start,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_navigate",
        "Navigate the controlled browser to an HTTP or HTTPS URL.",
        handler=controller.navigate,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_state",
        "Read the current browser URL and page title.",
        handler=controller.state,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_read_page",
        "Read the current browser page content.",
        handler=controller.read_page,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_click",
        "Click an element in the controlled browser using a selector.",
        handler=controller.click,
        requires_approval=True,
        metadata={"permission": Permission.WRITE, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_fill",
        "Fill a form field in the controlled browser using a selector.",
        handler=controller.fill,
        requires_approval=True,
        metadata={"permission": Permission.WRITE, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_press",
        "Press a keyboard key in the controlled browser using a selector.",
        handler=controller.press,
        requires_approval=True,
        metadata={"permission": Permission.WRITE, "capability": "browser"},
    ))


__all__ = ["BrowserController", "BrowserPageState", "register_browser_actions"]
