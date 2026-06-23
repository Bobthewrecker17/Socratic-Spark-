import re

FORBIDDEN_PHRASES = [
    r"the answer is",
    r"this means that",
    r"in summary",
    r"to summarize",
    r"\btherefore\b",
    r"thus the answer",
]
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_forbidden_compiled = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PHRASES]

RETRY_SUFFIX = (
    "\n\nYour previous response failed validation. "
    "You MUST end with a question and must not state answers directly."
)

FALLBACK = "Interesting — what do you think about that based on what you've read?"


def validate_response(text: str) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    """
    stripped = text.strip()
    if not stripped.endswith("?"):
        return False, "Response does not end with a question mark."

    for pattern in _forbidden_compiled:
        if pattern.search(stripped):
            return False, f"Response contains forbidden phrase matching: {pattern.pattern}"

    if URL_PATTERN.search(stripped):
        return False, "Response contains a URL."

    return True, ""


async def validated_completion(
    make_completion,
    system_prompt: str,
    messages: list[dict],
    max_retries: int = 2,
) -> tuple[str, int]:
    """
    Calls make_completion(system_prompt, messages) up to max_retries+1 times.
    Returns (final_text, retry_count).
    make_completion is an async callable.
    """
    current_system = system_prompt
    retries = 0

    for attempt in range(max_retries + 1):
        text = await make_completion(current_system, messages)
        valid, reason = validate_response(text)
        if valid:
            return text, retries
        retries = attempt + 1
        current_system = system_prompt + RETRY_SUFFIX

    return FALLBACK, retries
