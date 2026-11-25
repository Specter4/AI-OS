"""Read-only web research tools for AI-OS.

Search uses DuckDuckGo's no-JavaScript HTML results page. Page retrieval is
bounded, public-URL-only, and read-only. All retrieved text is untrusted data.
"""
from __future__ import annotations

import html
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from typing import Any, Callable

SEARCH_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = "AI-OS-WebResearch/1.0 (+read-only research)"
_MAX_SEARCH_RESULTS = 15
_MAX_PAGE_CHARS = 25_000
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_SEARCH_BYTES = 1_500_000


class WebResearchError(RuntimeError):
    """A search or page retrieval failed safely."""


def _clean_text(value: str) -> str:
    return " ".join(html.unescape(value).split())


def _unwrap_ddg_redirect(href: str) -> str:
    candidate = urljoin("https://duckduckgo.com/", href)
    parsed = urlparse(candidate)
    if parsed.hostname == "duckduckgo.com" and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return target
    return candidate


class _DuckDuckGoParser(HTMLParser):
    """Parse semantic classes from DDG's static HTML results."""

    def __init__(self, max_results: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_results = max_results
        self.results: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.result_div_depth = 0
        self.capture: str | None = None
        self.capture_tag: str | None = None
        self.capture_depth = 0
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "div" and "result" in classes and self.current is None:
            if "result--ad" in classes or "result--sponsored" in classes:
                self.current = {"_skip": "1"}
            else:
                self.current = {"title": "", "url": "", "snippet": ""}
            self.result_div_depth = 1
            return
        if self.current is None:
            return
        if tag == "div":
            self.result_div_depth += 1
        if tag == "a" and "result__a" in classes:
            self.current["url"] = _unwrap_ddg_redirect(values.get("href") or "")
            self.capture = "title"
            self.capture_tag = "a"
            self.capture_depth = 0
        elif "result__snippet" in classes:
            self.capture = "snippet"
            self.capture_tag = tag
            self.capture_depth = 0
        if self.capture is not None and tag != self.capture_tag:
            self.capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if self.capture is not None:
            if tag == self.capture_tag and self.capture_depth == 0:
                self.capture = None
                self.capture_tag = None
            elif self.capture_depth > 0:
                self.capture_depth -= 1
        if tag == "div":
            self.result_div_depth -= 1
            if self.result_div_depth <= 0:
                self._finish_result()

    def handle_data(self, data: str) -> None:
        if self.current is None or self.capture is None or self.current.get("_skip"):
            return
        self.current[self.capture] = self.current.get(self.capture, "") + data

    def _finish_result(self) -> None:
        item = self.current
        self.current = None
        self.result_div_depth = 0
        self.capture = None
        self.capture_tag = None
        if not item or item.get("_skip"):
            return
        title = _clean_text(item.get("title", ""))
        url = item.get("url", "").strip()
        snippet = _clean_text(item.get("snippet", ""))
        if not title or not url or url in self._seen:
            return
        self._seen.add(url)
        self.results.append({"title": title, "url": url, "snippet": snippet})


class _PageTextParser(HTMLParser):
    """Extract readable text while discarding active and non-content elements."""

    _ignored = {"script", "style", "noscript", "svg", "canvas", "iframe", "nav", "footer", "header", "aside", "form", "template"}
    _blocks = {"p", "div", "section", "article", "main", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr"}

    def __init__(self, max_chars: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_chars = max_chars
        self.title_parts: list[str] = []
        self.description = ""
        self.parts: list[str] = []
        self.length = 0
        self.ignored_stack: list[str] = []
        self.in_title = False
        self.truncated = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag in self._ignored:
            self.ignored_stack.append(tag)
            return
        if self.ignored_stack:
            return
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.description:
                self.description = _clean_text(values.get("content", ""))
        if tag in self._blocks:
            self._append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.ignored_stack:
            if tag == self.ignored_stack[-1]:
                self.ignored_stack.pop()
            return
        if tag == "title":
            self.in_title = False
        if tag in self._blocks:
            self._append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_stack:
            return
        if self.in_title:
            self.title_parts.append(data)
        else:
            self._append(data)

    def _append(self, text: str) -> None:
        if self.length >= self.max_chars:
            self.truncated = True
            return
        remaining = self.max_chars - self.length
        piece = text[:remaining]
        self.parts.append(piece)
        self.length += len(piece)
        if len(text) > remaining:
            self.truncated = True

    def output(self) -> tuple[str, str, str, bool]:
        title = _clean_text(" ".join(self.title_parts))
        body = _clean_text(" ".join(self.parts))
        return title, self.description, body, self.truncated


def _is_global_address(address: str) -> bool:
    try:
        return ipaddress.ip_address(address.split("%", 1)[0]).is_global
    except ValueError:
        return False


class _ValidatedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validate: Callable[[str], str]) -> None:
        super().__init__()
        self.validate = validate

    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str):
        safe_url = self.validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


class WebResearch:
    """Public web search and bounded webpage extraction."""

    def __init__(
        self,
        *,
        timeout: float = 12.0,
        resolver: Callable[..., Any] | None = None,
        transport: Callable[[str, float, int], tuple[bytes, str, str]] | None = None,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= float(timeout) <= 30:
            raise ValueError("timeout must be between 1 and 30 seconds")
        self.timeout = float(timeout)
        self._resolver = resolver or socket.getaddrinfo
        self._transport = transport or self._urllib_transport

    def validate_public_url(self, url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("A non-empty URL is required")
        value = url.strip()
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only absolute HTTP or HTTPS URLs are supported")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URLs must not contain embedded credentials")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("URL contains an invalid port") from exc
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
            raise PermissionError("Local or reserved hostnames are not permitted for web research")
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            try:
                addresses = self._resolver(host, port or (443 if parsed.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
            except OSError as exc:
                raise WebResearchError(f"Could not resolve public host: {host}") from exc
            resolved = {item[4][0] for item in addresses}
            if not resolved or not all(_is_global_address(address) for address in resolved):
                raise PermissionError("Host resolves to a non-public address")
        else:
            if not literal.is_global:
                raise PermissionError("Non-public IP addresses are not permitted for web research")
        return value

    def _urllib_transport(self, url: str, timeout: float, max_bytes: int) -> tuple[bytes, str, str]:
        opener = build_opener(_ValidatedRedirectHandler(self.validate_public_url))
        request = Request(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
                "Accept-Language": "en-US,en;q=0.8",
            },
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                final_url = self.validate_public_url(response.geturl())
                content_type = response.headers.get_content_type().lower()
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise WebResearchError("Web response exceeded the configured size limit")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise WebResearchError("Web response exceeded the configured size limit")
                return body, final_url, content_type
        except HTTPError as exc:
            raise WebResearchError(f"Web server returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise WebResearchError(f"Could not retrieve webpage: {exc.reason}") from exc
        except TimeoutError as exc:
            raise WebResearchError("Web request timed out") from exc

    def _get(self, url: str, *, max_bytes: int) -> tuple[bytes, str, str]:
        safe_url = self.validate_public_url(url)
        body, final_url, content_type = self._transport(safe_url, self.timeout, max_bytes)
        final_url = self.validate_public_url(final_url)
        if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise WebResearchError(f"Unsupported webpage content type: {content_type}")
        if len(body) > max_bytes:
            raise WebResearchError("Web response exceeded the configured size limit")
        return body, final_url, content_type

    @staticmethod
    def _validate_query(query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Research query must be a non-empty string")
        query = query.strip()
        if len(query) > 1000:
            raise ValueError("Research query cannot exceed 1000 characters")
        return query

    @staticmethod
    def _validate_count(value: int, *, name: str, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if not 1 <= value <= maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}")
        return value

    def search(self, query: str, max_results: int = 8) -> dict[str, Any]:
        query = self._validate_query(query)
        max_results = self._validate_count(max_results, name="max_results", maximum=_MAX_SEARCH_RESULTS)
        search_url = SEARCH_URL + "?" + urlencode({"q": query})
        body, final_url, _ = self._get(search_url, max_bytes=_MAX_SEARCH_BYTES)
        html_text = body.decode("utf-8", errors="replace")
        if "anomaly" in html_text[:10000].lower() and 'result__a' not in html_text:
            raise WebResearchError("Search provider returned an anti-bot or challenge page")
        parser = _DuckDuckGoParser(max_results)
        parser.feed(html_text)
        # Do not surface malformed, credential-bearing, or non-public result
        # destinations even when the search provider returns them.
        results: list[dict[str, str]] = []
        for item in parser.results:
            try:
                self.validate_public_url(item["url"])
            except (ValueError, PermissionError, WebResearchError):
                continue
            results.append(item)
            if len(results) >= max_results:
                break
        return {
            "success": True,
            "query": query,
            "provider": "DuckDuckGo HTML",
            "search_url": final_url,
            "result_count": len(results),
            "results": results,
        }

    def fetch_page(self, url: str, max_chars: int = 12_000) -> dict[str, Any]:
        max_chars = self._validate_count(max_chars, name="max_chars", maximum=_MAX_PAGE_CHARS)
        if max_chars < 1000:
            raise ValueError("max_chars must be at least 1000")
        body, final_url, content_type = self._get(url, max_bytes=_MAX_RESPONSE_BYTES)
        parser = _PageTextParser(max_chars)
        if content_type == "text/plain":
            parser._append(body.decode("utf-8", errors="replace"))
        else:
            parser.feed(body.decode("utf-8", errors="replace"))
        title, description, text, truncated = parser.output()
        if not text and not description:
            raise WebResearchError("No readable text could be extracted from the page")
        return {
            "success": True,
            "title": title or final_url,
            "url": final_url,
            "description": description,
            "text": text,
            "truncated": truncated,
        }

    def research(self, query: str, max_sources: int = 5, page_chars: int = 10_000) -> dict[str, Any]:
        query = self._validate_query(query)
        max_sources = self._validate_count(max_sources, name="max_sources", maximum=8)
        page_chars = self._validate_count(page_chars, name="page_chars", maximum=15_000)
        if page_chars < 1000:
            raise ValueError("page_chars must be at least 1000")
        search = self.search(query, max_results=min(_MAX_SEARCH_RESULTS, max_sources * 2))
        sources: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        seen: set[str] = set()
        total_chars = 0
        total_budget = 45_000
        for item in search["results"]:
            if len(sources) >= max_sources or total_chars >= total_budget:
                break
            url = item["url"]
            if url in seen:
                continue
            seen.add(url)
            try:
                page = self.fetch_page(url, max_chars=min(page_chars, total_budget - total_chars))
            except (WebResearchError, ValueError, PermissionError) as exc:
                errors.append({"url": url, "error": str(exc)[:300]})
                continue
            source_id = f"S{len(sources) + 1}"
            source = {
                "source_id": source_id,
                "title": page["title"] or item["title"],
                "url": page["url"],
                "search_snippet": item["snippet"],
                "description": page["description"],
                "text": page["text"],
                "truncated": page["truncated"],
            }
            sources.append(source)
            total_chars += len(source["text"])
        return {
            "success": bool(sources),
            "query": query,
            "provider": search["provider"],
            "search_result_count": search["result_count"],
            "sources": sources,
            "source_errors": errors,
        }


web_research = WebResearch()

__all__ = ["WebResearch", "WebResearchError", "web_research"]
