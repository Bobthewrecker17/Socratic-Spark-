import os
import re
import chromadb
from chromadb.config import Settings

_chroma_client = None
_collection = None

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "curriculum"
CHUNK_SIZE = 300  # approximate words per chunk
CHUNK_OVERLAP = 50  # words of overlap


def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
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


async def ingest_curriculum(
    content: bytes,
    filename: str,
    subject: str,
    session_id: str,
) -> int:
    """Ingest curriculum text or PDF, chunk it, and store in ChromaDB. Returns chunk count."""
    if filename.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(content)
    else:
        text = content.decode("utf-8", errors="replace")

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    chunks = _chunk_text(text)
    collection = get_collection()

    ids = [f"{session_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"subject": subject, "chunk_index": i, "session_id": session_id}
        for i in range(len(chunks))
    ]

    # Delete any existing chunks for this session so re-upload replaces them
    try:
        existing = collection.get(where={"session_id": session_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


async def retrieve_context(query: str, session_id: str, n_results: int = 5) -> list[str]:
    """Retrieve top-n relevant chunks for the given query within the session's curriculum."""
    collection = get_collection()
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"session_id": session_id},
        )
        docs = results.get("documents", [[]])[0]
        return docs
    except Exception:
        return []
