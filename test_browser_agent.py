"""Browser-agent integration tests.

Opt-in because these tests launch a real browser. They use example.com so
normal test runs are not dependent on search engines or bot-detection pages.
"""

import os

import pytest


if not os.getenv("AIOS_RUN_BROWSER_TESTS"):
    pytest.skip(
        "Browser-agent integration tests require AIOS_RUN_BROWSER_TESTS=1",
        allow_module_level=True,
    )

from agents.browser import browser_agent
from tools.browser import browser


@pytest.fixture(scope="module", autouse=True)
def browser_session():
    yield
    browser.close()


def test_agent_open():
    result = browser_agent.execute("open https://example.com")
    assert result["url"].startswith("https://example.com")


def test_agent_current_page():
    result = browser_agent.execute("current page")
    assert result["url"].startswith("https://example.com")


def test_agent_extract_text():
    result = browser_agent.execute("extract page text")
    assert "Example Domain" in result


def test_agent_extract_links():
    result = browser_agent.execute("extract links")
    assert any("iana.org" in link["href"] for link in result)
