from tools.browser import Browser, register_browser_actions
from workflow.action_registry import ActionRegistry


def test_browser_rejects_unsafe_navigation_schemes() -> None:
    browser = Browser()

    for url in ("file:///tmp/test.txt", "javascript:alert(1)", "ftp://example.com"):
        try:
            browser._validate_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected URL rejection for {url}")


def test_browser_allows_http_and_https() -> None:
    browser = Browser()
    assert browser._validate_url("https://example.com") == "https://example.com"
    assert browser._validate_url("http://example.com/path") == "http://example.com/path"


def test_browser_allowed_hosts_are_enforced() -> None:
    browser = Browser(allowed_hosts={"example.com"})

    assert browser._validate_url("https://example.com") == "https://example.com"

    try:
        browser._validate_url("https://other.example")
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected disallowed host to be rejected")


def test_browser_rejects_embedded_credentials_and_invalid_ports() -> None:
    browser = Browser()
    for url in ("https://user:password@example.com", "https://example.com:notaport"):
        try:
            browser._validate_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected malformed or credential-bearing URL rejection: {url}")


def test_invalid_navigation_does_not_start_browser() -> None:
    browser = Browser()
    started = []
    browser.start = lambda: started.append(True)

    try:
        browser.open("file:///private/secret.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected file URL rejection")

    assert started == []


def test_search_respects_host_allowlist_before_starting_browser() -> None:
    browser = Browser(allowed_hosts={"example.com"})
    started = []
    browser.start = lambda: started.append(True)

    try:
        browser.search("private query")
    except PermissionError:
        pass
    else:
        raise AssertionError("Search should be blocked when Google is not allowlisted")

    assert started == []


def test_browser_rejects_empty_queries_selectors_and_invalid_scroll_values() -> None:
    browser = Browser()
    for operation in (
        lambda: browser.search("  "),
        lambda: browser.click(" "),
        lambda: browser.type("#search", 123),
        lambda: browser.scroll(10001),
        lambda: browser.scroll(True),
    ):
        try:
            operation()
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError("Expected invalid browser input to be rejected")


def test_browser_actions_register_without_starting_browser() -> None:
    registry = ActionRegistry()
    browser = Browser()

    register_browser_actions(registry, browser)

    assert browser.browser is None
    assert registry.get("browser_open") is not None
    assert registry.get("browser_extract_text") is not None
    assert registry.require("browser_click").requires_approval is True
    assert registry.require("browser_type").requires_approval is True
    assert registry.require("browser_screenshot").requires_approval is True
    assert registry.require("browser_click").metadata["capability"] == "browser"


def test_browser_read_actions_do_not_require_approval() -> None:
    registry = ActionRegistry()
    register_browser_actions(registry, Browser())

    for name in (
        "browser_start",
        "browser_open",
        "browser_search",
        "browser_current_page",
        "browser_extract_text",
        "browser_extract_links",
    ):
        assert registry.require(name).requires_approval is False
