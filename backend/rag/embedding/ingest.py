"""
ingest.py — Takes scraped JSON and loads it into ChromaDB with embeddings.

Usage:
    python -m rag.embedding.ingest --file data/statutes.json
    python -m rag.embedding.ingest --file data/statutes.json --classify-empty
"""
import json
import sys
import os
import argparse
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from rag.retrieval.store import add_statutes
from rag.embedding.classifier import classify_batch, CONTRIBUTING_FACTORS


def adapt_record(record: dict) -> dict | None:
    """
    Convert one scraped JSON record into ChromaDB format.

    Input format (new scraper):
        citation, section_number, statute_language, complete_statute,
        source_url, contributing_factor (string), state, state_abbrev
    """
    # New format uses "statute_language" as the text field
    text = record.get("statute_language", "").strip()

    if not text or len(text) < 30:
        return None

    # contributing_factor is already a string in new format
    primary_factor = record.get("contributing_factor", "").strip()

    # Validate against our 17 categories
    if primary_factor and primary_factor not in CONTRIBUTING_FACTORS:
        primary_factor = ""

    # Build unique ID from state_abbrev + section_number
    state_abbrev = record.get("state_abbrev", "XX")
    section      = record.get("section_number", "")
    record_id    = f"{state_abbrev.lower()}-{section.replace('.', '').replace('(', '').replace(')', '').replace(' ', '')}"

    return {
        "id":   record_id,
        "text": text,
        "metadata": {
            "statute":             record.get("citation", ""),
            "state":               record.get("state", ""),
            "universal_citation":  record.get("citation", "").split("§")[0].strip(),
            "section":             section,
            "complete_statute":    record.get("complete_statute", ""),
            "contributing_factor": primary_factor,
            "source_url":          record.get("source_url", ""),
            "state_abbrev":        state_abbrev,
        },
    }


def ingest(filepath: str, classify_empty: bool = False) -> None:
    """
    Load a JSON file of scraped statutes into ChromaDB.

    Args:
        filepath:       path to JSON file from any scraper
        classify_empty: if True, auto-classify records missing contributing_factor
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    # Handle wrapper key — file has {"records": [...], "completed": ...}
    records = data["records"] if isinstance(data, dict) else data

    records = records[:20]

    print(f"Loaded {len(records)} records from {filepath}")

    adapted = []
    skipped = 0
    needs_classification = 0

    for record in records:
        result = adapt_record(record)
        if result is None:
            skipped += 1
            continue
        if not result["metadata"]["contributing_factor"]:
            needs_classification += 1
        adapted.append(result)

    print(f"  Valid:   {len(adapted)}")
    print(f"  Skipped: {skipped} (no text or too short)")
    print(f"  Missing contributing_factor: {needs_classification}")

    if classify_empty and needs_classification > 0:
        print(f"\nClassifying {needs_classification} records with Claude...")
        adapted = classify_batch(adapted)
    elif needs_classification > 0:
        print(f"  Tip: rerun with --classify-empty to auto-classify these")

    print(f"\nEmbedding + storing {len(adapted)} statutes in ChromaDB...")
    add_statutes(adapted)
    print(f"Done.")

    # Summary
    states = Counter(r["metadata"]["state"] for r in adapted)
    factors = Counter(
        r["metadata"]["contributing_factor"]
        for r in adapted
        if r["metadata"]["contributing_factor"]
    )
    print(f"\nStates:  {dict(states)}")
    print(f"Top factors: {dict(factors.most_common(5))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to scraped JSON file")
    parser.add_argument("--classify-empty", action="store_true",
                        help="Auto-classify records missing contributing_factor using Claude")
    args = parser.parse_args()

    ingest(filepath=args.file, classify_empty=args.classify_empty)

    # filepath = os.path.join(os.path.dirname(__file__), "..", "..", "data", "statutes.json")
    # ingest(filepath=filepath, classify_empty=True)

