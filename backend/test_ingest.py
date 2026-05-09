"""
test_ingest.py — Manual test for the embedding pipeline.
Run this with VS Code debugger to step through the full flow.

Place this file at: backend/test_ingest.py
"""
import sys
import os

# Make sure backend/ is on the path
sys.path.append(os.path.dirname(__file__))

from rag.embedding.ingest import adapt_record, ingest
from rag.embedding.classifier import classify_statute, CONTRIBUTING_FACTORS
from rag.retrieval.store import search, count, list_states, list_factors


# ── Step 1: Test adapt_record on a single record ───────────────────────────
# Put a breakpoint here — inspect what adapt_record returns

sample_record = {
    "id": "test-001",
    "citation": "Tex. Transp. Code Ann. § 544.007",
    "state": "Texas",
    "state_abbrev": "TX",
    "section_number": "544.007",
    "title": "Section 544.007",
    "statute_text": "An operator of a vehicle facing a circular green signal may proceed straight or turn right or left unless a sign prohibits the turn.",
    "source_url": "https://statutes.capitol.texas.gov/Docs/TN/htm/TN.544.htm#544.007",
    "official_url": "https://statutes.capitol.texas.gov/Docs/TN/htm/TN.544.htm#544.007",
    "contributing_factors": ["Failure to Obey Traffic Control Device"],
    "violation_type": "civil",
    "severity": "unknown",
    "chapter_name": "Traffic Signs, Signals, and Markings",
    "harvested_at": "2026-05-09T15:09:19.264479+00:00",
}

print("STEP 1: Testing adapt_record on single record")
adapted = adapt_record(sample_record)
print(f"id:     {adapted['id']}")
print(f"text:   {adapted['text'][:80]}...")
print(f"factor: {adapted['metadata']['contributing_factor']}")
print(f"state:  {adapted['metadata']['state']}")
print(f"url:    {adapted['metadata']['source_url']}")


# ── Step 2: Test classifier on a record with no contributing_factor ─────────
# Put a breakpoint here — watch Claude classify it

print("\n" + "=" * 50)
print("STEP 2: Testing classifier on unclassified statute")
print("=" * 50)
unclassified_text = "A person shall not drive a motor vehicle while holding and operating a handheld wireless telephone."
result = classify_statute(unclassified_text)
print(f"primary_factor:  {result['primary_factor']}")
print(f"confidence:      {result['confidence']}")
print(f"trigger_phrases: {result['trigger_phrases']}")
print(f"reason:          {result['reason']}")


# ── Step 3: Ingest the full JSON file ──────────────────────────────────────
# Put a breakpoint here — watch records go into ChromaDB

print("\n" + "=" * 50)
print("STEP 3: Ingesting full JSON file")
print("=" * 50)
JSON_PATH = os.path.join(os.path.dirname(__file__), "data", "statutes.json")

if os.path.exists(JSON_PATH):
    ingest(filepath=JSON_PATH, classify_empty=True)
else:
    print(f"File not found: {JSON_PATH}")
    print("Put statutes.json in backend/data/ first")


# ── Step 4: Test search after ingestion ────────────────────────────────────
# Put a breakpoint here — inspect what search returns

print("\n" + "=" * 50)
print("STEP 4: Testing search queries")
print("=" * 50)
print(f"Total statutes in DB: {count()}")
print(f"States: {list_states()}")
print(f"Factors: {list_factors()}")

queries = [
    ("DUI Texas",                    "Texas",  None),
    ("running a red light",          None,     "Failure to Obey Traffic Control Device"),
    ("texting while driving",        None,     None),
    ("failure to yield right of way", None,    None),
]

for query, state, factor in queries:
    print(f"\nQuery: '{query}' | state={state} | factor={factor}")
    results = search(query=query, n_results=3, state=state, contributing_factor=factor)
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r['metadata']['statute']}")
        print(f"       Factor: {r['metadata']['contributing_factor']}")
        print(f"       Distance: {r['distance']:.3f}")
        print(f"       URL: {r['metadata']['source_url']}")
