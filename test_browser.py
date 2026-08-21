"""Browser integration tests.

These tests are opt-in because they launch a real browser and depend on
external websites. They are intentionally deterministic and do not use
interactive input so pytest can collect them safely.
"""

import os

import pytest


if not os.getenv("AIOS_RUN_BROWSER_TESTS"):
    pytest.skip(
        "Browser integration tests require AIOS_RUN_BROWSER_TESTS=1",
        allow_module_level=True,
    )

from tools.browser import browser


@pytest.fixture(scope="module", autouse=True)
def browser_session():
    yield
    browser.close()


def test_open_example():
    result = browser.open("https://example.com")
    assert result["url"].startswith("https://example.com")


def test_extract_example_text():
    browser.open("https://example.com")
    text = browser.extract_text()
    assert "Example Domain" in text


def test_extract_example_links():
    browser.open("https://example.com")
    links = browser.extract_links()
    assert any("iana.org" in link["href"] for link in links)
