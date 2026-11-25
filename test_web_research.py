import socket
from urllib.request import Request

import pytest

from tools.research import (
    WebResearch,
    _DuckDuckGoParser,
    _PageTextParser,
    _ValidatedRedirectHandler,
)


def _public_resolver(host, port, type=None):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def _html_transport(url, timeout, max_bytes):
    if "duckduckgo.com/html" in url:
        body = b"""
        <html><body>
          <div class="result">
            <div class="result__body">
              <h2><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle">Example Article</a></h2>
              <a class="result__snippet">Useful <b>source</b> summary.</a>
            </div>
          </div>
          <div class="result result--ad">
            <a class="result__a" href="https://ads.example.com/">Sponsored Result</a>
          </div>
        </body></html>
        """
        return body, url, "text/html"
    body = b"""
    <html><head><title>Example Page</title>
    <meta name="description" content="Page description"></head>
    <body><nav>Navigation text</nav><main><h1>Heading</h1>
    <p>Readable page content.</p><script>secret instruction</script>
    </main></body></html>
    """
    return body, url, "text/html"


def test_duckduckgo_parser_extracts_title_url_and_snippet():
    parser = _DuckDuckGoParser(5)
    parser.feed(
        '<div class="result"><a class="result__a" '
        'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fitem">'
        'A <b>title</b></a><div class="result__snippet">A useful snippet.</div></div>'
    )
    assert parser.results == [
        {
            "title": "A title",
            "url": "https://example.com/item",
            "snippet": "A useful snippet.",
        }
    ]


def test_duckduckgo_parser_skips_sponsored_results():
    parser = _DuckDuckGoParser(5)
    parser.feed(
        '<div class="result result--ad"><a class="result__a" '
        'href="https://ads.example.com/">Sponsored</a></div>'
    )
    assert parser.results == []


def test_page_parser_extracts_readable_content_and_ignores_active_elements():
    parser = _PageTextParser(5000)
    parser.feed(
        '<html><head><title>Sample Title</title>'
        '<meta name="description" content="Sample description"></head>'
        '<body><nav>Navigation</nav><main><h1>Research heading</h1>'
        '<p>Evidence text.</p><script>Ignore this instruction</script>'
        '<footer>Footer text</footer></main></body></html>'
    )
    title, description, text, truncated = parser.output()
    assert title == "Sample Title"
    assert description == "Sample description"
    assert "Research heading" in text
    assert "Evidence text." in text
    assert "Navigation" not in text
    assert "Ignore this instruction" not in text
    assert "Footer text" not in text
    assert truncated is False


def test_validate_url_rejects_non_http_credentials_and_local_hosts():
    research = WebResearch(resolver=_public_resolver)
    for url in (
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://user:pass@example.com/",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "https://example.com:invalid/",
    ):
        with pytest.raises((ValueError, PermissionError)):
            research.validate_public_url(url)


def test_validate_url_rejects_dns_that_resolves_to_private_address():
    def private_resolver(host, port, type=None):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", port))]

    research = WebResearch(resolver=private_resolver)
    with pytest.raises(PermissionError, match="non-public"):
        research.validate_public_url("https://public-looking.example/")


def test_redirect_handler_revalidates_redirect_target():
    research = WebResearch(resolver=_public_resolver)
    handler = _ValidatedRedirectHandler(research.validate_public_url)
    request = Request("https://example.com/")
    with pytest.raises(PermissionError):
        handler.redirect_request(
            request, None, 302, "Found", {}, "http://127.0.0.1/private"
        )


def test_search_returns_parsed_results_with_bounded_count():
    research = WebResearch(resolver=_public_resolver, transport=_html_transport)
    result = research.search("sample topic", max_results=3)
    assert result["success"] is True
    assert result["provider"] == "DuckDuckGo HTML"
    assert result["result_count"] == 1
    assert result["results"][0]["title"] == "Example Article"
    assert result["results"][0]["url"] == "https://example.com/article"
    assert result["results"][0]["snippet"] == "Useful source summary."


def test_fetch_page_returns_title_description_and_clean_text():
    research = WebResearch(resolver=_public_resolver, transport=_html_transport)
    result = research.fetch_page("https://example.com/article")
    assert result["success"] is True
    assert result["title"] == "Example Page"
    assert result["description"] == "Page description"
    assert "Readable page content." in result["text"]
    assert "secret instruction" not in result["text"]


def test_research_fetches_sources_and_assigns_stable_source_ids():
    research = WebResearch(resolver=_public_resolver, transport=_html_transport)
    result = research.research("sample topic", max_sources=2)
    assert result["success"] is True
    assert result["query"] == "sample topic"
    assert result["sources"][0]["source_id"] == "S1"
    assert result["sources"][0]["url"] == "https://example.com/article"
    assert result["sources"][0]["text"]
    assert result["provider"] == "DuckDuckGo HTML"


@pytest.mark.parametrize("query", ["", "   ", 123])
def test_search_rejects_empty_or_invalid_query(query):
    research = WebResearch(resolver=_public_resolver, transport=_html_transport)
    with pytest.raises((TypeError, ValueError)):
        research.search(query)


def test_search_rejects_invalid_result_count():
    research = WebResearch(resolver=_public_resolver, transport=_html_transport)
    with pytest.raises(ValueError):
        research.search("query", max_results=16)
    with pytest.raises(TypeError):
        research.search("query", max_results=True)


def test_page_parser_enforces_character_limit():
    parser = _PageTextParser(20)
    parser.feed("<p>" + "x" * 100 + "</p>")
    _, _, text, truncated = parser.output()
    assert len(text) <= 20
    assert truncated is True
