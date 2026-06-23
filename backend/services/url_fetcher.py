import re
import httpx
from urllib.parse import urlparse
from bs4 import BeautifulSoup

TIMEOUT = 15
MAX_BYTES = 3_000_000

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
    "article", "main", '[role="main"]',
    ".content", ".article-body", ".post-content",
    ".entry-content", "#content", "#main-content",
    ".mw-parser-output",
]

# ── Google helpers ─────────────────────────────────────────────────────────────

def _google_doc_id(url: str) -> str | None:
    """Extract the doc ID from a Google Docs/Slides/Sheets URL."""
    m = re.search(r"/(?:document|presentation|spreadsheets)/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def _is_google_drive_file(url: str) -> bool:
    return "drive.google.com/file/" in url


def _google_drive_id(url: str) -> str | None:
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


async def _fetch_google_doc(url: str) -> tuple[str, str | None]:
    """Export a Google Doc/Slides/Sheets as plain text via the export API."""
    doc_id = _google_doc_id(url)
    if not doc_id:
        return "", "Could not parse the Google document ID from that URL."

    if "presentation" in url:
        # Slides export as plain text (speaker notes + slide text)
        export_url = f"https://docs.google.com/presentation/d/{doc_id}/export/txt"
    elif "spreadsheets" in url:
        export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
    else:
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT) as client:
            res = await client.get(export_url, headers=BROWSER_HEADERS)

        if res.status_code == 401 or res.status_code == 403:
            return "", (
                "That Google document isn't shared publicly. "
                "In Google Docs go to Share → Change to 'Anyone with the link can view', then try again."
            )
        if res.status_code != 200:
            return "", (
                f"Google returned status {res.status_code}. "
                "Make sure the document is shared as 'Anyone with the link can view'."
            )

        text = res.content.decode("utf-8", errors="replace").strip()
        if len(text) < 100:
            return "", (
                "The Google document appears to be empty or inaccessible. "
                "Make sure it's shared publicly and contains text content."
            )
        return _clean_text(text), None

    except Exception as e:
        return "", f"Could not fetch the Google document: {e}"


async def _fetch_google_drive_pdf(url: str) -> tuple[str, str | None]:
    """A Google Drive PDF link — guide the user to download it."""
    return "", (
        "That's a Google Drive PDF link. "
        "To use it: open the file in Drive → click the download button → "
        "then upload it here using the 'Upload File' tab."
    )


# ── Wikipedia ──────────────────────────────────────────────────────────────────

async def _fetch_wikipedia(url: str) -> tuple[str, str | None]:
    path = urlparse(url).path
    title = path.split("/wiki/")[-1]
    lang = urlparse(url).hostname.split(".")[0]
    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query", "prop": "extracts", "explaintext": True,
        "exsectionformat": "plain", "titles": title.replace("_", " "),
        "format": "json", "redirects": True,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            res = await client.get(api_url, params=params)
        pages = res.json().get("query", {}).get("pages", {})
        page = next(iter(pages.values()))
        if "missing" in page:
            return "", "Wikipedia article not found. Check the URL."
        text = page.get("extract", "").strip()
        return (text, None) if text else ("", "Could not extract text from that Wikipedia article.")
    except Exception as e:
        return "", f"Failed to fetch Wikipedia article: {e}"


# ── HTML scraping ──────────────────────────────────────────────────────────────

def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "noscript", "iframe", "form", "button"]):
        tag.decompose()
    for selector in CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container:
            text = container.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text
    body = soup.find("body")
    return (body or soup).get_text(separator="\n", strip=True)


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [" ".join(ln.split()) for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


# ── Known JS-heavy / login-walled sites ────────────────────────────────────────

JS_BLOCKED = {
    "khanacademy.org": "Khan Academy",
    "quizlet.com": "Quizlet",
    "coursehero.com": "Course Hero",
    "chegg.com": "Chegg",
    "canvas.instructure.com": "Canvas LMS",
    "blackboard.com": "Blackboard",
    "moodle": "Moodle",
    "classroom.google.com": "Google Classroom",
}


def _blocked_site_message(url: str) -> str | None:
    for domain, name in JS_BLOCKED.items():
        if domain in url:
            return (
                f"{name} requires a login and blocks automated access. "
                "Copy the text you want to study, paste it into a .txt file, "
                "and upload it using the 'Upload File' tab instead."
            )
    return None


# ── Main entry point ───────────────────────────────────────────────────────────

async def fetch_url_as_text(url: str) -> tuple[str, str | None]:
    """
    Returns (text_content, error_message).
    On success: (text, None). On failure: ("", friendly_error).
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Known blocked sites — fail fast with a helpful message
    blocked_msg = _blocked_site_message(url)
    if blocked_msg:
        return "", blocked_msg

    # Wikipedia — use their API
    if "wikipedia.org/wiki/" in url:
        return await _fetch_wikipedia(url)

    # Google Docs / Slides / Sheets — use the export API
    if "docs.google.com" in url and _google_doc_id(url):
        return await _fetch_google_doc(url)

    # Google Drive PDF link — guide to download
    if _is_google_drive_file(url):
        return await _fetch_google_drive_pdf(url)

    # General HTML page
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=TIMEOUT, headers=BROWSER_HEADERS,
        ) as client:
            response = await client.get(url)

        if response.status_code != 200:
            return "", FRIENDLY_ERRORS.get(
                response.status_code,
                f"The page returned status {response.status_code} — we can't access it.",
            )

        raw = response.content[:MAX_BYTES]
        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type:
            return "", (
                "That URL points to a PDF. "
                "Please download it and upload it using the 'Upload File' tab instead."
            )

        text = raw.decode("utf-8", errors="replace")
        if "html" in content_type or text.lstrip().startswith("<"):
            text = _extract_text_from_html(text)

        text = _clean_text(text)

        if len(text) < 150:
            return "", (
                "We reached the page but couldn't extract enough readable text from it. "
                "The site likely requires JavaScript or a login to show its content. "
                "Try copying the text manually into a .txt file and uploading it instead."
            )

        return text, None

    except httpx.TimeoutException:
        return "", f"Request timed out after {TIMEOUT}s. The site may be slow or blocking access."
    except httpx.TooManyRedirects:
        return "", "The URL redirected too many times — it may be a login wall."
    except httpx.RequestError as e:
        return "", f"Could not connect to that URL ({type(e).__name__}). Check the URL and try again."
