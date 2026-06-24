import os
import re
import math
from collections import defaultdict

CHUNK_SIZE = 300  # approximate words per chunk
CHUNK_OVERLAP = 50  # words of overlap

# In-memory store: session_id -> list of chunk strings
_store: dict[str, list[str]] = {}


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    import PyPDF2
    import io

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_scores(query: str, chunks: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Lightweight BM25 scoring with no external dependencies."""
    tokenized_chunks = [_tokenize(c) for c in chunks]
    query_terms = _tokenize(query)
    avg_dl = sum(len(c) for c in tokenized_chunks) / max(len(tokenized_chunks), 1)

    # Document frequency per term
    df: dict[str, int] = defaultdict(int)
    for tc in tokenized_chunks:
        for term in set(tc):
            df[term] += 1

    N = len(tokenized_chunks)
    scores = []
    for tc in tokenized_chunks:
        dl = len(tc)
        tf_map: dict[str, int] = defaultdict(int)
        for term in tc:
            tf_map[term] += 1

        score = 0.0
        for term in query_terms:
            if term not in df:
                continue
            idf = math.log((N - df[term] + 0.5) / (df[term] + 0.5) + 1)
            tf = tf_map[term]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avg_dl)
            score += idf * numerator / denominator
        scores.append(score)
    return scores


async def ingest_curriculum(
    content: bytes,
    filename: str,
    subject: str,
    session_id: str,
) -> int:
    """Ingest curriculum text or PDF, chunk it, and store in memory. Returns chunk count."""
    if filename.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(content)
    else:
        text = content.decode("utf-8", errors="replace")

    text = re.sub(r"\s+", " ", text).strip()
    chunks = _chunk_text(text)
    _store[session_id] = chunks
    return len(chunks)


async def retrieve_context(query: str, session_id: str, n_results: int = 5) -> list[str]:
    """Retrieve top-n relevant chunks for the given query within the session's curriculum."""
    chunks = _store.get(session_id, [])
    if not chunks:
        return []

    scores = _bm25_scores(query, chunks)
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in ranked[:n_results]]
