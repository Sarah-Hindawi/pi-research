"""
ChromaDB wrapper using free local sentence-transformers embeddings.
"""
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from config import get_settings

settings = get_settings()

COLLECTION_NAME = "pi_cases"

# Free local embeddings
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


def add_cases(cases: list[dict]) -> None:
    """
    Upsert cases into ChromaDB.
    Each case dict must have:
        - id: str (unique, e.g. CanLII citation)
        - text: str (full opinion text to embed)
        - metadata: dict with keys like jurisdiction, year, injury_type,
                    verdict_amount, case_name, url
    """
    collection = _get_collection()
    collection.upsert(
        ids=[c["id"] for c in cases],
        documents=[c["text"] for c in cases],
        metadatas=[c["metadata"] for c in cases],
    )


def search(
    query: str,
    n_results: int = 5,
    jurisdiction: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict]:
    """
    Semantic search over ingested cases.
    Returns list of dicts with keys: id, text, metadata, distance.
    """
    collection = _get_collection()

    where: dict = {}
    if jurisdiction:
        where["jurisdiction"] = {"$eq": jurisdiction}
    if year_min and year_max:
        where["year"] = {"$gte": year_min, "$lte": year_max}
    elif year_min:
        where["year"] = {"$gte": year_min}
    elif year_max:
        where["year"] = {"$lte": year_max}

    kwargs: dict = {"query_texts": [query], "n_results": n_results}
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


def count() -> int:
    return _get_collection().count()
