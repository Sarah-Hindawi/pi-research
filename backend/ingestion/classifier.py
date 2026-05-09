"""
Auto-classifier — assigns contributing factor labels to scraped statutes
using Claude (or placeholder). Used by all state scrapers.
Owner: Sarah / Yingkai

Usage:
    from ingestion.classifier import classify_statute
    factor = classify_statute("no person shall drive under the influence...")
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_client import get_llm

# The 17 official contributing factor categories from the eval
CONTRIBUTING_FACTORS = [
    "DUI/DWI",
    "Failure to Maintain Lane",
    "Failure to Obey Traffic Control Device",
    "Failure to Use/Activate Horn",
    "Failure to Yield",
    "Fleeing a Police Officer",
    "Fleeing the Scene of a Collision",
    "Improper Passing",
    "Improper Stopping",
    "Improper Turning",
    "Reckless Driving",
    "Using a Wireless Telephone/Texting While Driving",
    "Driving Too Fast For Conditions",
    "Speeding",
    "Following Too Closely",
    "Improper Lane Change",
    "Other",
]

CLASSIFY_PROMPT = """You are a legal classification assistant.

Given a vehicle code statute, classify it into exactly one of these 17 contributing factor categories:

{categories}

Statute text:
{statute_text}

Reply with ONLY the category name, exactly as written above. No explanation."""


def classify_statute(statute_text: str) -> str:
    """
    Classify a statute into one of the 17 contributing factor categories.
    Returns the category name string.
    Falls back to "Other" if classification fails.
    """
    llm = get_llm()
    prompt = CLASSIFY_PROMPT.format(
        categories="\n".join(f"- {f}" for f in CONTRIBUTING_FACTORS),
        statute_text=statute_text[:1000],
    )
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        # Clean up response
        result = response.strip().strip('"').strip("'")
        # Validate it's one of our categories
        if result in CONTRIBUTING_FACTORS:
            return result
        # Try case-insensitive match
        for factor in CONTRIBUTING_FACTORS:
            if factor.lower() == result.lower():
                return factor
        return "Other"
    except Exception as e:
        print(f"  [classifier] error: {e}")
        return "Other"


def classify_batch(statutes: list[dict]) -> list[dict]:
    """
    Classify a list of statute dicts in place.
    Each dict must have a 'text' key.
    Adds 'contributing_factor' to metadata.
    """
    for s in statutes:
        if not s["metadata"].get("contributing_factor"):
            factor = classify_statute(s["text"])
            s["metadata"]["contributing_factor"] = factor
            print(f"  → {s['metadata'].get('section', '?')} classified as: {factor}")
    return statutes
