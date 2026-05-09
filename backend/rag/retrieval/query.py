"""
query.py — Converts an attorney's query into an embedding and searches ChromaDB.

This is the RAG query side. Called by the agent at question time.
Sits at: backend/rag/retrieval/query.py

How it works:
    1. Attorney types a question
    2. We embed the question using the same model used at ingestion time
    3. ChromaDB finds the most similar statute embeddings
    4. We return the top matches with metadata

The embedding model (all-MiniLM-L6-v2) is the same for both:
    - ingestion (storing statutes)
    - query     (searching statutes)
They MUST match — otherwise similarity search breaks.

Usage:
    from rag.retrieval.query import query_rag
    results = query_rag("What is the DUI statute in Texas?")
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag.retrieval.store import search, get_by_factor, get_by_citation, count
from ingestion.citation_normalizer import normalize


def query_rag(
    question: str,
    state: str | None = None,
    contributing_factor: str | None = None,
    n_results: int = 5,
) -> list[dict]:
    """
    Main RAG query function.

    Takes a natural language question, embeds it, finds the most
    relevant statutes in ChromaDB, returns them with metadata.

    Args:
        question:            attorney's natural language query
        state:               optional filter e.g. "Texas"
        contributing_factor: optional filter e.g. "DUI/DWI"
        n_results:           how many statutes to return

    Returns:
        list of dicts, each with:
            id, text, metadata, distance
            where distance is cosine distance (lower = more similar)
    """
    if count() == 0:
        print("WARNING: ChromaDB is empty. Run ingest.py first.")
        return []

    # ChromaDB handles the embedding internally using the same
    # model (all-MiniLM-L6-v2) that was used during ingestion
    results = search(
        query=question,
        n_results=n_results,
        state=state,
        contributing_factor=contributing_factor,
    )

    return results


def query_by_citation(raw_citation: str) -> dict | None:
    """
    Look up a statute by citation — handles fuzzy/malformed input.

    e.g. "CVC 21451" → finds Cal. Veh. Code § 21451
    """
    # First try exact match
    result = get_by_citation(raw_citation)
    if result:
        return result

    # Normalize and try again
    normalized = normalize(raw_citation)
    return get_by_citation(normalized["canonical"])


def query_by_factor(
    contributing_factor: str,
    state: str | None = None,
) -> list[dict]:
    """
    Get all statutes for a contributing factor category.

    e.g. factor="DUI/DWI", state="Texas"
    """
    return get_by_factor(
        contributing_factor=contributing_factor,
        state=state,
    )


def format_for_prompt(results: list[dict]) -> str:
    """
    Format RAG results into a string for the LLM prompt.
    This is what gets injected into the prompt template.
    """
    if not results:
        return "No relevant statutes found in the database."

    formatted = []
    for i, r in enumerate(results):
        m = r["metadata"]
        formatted.append(
            f"[{i+1}] {m.get('statute', '')}\n"
            f"State: {m.get('state', '')}\n"
            f"Contributing Factor: {m.get('contributing_factor', '')}\n"
            f"Text: {r['text'][:400]}\n"
            f"Source: {m.get('source_url', '')}"
        )
    return "\n\n".join(formatted)


# ── Quick manual test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Statutes in DB: {count()}")
    if count() == 0:
        print("Run ingest.py first")
        sys.exit(0)

    test_queries = [
        ("What is the DUI law in Texas?",            "Texas",  None),
        ("running a red light",                       None,     "Failure to Obey Traffic Control Device"),
        ("texting while driving",                     None,     None),
        ("CVC 23152",                                 None,     None),  # fuzzy citation
    ]

    for question, state, factor in test_queries:
        print(f"\n{'='*50}")
        print(f"Query:  {question}")
        print(f"State:  {state}  |  Factor: {factor}")
        print(f"{'='*50}")

        if "CVC" in question or "§" in question:
            result = query_by_citation(question)
            results = [result] if result else []
        else:
            results = query_rag(question, state=state, contributing_factor=factor)

        print(format_for_prompt(results))
