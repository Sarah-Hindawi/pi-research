"""
New York Vehicle & Traffic Law scraper.
Owner: Sarah

Source: https://legislation.nysenate.gov/api/3/statutes/
NY has a public API — no scraping needed, just JSON calls.

Usage:
    python -m ingestion.ny_scraper
"""
import asyncio, sys, os
import httpx
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from retrieval.vector_store import add_statutes
from ingestion.classifier import classify_batch

STATE = "New York"
CITATION = "N.Y. Veh. & Traf. Law"
NY_API = "https://legislation.nysenate.gov/api/3/statutes/VTL"

# NY Vehicle & Traffic Law — PI-relevant sections
# Article 28 (Rules of Road), Article 31 (DUI)
SECTIONS = [
    # Speed
    "1180", "1181", "1182",
    # Traffic signals
    "1110", "1111", "1112", "1113",
    # Turning
    "1160", "1161", "1162", "1163", "1164", "1165",
    # Lane discipline
    "1128", "1129",
    # Following
    "1129-a",
    # Passing
    "1120", "1121", "1122", "1123", "1124", "1125", "1126",
    # Yielding
    "1140", "1141", "1142", "1143", "1144", "1144-a",
    # Stop signs
    "1172",
    # DUI
    "1192",
    # Reckless
    "1212",
    # Phone
    "1225-c", "1225-d",
    # Fleeing
    "270.25",
    # Horn
    "375",
]


async def fetch_section(client: httpx.AsyncClient, section: str) -> dict | None:
    # NY Senate API format
    section_clean = section.replace("-", "%2D")
    url = f"{NY_API}/{section_clean}"
    source_url = f"https://www.nysenate.gov/legislation/laws/VAT/{section}"

    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        result = data.get("result", {})
        text = result.get("text", "").strip()
        if not text or len(text) < 30:
            return None

        return {
            "id": f"ny-vtl-{section.replace('-', '').replace('.', '')}",
            "text": text[:3000],
            "metadata": {
                "statute":            f"N.Y. Veh. & Traf. Law § {section}",
                "state":              STATE,
                "universal_citation": CITATION,
                "section":            section,
                "complete_statute":   f"Pursuant to N.Y. Veh. & Traf. Law § {section}, \"{text[:500]}\"",
                "contributing_factor": "",
                "source_url":         source_url,
            },
        }
    except Exception as e:
        print(f"  [ny_scraper] section {section}: {e}")
        return None


async def run():
    print("Fetching New York Vehicle & Traffic Law via API...")
    results = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (legal research tool)"},
        follow_redirects=True,
    ) as client:
        for section in tqdm(SECTIONS, desc="NY sections"):
            result = await fetch_section(client, section)
            if result:
                results.append(result)
            await asyncio.sleep(0.3)

    print(f"\nFetched {len(results)} sections — classifying...")
    results = classify_batch(results)
    add_statutes(results)
    print(f"Done. {len(results)} NY statutes added.")


if __name__ == "__main__":
    asyncio.run(run())
