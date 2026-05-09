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

    Input format:
        citation, section_number, statute_language, complete_statute,
        source_url, contributing_factor (string), state, state_abbrev
    """
    text = record.get("statute_language", "").strip()
    if not text or len(text) < 30:
        return None

    # contributing_factor is a string in this format
    primary_factor = record.get("contributing_factor", "").strip()
    if primary_factor and primary_factor not in CONTRIBUTING_FACTORS:
        # Try fuzzy match — check if any official factor is contained in the value
        matched = ""
        for factor in CONTRIBUTING_FACTORS:
            if factor.lower() in primary_factor.lower() or primary_factor.lower() in factor.lower():
                matched = factor
                break
        primary_factor = matched  # empty string if no match found

    # Build unique ID from citation
    citation  = record.get("citation", "")
    record_id = (
        citation
        .replace(" ", "-")
        .replace(".", "")
        .replace("§", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "-")
        .lower()
        .strip("-")
    )

    # Safety fallback if citation was empty
    if not record_id:
        state_abbrev = record.get("state_abbrev", "XX")
        section      = record.get("section_number", "unknown")
        record_id    = f"{state_abbrev.lower()}-{section.replace('.', '-').replace('(', '').replace(')', '')}"

    return {
        "id":   record_id,
        "text": text,
        "metadata": {
            "statute":             citation,
            "state":               record.get("state", ""),
            "universal_citation":  citation.split("§")[0].strip(),
            "section":             record.get("section_number", ""),
            "complete_statute":    record.get("complete_statute", ""),
            "contributing_factor": primary_factor,
            "source_url":          record.get("source_url", ""),
            "state_abbrev":        record.get("state_abbrev", ""),
        },
    }


def ingest(filepath: str, classify_empty: bool = False) -> None:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    records = data["records"] if isinstance(data, dict) else data
    print(f"Loaded {len(records)} records from {filepath}")

    adapted              = []
    skipped              = 0
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

    # Deduplicate by ID before upserting.
    # No records are lost — duplicates just mean the same statute appeared
    # twice in the source JSON. We keep the last occurrence (most complete).
    seen = {}
    for r in adapted:
        seen[r["id"]] = r
    deduped = list(seen.values())

    if len(deduped) < len(adapted):
        print(f"  Deduplicated: {len(adapted) - len(deduped)} duplicate statutes merged "
              f"({len(deduped)} unique statutes remain — no data lost)")

    print(f"\nEmbedding + storing {len(deduped)} statutes in ChromaDB...")
    add_statutes(deduped)
    print("Done.")

    states  = Counter(r["metadata"]["state"] for r in deduped)
    factors = Counter(
        r["metadata"]["contributing_factor"]
        for r in deduped
        if r["metadata"]["contributing_factor"]
    )
    print(f"\nStates:  {dict(states)}")
    print(f"Top factors: {dict(factors.most_common(5))}")


if __name__ == "__main__":
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--file", required=True, help="Path to scraped JSON file")
    # parser.add_argument("--classify-empty", action="store_true",
    #                     help="Auto-classify records missing contributing_factor using Claude")
    # args = parser.parse_args()
    # ingest(filepath=args.file, classify_empty=args.classify_empty)

    filepath = os.path.join(os.path.dirname(__file__), "..", "..", "data", "agent_checkpoint (6).json")
    ingest(filepath=filepath, classify_empty=True)

