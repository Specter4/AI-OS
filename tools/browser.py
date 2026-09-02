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
        self.allowed_hosts = {host.lower() for host in allowed_hosts} if allowed_hosts else None
        self.playwright = None
        self.browser = None
        self.page = None

    def _validate_url(self, url: str) -> str:
        value = url.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Browser URLs must use http:// or https://")
        if self.allowed_hosts is not None:
            hostname = (parsed.hostname or "").lower()
            if hostname not in self.allowed_hosts:
                raise PermissionError(f"Browser host is not allowed: {hostname}")
        return value

    # ==================================================
    # START
    # ==================================================

    def start(self):
        if self.browser:
            return

        log("Starting browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page()
        log("Browser started.")

    # ==================================================
    # OPEN WEBSITE
    # ==================================================

    def open(self, url: str):
        self.start()
        safe_url = self._validate_url(url)
        log(f"Opening website: {safe_url}")
        self.page.goto(safe_url, wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    # ==================================================
    # SEARCH
    # ==================================================

    def search(self, query: str):
        self.start()
        log(f"Browser searching: {query}")
        self.page.goto("https://www.google.com", wait_until="domcontentloaded")
        search = self.page.locator('textarea[name="q"]')
        search.wait_for()
        search.fill(query)
        search.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")
        result = {"title": self.page.title(), "url": self.page.url}
        log(f"Search completed: {result['title']}")
        return result

    # ==================================================
    # CLICK
    # ==================================================

    def click(self, selector: str):
        self.start()
        log(f"Clicking: {selector}")
        element = self.page.locator(selector)
        element.wait_for()
        element.click()
        return True

    # ==================================================
    # TYPE
    # ==================================================

    def type(self, selector: str, text: str):
        self.start()
        log(f"Typing into: {selector}")
        element = self.page.locator(selector)
        element.wait_for()
        element.fill(text)
        return True

    # ==================================================
    # EXTRACT TEXT
    # ==================================================

    def extract_text(self, selector: str = "body"):
        self.start()
        log(f"Extracting text from: {selector}")
        element = self.page.locator(selector)
        element.wait_for()
        return element.inner_text()

    # ==================================================
    # EXTRACT LINKS
    # ==================================================

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

    # ==================================================
    # SCREENSHOT
    # ==================================================

    def screenshot(self, path: str):
        self.start()
        log(f"Taking screenshot: {path}")
        self.page.screenshot(path=path, full_page=True)
        return path

    # ==================================================
    # SCROLL
    # ==================================================

    def scroll(self, amount: int = 800):
        self.start()
        log(f"Scrolling page by {amount}px")
        self.page.mouse.wheel(0, amount)
        return True

    # ==================================================
    # BACK
    # ==================================================

    def back(self):
        self.start()
        self.page.go_back(wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    # ==================================================
    # FORWARD
    # ==================================================

    def forward(self):
        self.start()
        self.page.go_forward(wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    # ==================================================
    # REFRESH
    # ==================================================

    def refresh(self):
        self.start()
        self.page.reload(wait_until="domcontentloaded")
        return {"title": self.page.title(), "url": self.page.url}

    # ==================================================
    # CURRENT PAGE
    # ==================================================

    def current_page(self):
        self.start()
        return {"title": self.page.title(), "url": self.page.url}

    # ==================================================
    # CLOSE
    # ==================================================

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


# ======================================================
# Action Registry Integration
# ======================================================

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
        "Open an HTTP or HTTPS website in the JARVIS browser.",
        handler=controller.open,
        metadata={"permission": Permission.READ, "capability": "browser"},
    ))
    registry.register(ActionSpec(
        "browser_search",
        "Search the web using the controlled browser.",
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


# ======================================================
# Global Browser Instance
# ======================================================

browser = Browser()


__all__ = ["Browser", "browser", "register_browser_actions"]
