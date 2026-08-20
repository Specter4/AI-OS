import os

import pytest


if not os.getenv("AIOS_RUN_BROWSER_TESTS"):
    pytest.skip(
        "Browser integration script requires AIOS_RUN_BROWSER_TESTS=1",
        allow_module_level=True,
    )

from agents.browser import browser_agent


print("\n=== TEST 1: OPEN ===")

result = browser_agent.execute(
    "open https://example.com"
)

print(result)


print("\n=== TEST 2: CURRENT PAGE ===")

result = browser_agent.execute(
    "current page"
)

print(result)


print("\n=== TEST 3: EXTRACT TEXT ===")

result = browser_agent.execute(
    "extract page text"
)

print(result)


print("\n=== TEST 4: EXTRACT LINKS ===")

result = browser_agent.execute(
    "extract links"
)

print(result)


input("\nPress ENTER to close the browser...")

from tools.browser import browser

browser.close()
