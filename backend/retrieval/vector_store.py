"""
ChromaDB wrapper — statute-focused schema.
Owner: Yingkai

Schema per statute:
    id:       unique string (e.g. "ca-veh-22350")
    text:     statute language — what gets embedded
    metadata:
        statute             — full citation e.g. "Cal. Veh. Code § 22350"
        state               — "California"
        universal_citation  — "Cal. Veh. Code"
        section             — "22350"
        complete_statute    — full formatted quote
        contributing_factor — one of 17 categories
        source_url          — real URL (required for scoring)
"""
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import get_settings

settings = get_settings()
COLLECTION_NAME = "statutes"

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def _get_collection() -> chromadb.Collection:
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


def add_statutes(statutes: list[dict]) -> None:
    """
    Upsert statutes into ChromaDB.
    Each statute dict must have: id, text, metadata.
    """
    if not statutes:
        return
    collection = _get_collection()
    collection.upsert(
        ids=[s["id"] for s in statutes],
        documents=[s["text"] for s in statutes],
        metadatas=[s["metadata"] for s in statutes],
    )


def search(
    query: str,
    n_results: int = 5,
    state: str | None = None,
    contributing_factor: str | None = None,
) -> list[dict]:
    """
    Semantic search over statutes with optional metadata filters.

    Args:
        query:               natural language query
        n_results:           number of results to return
        state:               filter by state e.g. "California"
        contributing_factor: filter by category e.g. "DUI/DWI"

    Returns:
        list of dicts with keys: id, text, metadata, distance
    """
    collection = _get_collection()

    # Build metadata filter
    where: dict = {}
    conditions = []
    if state:
        conditions.append({"state": {"$eq": state}})
    if contributing_factor:
        conditions.append({"contributing_factor": {"$eq": contributing_factor}})

    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    kwargs: dict = {"query_texts": [query], "n_results": min(n_results, count() or 1)}
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append({
            "id": doc_id,
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return output


def get_by_citation(citation: str) -> dict | None:
    """
    Exact lookup by statute citation string.
    e.g. "Cal. Veh. Code § 22350"
    """
    collection = _get_collection()
    results = collection.query(
        query_texts=[citation],
        n_results=1,
        where={"statute": {"$eq": citation}},
    )
    if not results["ids"][0]:
        return None
    return {
        "id": results["ids"][0][0],
        "text": results["documents"][0][0],
        "metadata": results["metadatas"][0][0],
    }


def get_by_factor(contributing_factor: str, state: str | None = None) -> list[dict]:
    """
    Get all statutes for a contributing factor, optionally filtered by state.
    Used for the eval queries.
    """
    return search(
        query=contributing_factor,
        n_results=20,
        state=state,
        contributing_factor=contributing_factor,
    )


def list_states() -> list[str]:
    """Return all unique states in the DB."""
    collection = _get_collection()
    results = collection.get(include=["metadatas"])
    states = set()
    for m in results["metadatas"]:
        if m.get("state"):
            states.add(m["state"])
    return sorted(states)


def list_factors() -> list[str]:
    """Return all unique contributing factors in the DB."""
    collection = _get_collection()
    results = collection.get(include=["metadatas"])
    factors = set()
    for m in results["metadatas"]:
        if m.get("contributing_factor"):
            factors.add(m["contributing_factor"])
    return sorted(factors)


def count() -> int:
    return _get_collection().count()
