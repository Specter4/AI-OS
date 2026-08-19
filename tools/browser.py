"""
Browser Tool

General-purpose browser automation for AI-OS.

Provides:
- Website navigation
- Google search
- Clicking
- Typing
- Text extraction
- Link extraction
- Screenshots
- Scrolling
- Back / forward navigation
- Page refresh
- Browser lifecycle management
"""

from playwright.sync_api import sync_playwright

from core.logger import log


class Browser:

    def __init__(self):

        self.playwright = None
        self.browser = None
        self.page = None

    # ==================================================
    # START
    # ==================================================

    def start(self):

        if self.browser:

            return

        log("Starting browser...")

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=False
        )

        self.page = self.browser.new_page()

        log("Browser started.")

    # ==================================================
    # OPEN WEBSITE
    # ==================================================

    def open(self, url: str):

        self.start()

        log(f"Opening website: {url}")

        self.page.goto(
            url,
            wait_until="domcontentloaded"
        )

        return {
            "title": self.page.title(),
            "url": self.page.url
        }

    # ==================================================
    # SEARCH
    # ==================================================

    def search(self, query: str):

        self.start()

        log(f"Browser searching: {query}")

        self.page.goto(
            "https://www.google.com",
            wait_until="domcontentloaded"
        )

        search = self.page.locator(
            'textarea[name="q"]'
        )

        search.wait_for()

        search.fill(query)

        search.press("Enter")

        self.page.wait_for_load_state(
            "domcontentloaded"
        )

        result = {
            "title": self.page.title(),
            "url": self.page.url
        }

        log(
            f"Search completed: {result['title']}"
        )

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

        log(
            f"Typing into: {selector}"
        )

        element = self.page.locator(selector)

        element.wait_for()

        element.fill(text)

        return True

    # ==================================================
    # EXTRACT TEXT
    # ==================================================

    def extract_text(self, selector: str = "body"):

        self.start()

        log(
            f"Extracting text from: {selector}"
        )

        element = self.page.locator(selector)

        element.wait_for()

        return element.inner_text()

    # ==================================================
    # EXTRACT LINKS
    # ==================================================

    def extract_links(self):

        self.start()

        log("Extracting page links...")

        links = self.page.locator("a").evaluate_all(
            """
            elements => elements.map(
                element => ({
                    text: element.innerText,
                    href: element.href
                })
            )
            """
        )

        return links

    # ==================================================
    # SCREENSHOT
    # ==================================================

    def screenshot(self, path: str):

        self.start()

        log(
            f"Taking screenshot: {path}"
        )

        self.page.screenshot(
            path=path,
            full_page=True
        )

        return path

    # ==================================================
    # SCROLL
    # ==================================================

    def scroll(self, amount: int = 800):

        self.start()

        log(
            f"Scrolling page by {amount}px"
        )

        self.page.mouse.wheel(
            0,
            amount
        )

        return True

    # ==================================================
    # BACK
    # ==================================================

    def back(self):

        self.start()

        self.page.go_back(
            wait_until="domcontentloaded"
        )

        return {
            "title": self.page.title(),
            "url": self.page.url
        }

    # ==================================================
    # FORWARD
    # ==================================================

    def forward(self):

        self.start()

        self.page.go_forward(
            wait_until="domcontentloaded"
        )

        return {
            "title": self.page.title(),
            "url": self.page.url
        }

    # ==================================================
    # REFRESH
    # ==================================================

    def refresh(self):

        self.start()

        self.page.reload(
            wait_until="domcontentloaded"
        )

        return {
            "title": self.page.title(),
            "url": self.page.url
        }

    # ==================================================
    # CURRENT PAGE
    # ==================================================

    def current_page(self):

        self.start()

        return {
            "title": self.page.title(),
            "url": self.page.url
        }

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
# Global Browser Instance
# ======================================================

browser = Browser()