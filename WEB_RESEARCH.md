# AI-OS Web Research

Phase 9, Step 6 adds read-only public web search and webpage text retrieval.

## Tools

The built-in tool registry exposes:

- `web.search(query, max_results=8)` — ranked search result titles, URLs, and snippets.
- `web.fetch_page(url, max_chars=12000)` — readable text, title, description, final URL, and truncation status for one public HTML/text page.
- `web.research(query, max_sources=5, page_chars=10000)` — search, fetch a bounded set of pages, and return source records labeled `S1`, `S2`, etc.

The implementation uses Python's standard library and DuckDuckGo's static HTML results page. It does not require a search API key or a new package. Search results may be blocked or challenged by the provider; in that case the tool reports failure rather than fabricating results.

## Research agent

`agents.research.research(topic)` retrieves sources before asking the configured LLM to write the report. The report keeps the existing sections:

- Objective
- Key Findings
- Opportunities
- Risks
- Recommended Next Steps
- Sources

Factual claims should cite the retrieved source IDs, such as `[S1]`. The model is instructed not to invent citations or facts, and to disclose when evidence is missing or conflicting.

## Safety boundaries

- Only HTTP and HTTPS URLs are accepted. Embedded credentials, localhost/reserved hostnames, and private/non-global IP addresses are rejected.
- DNS results are checked for non-public addresses and each redirect target is revalidated.
- Requests are GET-only, time-bounded, and size-bounded. Only HTML, XHTML, or plain text is processed.
- Page extraction removes script, style, navigation, footer, form, and other non-content elements.
- Search and retrieval are registered as read-only tools. This step does not click page controls, submit forms, download files, execute code, or use page content as authorization.
- Webpage text and search snippets are untrusted evidence. Prompt-injection text in a page must not be followed as instructions.

These controls reduce risk but do not provide an absolute SSRF guarantee: DNS can change between validation and connection. A future deployment should add network-level egress restrictions for the research process. Source credibility, publication dates, and freshness are not inferred when the page does not provide them.
