import re
import httpx
from urllib.parse import urlparse, urlencode
from bs4 import BeautifulSoup

TIMEOUT = 15
MAX_BYTES = 3_000_000  # 3 MB cap

# Realistic browser headers to avoid bot-detection blocks
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

FRIENDLY_ERRORS = {
    400: "The URL returned a bad request error.",
    401: "That page requires a login — we can't access it.",
    403: "That site is blocking automated access (403 Forbidden). Try copying the text into a .txt file and uploading it instead.",
    404: "Page not found (404). Double-check the URL.",
    429: "That site is rate-limiting requests. Try again in a moment.",
    500: "The website returned a server error. Try a different URL.",
    503: "That website is currently unavailable.",
}

CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".content",
    ".article-body",
    ".post-content",
    ".entry-content",
    "#content",
    "#main-content",
    ".mw-parser-output",  # Wikipedia
]


def _is_wikipedia(url: str) -> bool:
    return "wikipedia.org/wiki/" in url


async def _fetch_wikipedia(url: str) -> tuple[str, str | None]:
    """Use Wikipedia's public API to get clean article text."""
    path = urlparse(url).path  # /wiki/Photosynthesis
    title = path.split("/wiki/")[-1]
    lang = urlparse(url).hostname.split(".")[0]  # en, fr, etc.

    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "titles": title.replace("_", " "),
        "format": "json",
        "redirects": True,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            res = await client.get(api_url, params=params)
        data = res.json()
        pages = data.get("query", {}).get("pages", {})
        page = next(iter(pages.values()))
        if "missing" in page:
            return "", "Wikipedia article not found. Check the URL."
        text = page.get("extract", "").strip()
        if not text:
            return "", "Could not extract text from that Wikipedia article."
        return text, None
    except Exception as e:
        return "", f"Failed to fetch Wikipedia article: {e}"


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "noscript", "iframe", "form", "button",
                     "[class*='cookie']", "[class*='banner']", "[id*='cookie']"]):
        tag.decompose()

    # Try to find the main content area first
    for selector in CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container:
            text = container.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text

    # Fallback: full body text
    body = soup.find("body")
    if body:
        return body.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


def _clean_text(text: str) -> str:
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse whitespace within lines
    lines = [" ".join(ln.split()) for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


async def fetch_url_as_text(url: str) -> tuple[str, str | None]:
    """
    Returns (text_content, error_message).
    On success: (text, None). On failure: ("", friendly_error).
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Use Wikipedia API for Wikipedia articles — much cleaner results
    if _is_wikipedia(url):
        return await _fetch_wikipedia(url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=TIMEOUT,
            headers=BROWSER_HEADERS,
        ) as client:
            response = await client.get(url)

        if response.status_code != 200:
            msg = FRIENDLY_ERRORS.get(
                response.status_code,
                f"The page returned status {response.status_code} — we can't access it.",
            )
            return "", msg

        raw = response.content[:MAX_BYTES]
        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type:
            return "", (
                "That URL points to a PDF file. "
                "Please download it and upload it using the 'Upload File' tab instead."
            )

        text = raw.decode("utf-8", errors="replace")

        if "html" in content_type or text.lstrip().startswith("<"):
            text = _extract_text_from_html(text)

        text = _clean_text(text)

        if len(text) < 150:
            return "", (
                "We reached the page but couldn't extract enough readable text. "
                "The site may require JavaScript or a login. "
                "Try copying the text manually into a .txt file and uploading it instead."
            )

        return text, None

    except httpx.TimeoutException:
        return "", (
            f"Request timed out after {TIMEOUT}s. "
            "The site may be slow or blocking access."
        )
    except httpx.TooManyRedirects:
        return "", "The URL redirected too many times — it may be a login wall or redirect loop."
    except httpx.RequestError as e:
        return "", f"Could not connect to that URL ({type(e).__name__}). Check the URL and try again."
