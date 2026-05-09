"""
Citation normalizer — handles malformed/partial citations.

Normalizes inputs like:
    CVC 21451            → Cal. Veh. Code § 21451
    California 21451     → Cal. Veh. Code § 21451
    fla stat 316.193     → Fla. Stat. § 316.193(1)
    fl 316.193           → Fla. Stat. § 316.193
    TX 545.351           → Tex. Transp. Code § 545.351

Usage:
    from ingestion.citation_normalizer import normalize, find_best_match
"""
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from ingestion.state_urls import STATE_BY_ABBR, STATE_BY_NAME, STATE_SOURCES

# Common shorthand aliases → canonical citation prefix
# also maps alias → state name so detect_state works
CITATION_ALIASES = {
    # California
    "cvc":                  ("Cal. Veh. Code",          "California"),
    "ca veh":               ("Cal. Veh. Code",          "California"),
    "cal veh":              ("Cal. Veh. Code",          "California"),
    "california vehicle":   ("Cal. Veh. Code",          "California"),
    "vehicle code":         ("Cal. Veh. Code",          "California"),
    # Texas
    "tx transp":            ("Tex. Transp. Code",       "Texas"),
    "texas transp":         ("Tex. Transp. Code",       "Texas"),
    "tex transp":           ("Tex. Transp. Code",       "Texas"),
    "texas transportation": ("Tex. Transp. Code",       "Texas"),
    # New York
    "ny vtl":               ("N.Y. Veh. & Traf. Law",  "New York"),
    "ny veh":               ("N.Y. Veh. & Traf. Law",  "New York"),
    "new york vtl":         ("N.Y. Veh. & Traf. Law",  "New York"),
    # Florida — FIX: added fla + fl as standalone aliases
    "fla stat":             ("Fla. Stat.",              "Florida"),
    "fl stat":              ("Fla. Stat.",              "Florida"),
    "florida stat":         ("Fla. Stat.",              "Florida"),
    "fla":                  ("Fla. Stat.",              "Florida"),
    "florida":              ("Fla. Stat.",              "Florida"),
    # Illinois
    "ilcs":                 ("625 Ill. Comp. Stat.",    "Illinois"),
    "illinois vehicle":     ("625 Ill. Comp. Stat.",    "Illinois"),
    # Ohio
    "ohio rev":             ("Ohio Rev. Code",          "Ohio"),
    # Georgia
    "ga code":              ("Ga. Code Ann.",           "Georgia"),
    # Washington
    "wash rev":             ("Wash. Rev. Code",         "Washington"),
    "rcw":                  ("Wash. Rev. Code",         "Washington"),
    # Colorado
    "colo rev":             ("Colo. Rev. Stat.",        "Colorado"),
    # Michigan
    "mich comp":            ("Mich. Comp. Laws",        "Michigan"),
    "mcl":                  ("Mich. Comp. Laws",        "Michigan"),
    # Pennsylvania
    "pa cons":              ("75 Pa. Cons. Stat.",      "Pennsylvania"),
    # North Carolina
    "nc gen":               ("N.C. Gen. Stat.",         "North Carolina"),
    # New Jersey
    "nj stat":              ("N.J. Stat. Ann.",         "New Jersey"),
    # Arizona
    "ariz rev":             ("Ariz. Rev. Stat.",        "Arizona"),
    "ars":                  ("Ariz. Rev. Stat.",        "Arizona"),
}

STATE_TO_CITATION = {s["name"]: s["citation"] for s in STATE_SOURCES}
ABBR_TO_CITATION  = {s["abbr"]: s["citation"] for s in STATE_SOURCES}


def extract_section_number(text: str) -> str | None:
    """Extract section number from citation string."""
    patterns = [
        r"§\s*([\d\w\.\-\(\)]+)",
        r"[Ss]ec(?:tion)?\s+(\d[\d\w\.\-\(\)]*)",
        r"\b(\d{3,6}(?:\.\d+)+(?:\([a-z]\))*)\b",   # must have a dot e.g. 316.193
        r"\b(\d{4,6}(?:\([a-z]\))*)\b",               # 4-6 digit plain e.g. 21451(a)
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return None


def detect_state(text: str) -> str | None:
    """
    Detect state from citation string.
    FIX: checks aliases FIRST before abbreviations so 'fla' → Florida
    works even though 'FL' is the official abbreviation.
    """
    text_lower = text.lower().strip()

    # 1. Check aliases first (most specific)
    for alias, (citation, state_name) in CITATION_ALIASES.items():
        if alias in text_lower:
            return state_name

    # 2. Check official 2-letter abbreviations
    for abbr, info in STATE_BY_ABBR.items():
        if re.search(rf"\b{abbr.lower()}\b", text_lower):
            return info["name"]

    # 3. Check full state names
    for name in STATE_BY_NAME:
        if name.lower() in text_lower:
            return name

    return None


def normalize(raw_citation: str) -> dict:
    """
    Normalize a raw citation string to canonical form.

    Returns:
        {
            "canonical":        "Fla. Stat. § 316.193(1)",
            "state":            "Florida",
            "section":          "316.193(1)",
            "citation_prefix":  "Fla. Stat.",
            "confidence":       0.9,
            "original":         "fla stat 316.193",
        }
    """
    raw       = raw_citation.strip()
    raw_lower = raw.lower()

    section    = extract_section_number(raw)
    state_name = detect_state(raw)

    # Get citation prefix from state
    citation_prefix = STATE_TO_CITATION.get(state_name) if state_name else None

    # Fallback: check aliases directly
    if not citation_prefix:
        raw_lower_nodots = raw_lower.replace(".", "").replace(",", "")
        for alias, (prefix, _) in CITATION_ALIASES.items():
            if alias in raw_lower_nodots or alias in raw_lower:
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
        "canonical":       canonical,
        "state":           state_name or "Unknown",
        "section":         section or "",
        "citation_prefix": citation_prefix,
        "confidence":      round(confidence, 2),
        "original":        raw,
    }


def find_best_match(raw_citation: str, db_search_fn) -> dict | None:
    """
    Normalize a citation and search ChromaDB for the best matching statute.
    Tries multiple strategies in order of precision.
    """
    from rag.retrieval.store import get_by_citation, search as store_search

    normalized = normalize(raw_citation)
    state = normalized["state"] if normalized["state"] != "Unknown" else None
    section = normalized["section"]

    # Strategy 1: exact canonical citation
    result = get_by_citation(normalized["canonical"])
    if result:
        return result

    # Strategy 2: try adding common subdivisions (a), (b), (1), (2)
    if section:
        for suffix in ["(a)", "(b)", "(1)", "(2)", "(c)", "(3)"]:
            result = get_by_citation(f"{normalized['citation_prefix']} § {section}{suffix}")
            if result:
                return result

    # Strategy 3: semantic search with state + section as query
    if section and state:
        results = store_search(query=section, n_results=3, state=state)
        if results:
            # Return only if section number appears in the statute citation
            for r in results:
                if section.split("(")[0] in r["metadata"].get("section", ""):
                    return r

    # Strategy 4: broad semantic search with state filter only
    results = db_search_fn(query=normalized["canonical"], n_results=3, state=state)
    if results:
        return results[0]

    # Strategy 5: no filters at all
    if section:
        results = db_search_fn(query=section, n_results=3)
        if results:
            return results[0]

    return None