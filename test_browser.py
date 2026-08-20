import os

import pytest


if not os.getenv("AIOS_RUN_BROWSER_TESTS"):
    pytest.skip(
        "Browser integration script requires AIOS_RUN_BROWSER_TESTS=1",
        allow_module_level=True,
    )

from tools.browser import browser


# Open a website
result = browser.open(
    "https://www.google.com"
)

print("\nOPEN:")
print(result)


# Search
result = browser.search(
    "Dentist websites"
)

print("\nSEARCH:")
print(result)


# Extract page text
text = browser.extract_text()

print("\nPAGE TEXT:")
print(text[:1000])


# Extract links
links = browser.extract_links()

print("\nLINKS FOUND:")
print(len(links))

for link in links[:10]:
    print(
        link["text"],
        "->",
        link["href"]
    )


# Close browser
input("\nPress ENTER to close the browser...")

browser.close()
