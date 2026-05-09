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

    Handles two input shapes:
      1. Colleague's scraper format (statute_text, contributing_factors as list)
      2. Seed CSV format (Statute Language, Contributing Factor as string)
    """
    # Try colleague's scraper format first
    text = record.get("statute_text", "").strip()

    # Fallback to seed CSV format
    if not text:
        text = record.get("Statute Language", "").strip()

    if not text or len(text) < 30:
        return None

    # contributing_factors is a list in scraper format
    factors = record.get("contributing_factors", [])
    if isinstance(factors, list):
        primary_factor = factors[0] if factors else ""
    else:
        primary_factor = str(factors)

    # Fallback for seed CSV format
    if not primary_factor:
        primary_factor = record.get("Contributing Factor", "")

    # Validate against our 17 categories
    if primary_factor and primary_factor not in CONTRIBUTING_FACTORS:
        primary_factor = ""

    # Build unique ID
    record_id = (
        record.get("id")
        or f"{record.get('state_abbrev', 'XX').lower()}-{record.get('section_number', '').replace('.', '').replace('(', '').replace(')', '')}"
    )

    return {
        "id":   record_id,
        "text": text,
        "metadata": {
            "statute":             record.get("citation") or record.get("Statute", ""),
            "state":               record.get("state") or record.get("State", ""),
            "universal_citation":  (record.get("citation", "") or "").split("§")[0].strip(),
            "section":             record.get("section_number") or record.get("Section #", ""),
            "complete_statute":    record.get("complete_statute") or f"Pursuant to {record.get('citation', '')}, \"{text[:300]}\"",
            "contributing_factor": primary_factor,
            "source_url":          record.get("official_url") or record.get("source_url", ""),
            "title":               record.get("title", ""),
            "chapter_name":        record.get("chapter_name", ""),
            "violation_type":      record.get("violation_type", ""),
            "severity":            record.get("severity", ""),
            "state_abbrev":        record.get("state_abbrev", ""),
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
        records = json.load(f)

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
    print(f"  Skipped: {skipped} (no text)")
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
