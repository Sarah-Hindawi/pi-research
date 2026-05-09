"""
store.py — ChromaDB wrapper. Handles embedding + storage + search.

Uses free local sentence-transformers — no API key needed for embedding.
"""
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import get_settings

settings = get_settings()
COLLECTION_NAME = "statutes"

# Free local embeddings — no API key, runs on CPU
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
    """Embed and store statutes. Each must have id, text, metadata."""
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
    Semantic search with optional filters.
    Returns list of {id, text, metadata, distance}.
    """
    collection = _get_collection()

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
    return [
        {
            "id":       results["ids"][0][i],
            "text":     results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        }
        for i in range(len(results["ids"][0]))
    ]


def get_by_citation(citation: str) -> dict | None:
    """Exact citation lookup e.g. 'Cal. Veh. Code § 22350'"""
    collection = _get_collection()
    results = collection.query(
        query_texts=[citation],
        n_results=1,
        where={"statute": {"$eq": citation}},
    )
    if not results["ids"][0]:
        return None
    return {
        "id":       results["ids"][0][0],
        "text":     results["documents"][0][0],
        "metadata": results["metadatas"][0][0],
    }


def get_by_factor(contributing_factor: str, state: str | None = None) -> list[dict]:
    """Get all statutes for a contributing factor."""
    return search(
        query=contributing_factor,
        n_results=20,
        state=state,
        contributing_factor=contributing_factor,
    )


def list_states() -> list[str]:
    collection = _get_collection()
    results = collection.get(include=["metadatas"])
    return sorted(set(m.get("state", "") for m in results["metadatas"] if m.get("state")))


def list_factors() -> list[str]:
    collection = _get_collection()
    results = collection.get(include=["metadatas"])
    return sorted(set(m.get("contributing_factor", "") for m in results["metadatas"] if m.get("contributing_factor")))


def count() -> int:
    return _get_collection().count()
