"""
Browser Agent

Interprets browser-related tasks and uses the Browser Tool
to perform them.
"""

from core.logger import log
from tools.browser import browser


class BrowserAgent:

    def execute(self, task: str):

        log(f"Browser Agent received task: {task}")

        text = task.lower().strip()

        # ==================================================
        # OPEN URL
        # ==================================================

        if text.startswith("open "):

            url = task[5:].strip()

            log(f"Opening URL: {url}")

            return browser.open(url)

        # ==================================================
        # SEARCH WEB
        # ==================================================

        if text.startswith("search "):

            query = task[7:].strip()

            log(f"Searching web: {query}")

            return browser.search(query)

        # ==================================================
        # VISIT / RESEARCH WEBSITES
        # ==================================================

        if (
            "visit" in text
            or "websites" in text
            or "website" in text
            or "browse" in text
        ):

            log(
                "Browser task requires website research."
            )

            return browser.search(task)

        # ==================================================
        # EXTRACT PAGE TEXT
        # ==================================================

        if (
            "extract text" in text
            or "read page" in text
            or "read webpage" in text
            or "page text" in text
        ):

            log("Extracting page text.")

            return browser.extract_text()

        # ==================================================
        # EXTRACT LINKS
        # ==================================================

        if (
            "extract links" in text
            or "get links" in text
            or "find links" in text
        ):

            log("Extracting page links.")

            return browser.extract_links()

        # ==================================================
        # SCREENSHOT
        # ==================================================

        if "screenshot" in text:

            path = "browser_screenshot.png"

            log(f"Taking screenshot: {path}")

            return browser.screenshot(path)

        # ==================================================
        # BACK
        # ==================================================

        if text == "back" or "go back" in text:

            log("Going back.")

            return browser.back()

        # ==================================================
        # FORWARD
        # ==================================================

        if text == "forward" or "go forward" in text:

            log("Going forward.")

            return browser.forward()

        # ==================================================
        # REFRESH
        # ==================================================

        if text == "refresh" or "reload" in text:

            log("Refreshing page.")

            return browser.refresh()

        # ==================================================
        # CURRENT PAGE
        # ==================================================

        if (
            "current page" in text
            or "where am i" in text
            or "current website" in text
        ):

            return browser.current_page()

        # ==================================================
        # UNKNOWN
        # ==================================================

        log(
            f"Browser Agent does not understand task: {task}"
        )

        return {
            "success": False,
            "error": (
                "Browser Agent does not understand "
                f"this task yet: {task}"
            )
        }


# ==========================================================
# Global Browser Agent
# ==========================================================

browser_agent = BrowserAgent()