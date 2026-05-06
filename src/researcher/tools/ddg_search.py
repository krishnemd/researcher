"""DuckDuckGo search tool for Strands agents."""

from strands import tool

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


@tool
def ddg_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        Formatted search results with title, URL, and snippet for each result.
    """
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('href', 'No URL')}\n"
                f"    {r.get('body', 'No snippet')}"
            )
        return "\n\n".join(formatted)

    except Exception as e:
        return f"Search error: {e}"
