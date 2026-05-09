"""
classifier.py — Auto-classifies statutes into 17 contributing factor categories.

Moved here from ingestion/ — this is part of your embedding pipeline,
not the scraping pipeline.
"""
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from llm_client import get_llm

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

CLASSIFY_PROMPT = """Classify this vehicle code statute into contributing factor categories.

Categories:
{categories}

Statute text:
{statute_text}

Return ONLY valid JSON — no markdown:
{{
  "primary_factor": "<exact category name>",
  "secondary_factors": ["<optional>"],
  "confidence": <0.0-1.0>,
  "trigger_phrases": ["<key phrases from statute>"],
  "reason": "<one sentence>"
}}"""


def classify_statute(statute_text: str) -> dict:
    """Classify a single statute. Returns structured dict."""
    llm = get_llm()
    prompt = CLASSIFY_PROMPT.format(
        categories="\n".join(f"- {f}" for f in CONTRIBUTING_FACTORS),
        statute_text=statute_text[:1000],
    )
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        clean = response.strip().removeprefix("```json").removesuffix("```").strip()
        result = json.loads(clean)

        # Validate
        if result.get("primary_factor") not in CONTRIBUTING_FACTORS:
            for f in CONTRIBUTING_FACTORS:
                if f.lower() == result.get("primary_factor", "").lower():
                    result["primary_factor"] = f
                    break
            else:
                result["primary_factor"] = "Other"
        return result
    except Exception as e:
        return {
            "primary_factor":    "Other",
            "secondary_factors": [],
            "confidence":        0.0,
            "trigger_phrases":   [],
            "reason":            f"Failed: {e}",
        }


def classify_batch(statutes: list[dict]) -> list[dict]:
    """Classify all statutes missing a contributing_factor."""
    for s in statutes:
        if s["metadata"].get("contributing_factor"):
            continue
        result = classify_statute(s["text"])
        s["metadata"]["contributing_factor"] = result["primary_factor"]
        s["metadata"]["confidence"]          = result.get("confidence", 0.0)
        s["metadata"]["trigger_phrases"]     = json.dumps(result.get("trigger_phrases", []))
        print(f"  → [{s['metadata'].get('state','?')}] {s['metadata'].get('section','?')}: "
              f"{result['primary_factor']} ({result.get('confidence', 0):.0%})")
    return statutes
