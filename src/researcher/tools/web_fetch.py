"""Web page fetching tool for Strands agents with URL dedup."""

import requests
from strands import tool
from markdownify import markdownify as md
from researcher.config import MAX_CONTENT_LENGTH

# Module-level visited set shared across agent instances within a process
_visited_urls: set[str] = set()


def set_visited_urls(urls: set[str]) -> None:
    """Initialize the visited URLs set from the evidence store."""
    global _visited_urls
    _visited_urls = urls


@tool
def web_fetch(url: str) -> str:
    """Fetch a web page and return its content as markdown. Skips already-visited URLs.

    Args:
        url: The URL to fetch.

    Returns:
        The page content converted to markdown, or a skip notice if already visited.
    """
    global _visited_urls

    if url in _visited_urls:
        return f"SKIPPED: {url} has already been researched. Use a different URL."

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        _visited_urls.add(url)

        content = md(response.text, strip=["img", "script", "style"])
        lines = [line.strip() for line in content.splitlines()]
        content = "\n".join(line for line in lines if line)

        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "\n\n[... content truncated ...]"

        return f"Content from {url}:\n\n{content}"

    except requests.exceptions.Timeout:
        return f"Timeout fetching {url}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching {url}: {e}"
