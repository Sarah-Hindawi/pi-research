"""
Citation normalizer — handles malformed/partial citations.
Owner: Yingkai

Normalizes inputs like:
    CVC 21451          → Cal. Veh. Code § 21451
    California 21451   → Cal. Veh. Code § 21451
    Veh Code 21451(a)  → Cal. Veh. Code § 21451(a)
    TX 545.351         → Tex. Transp. Code § 545.351

Usage:
    from ingestion.citation_normalizer import normalize, find_best_match
"""
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from ingestion.state_urls import STATE_BY_ABBR, STATE_BY_NAME, STATE_SOURCES

# Common shorthand aliases → canonical citation prefix
CITATION_ALIASES = {
    # California
    "cvc": "Cal. Veh. Code",
    "ca veh": "Cal. Veh. Code",
    "cal veh": "Cal. Veh. Code",
    "california vehicle code": "Cal. Veh. Code",
    "vehicle code": "Cal. Veh. Code",  # defaults to CA if no state given
    # Texas
    "tx transp": "Tex. Transp. Code",
    "texas transp": "Tex. Transp. Code",
    "tex transp": "Tex. Transp. Code",
    "texas transportation": "Tex. Transp. Code",
    # New York
    "ny vtl": "N.Y. Veh. & Traf. Law",
    "ny veh": "N.Y. Veh. & Traf. Law",
    "new york vtl": "N.Y. Veh. & Traf. Law",
    # Florida
    "fla stat": "Fla. Stat.",
    "fl stat": "Fla. Stat.",
    "florida stat": "Fla. Stat.",
    # Illinois
    "ilcs": "625 Ill. Comp. Stat.",
    "illinois vehicle": "625 Ill. Comp. Stat.",
    # Generic
    "rev code": None,
    "ann code": None,
    "comp stat": None,
}

# State name → citation prefix
STATE_TO_CITATION = {s["name"]: s["citation"] for s in STATE_SOURCES}
ABBR_TO_CITATION = {s["abbr"]: s["citation"] for s in STATE_SOURCES}


def extract_section_number(text: str) -> str | None:
    """Extract section number from citation string."""
    # Patterns: § 21451(a), 21451(a), section 21451, 545.351
    patterns = [
        r"§\s*([\d\w\.\-\(\)]+)",
        r"[Ss]ec(?:tion)?\s+(\d[\d\w\.\-\(\)]*)",
        r"\b(\d{3,6}(?:\.\d+)?(?:\([a-z]\))*)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return None


def detect_state(text: str) -> str | None:
    """Detect state from citation string."""
    text_lower = text.lower()

    # Check abbreviations
    for abbr, info in STATE_BY_ABBR.items():
        if re.search(rf"\b{abbr.lower()}\b", text_lower):
            return info["name"]

    # Check full state names
    for name in STATE_BY_NAME:
        if name.lower() in text_lower:
            return name

    # Check aliases
    for alias, citation in CITATION_ALIASES.items():
        if alias in text_lower and citation:
            # Find state from citation
            for s in STATE_SOURCES:
                if s["citation"] == citation:
                    return s["name"]

    return None


def normalize(raw_citation: str) -> dict:
    """
    Normalize a raw citation string to canonical form.

    Returns:
        {
            "canonical": "Cal. Veh. Code § 21451(a)",
            "state": "California",
            "section": "21451(a)",
            "citation_prefix": "Cal. Veh. Code",
            "confidence": 0.9,
        }
    """
    raw = raw_citation.strip()
    raw_lower = raw.lower().replace(".", "").replace(",", "")

    section = extract_section_number(raw)
    state_name = detect_state(raw)

    citation_prefix = None
    if state_name:
        citation_prefix = STATE_TO_CITATION.get(state_name)

    # Check aliases
    if not citation_prefix:
        for alias, prefix in CITATION_ALIASES.items():
            if alias in raw_lower:
                citation_prefix = prefix
                break

    if not citation_prefix:
        citation_prefix = "Unknown Code"

    confidence = 1.0
    if not state_name:
        confidence -= 0.3
    if not section:
        confidence -= 0.4

    canonical = f"{citation_prefix} § {section}" if section else citation_prefix

    return {
        "canonical": canonical,
        "state": state_name or "Unknown",
        "section": section or "",
        "citation_prefix": citation_prefix,
        "confidence": round(confidence, 2),
        "original": raw,
    }


def find_best_match(raw_citation: str, db_search_fn) -> dict | None:
    """
    Normalize a citation and search ChromaDB for the best matching statute.

    Args:
        raw_citation: raw user input e.g. "CVC 21451"
        db_search_fn: callable — the vector_store.search function

    Returns:
        best matching statute dict or None
    """
    normalized = normalize(raw_citation)

    # Try exact canonical citation first
    results = db_search_fn(
        query=normalized["canonical"],
        n_results=3,
        state=normalized["state"] if normalized["state"] != "Unknown" else None,
    )

    if results:
        return results[0]

    # Try section number only
    if normalized["section"]:
        results = db_search_fn(
            query=normalized["section"],
            n_results=3,
        )
        if results:
            return results[0]

    return None
