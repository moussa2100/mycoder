"""Web fetch tool — fetches URLs and converts content to clean markdown."""

from __future__ import annotations

import httpx
from langchain_core.tools import tool
from markdownify import markdownify


@tool(parse_docstring=True)
def web_fetch(url: str, timeout: float = 15.0) -> str:
    """Fetch a webpage and return its content converted to clean markdown.

    Use this tool when the user provides a URL or when you need to read
    the full content of a specific webpage. Returns the page body as
    markdown so it is easy to read and quote from.

    Args:
        url: The exact URL to fetch (must start with http:// or https://)
        timeout: Request timeout in seconds (default: 15.0)

    Returns:
        The webpage content as markdown, or an error message if the
        fetch failed.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = httpx.get(
            url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        markdown = markdownify(response.text)
        # Trim excessive blank lines that markdownify sometimes produces
        cleaned = "\n".join(
            line for line in markdown.splitlines() if line.strip() or True
        )
        return cleaned
    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code} fetching {url}: {e}"
    except httpx.TimeoutException:
        return f"Timeout after {timeout}s fetching {url}"
    except Exception as e:
        return f"Error fetching {url}: {e}"
