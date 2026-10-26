"""
Browser Tool

General-purpose browser automation for AI-OS.

Provides website navigation, search, clicking, typing, text/link extraction,
screenshots, scrolling, history navigation, refresh, and lifecycle control.

The tool validates navigation URLs and can optionally restrict browser hosts.
Side-effecting browser actions are exposed through the execution registry with
approval required by default; the browser itself does not bypass the approval
layer.
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Any

from playwright.sync_api import sync_playwright

from core.logger import log
from core.tool_registry import Permission
from workflow.action_registry import ActionRegistry, ActionSpec


class Browser:
    """Playwright-backed browser with explicit URL safety boundaries."""

    def __init__(
        self,
        *,
        headless: bool = False,
        allowed_hosts: set[str] | None = None,
    ) -> None:
        self.headless = headless
        self.allowed_hosts = {host.lower().strip(".") for host in allowed_hosts} if allowed_hosts else None
        self.playwright = None
        self.browser = None
        self.page = None

    def _validate_url(self, url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("A non-empty URL is required")

        value = url.strip()
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Browser URLs must use http:// or https://")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Browser URLs must not contain embedded credentials")

        hostname = (parsed.hostname or "").lower().rstrip(".")
        if not hostname:
            raise ValueError("Browser URL must include a hostname")
        try:
            parsed.port  # Force urllib to reject malformed ports before browser startup.
        except ValueError as exc:
            raise ValueError("Browser URL contains an invalid port") from exc

        if self.allowed_hosts is not None and hostname not in self.allowed_hosts:
            raise PermissionError(f"Browser host is not allowed: {hostname}")

        return value

    @staticmethod
    def _validate_selector(selector: str) -> str:
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("A non-empty browser selector is required")
        return selector.strip()

    def start(self):
        if self.browser:
            return

        log("Starting browser...")
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.page = self.browser.new_page()
        except Exception:
            self.playwright.stop()
            self.playwright = None
            self.browser = None
            self.page = None
            raise
        log("Browser started.")

    def open(self, url: str):
        # Validate before starting Playwright so rejected input has no side effects.
        safe_url = self._validate_url(url)
        self.start()
        log(f"Opening website: {safe_url}")
        self.page.goto(safe_url, wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    def search(self, query: str):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("A non-empty search query is required")
        # The search provider is subject to the same host allowlist as all navigation.
        search_url = self._validate_url("https://www.google.com")
        self.start()
        log(f"Browser searching: {query.strip()}")
        self.page.goto(search_url, wait_until="domcontentloaded")
        search = self.page.locator('textarea[name="q"]')
        search.wait_for()
        search.fill(query.strip())
        search.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")
        result = {"title": self.page.title(), "url": self.page.url}
        log(f"Search completed: {result['title']}")
        return result

    def click(self, selector: str):
        selector = self._validate_selector(selector)
        self.start()
        log(f"Clicking: {selector}")
        element = self.page.locator(selector)
        element.wait_for()
        element.click()
        return True

    def type(self, selector: str, text: str):
        selector = self._validate_selector(selector)
        if not isinstance(text, str):
            raise TypeError("Browser input text must be a string")
        self.start()
        log(f"Typing into: {selector}")
        element = self.page.locator(selector)
        element.wait_for()
        element.fill(text)
        return True

    def extract_text(self, selector: str = "body"):
        selector = self._validate_selector(selector)
        self.start()
        log(f"Extracting text from: {selector}")
        element = self.page.locator(selector)
        element.wait_for()
        return element.inner_text()

    def extract_links(self):
        self.start()
        log("Extracting page links...")
        return self.page.locator("a").evaluate_all(
            """
            elements => elements.map(
                element => ({
                    text: element.innerText,
                    href: element.href
                })
            )
            """
        )

    def screenshot(self, path: str):
        if not isinstance(path, str) or not path.strip():
            raise ValueError("A non-empty screenshot path is required")
        self.start()
        log(f"Taking screenshot: {path}")
        self.page.screenshot(path=path, full_page=True)
        return path

    def scroll(self, amount: int = 800):
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise TypeError("Scroll amount must be an integer")
        if not -10000 <= amount <= 10000:
            raise ValueError("Scroll amount must be between -10000 and 10000 pixels")
        self.start()
        log(f"Scrolling page by {amount}px")
        self.page.mouse.wheel(0, amount)
        return True

    def back(self):
        self.start()
        self.page.go_back(wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    def forward(self):
        self.start()
        self.page.go_forward(wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    def refresh(self):
        self.start()
        self.page.reload(wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    def current_page(self):
        self.start()
        return {"title": self.page.title(), "url": self.page.url}

    def close(self):
        if self.browser:
            log("Closing browser...")
            self.browser.close()
            self.browser = None
            self.page = None

        if self.playwright:
            self.playwright.stop()
            self.playwright = None

        log("Browser closed.")


def register_browser_actions(
    registry: ActionRegistry,
    controller: Browser,
) -> None:
    """Register browser capabilities without performing browser I/O."""
    registry.register(ActionSpec(
        "browser_start",
        "Start the JARVIS browser session.",
        handler=controller.start,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_open",
        "Open an HTTP or HTTPS website allowed by the browser host policy.",
        handler=controller.open,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_search",
        "Search the web using the controlled browser, subject to the host policy.",
        handler=controller.search,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_current_page",
        "Read the current browser page URL and title.",
        handler=controller.current_page,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_extract_text",
        "Extract visible text from the current browser page.",
        handler=controller.extract_text,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_extract_links",
        "Extract links from the current browser page.",
        handler=controller.extract_links,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))

    for name, description, handler in (
        ("browser_click", "Click an element in the browser.", controller.click),
        ("browser_type", "Type text into a browser field.", controller.type),
        ("browser_scroll", "Scroll the current browser page.", controller.scroll),
        ("browser_back", "Navigate the browser back one page.", controller.back),
        ("browser_forward", "Navigate the browser forward one page.", controller.forward),
        ("browser_refresh", "Refresh the current browser page.", controller.refresh),
        ("browser_screenshot", "Save a screenshot of the current browser page.", controller.screenshot),
    ):
        registry.register(ActionSpec(
            name,
            description,
            handler=handler,
            requires_approval=True,
            metadata={"permission": Permission.WRITE, "capability": "browser"},
        ))


browser = Browser()


__all__ = ["Browser", "browser", "register_browser_actions"]
