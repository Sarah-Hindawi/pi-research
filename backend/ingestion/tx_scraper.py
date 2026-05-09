"""
Texas Transportation Code scraper.
Owner: Sarah

Source: https://statutes.capitol.texas.gov
Equivalent to CA Vehicle Code for Texas.

Usage:
    python -m ingestion.tx_scraper
"""
import asyncio, sys, os
import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from retrieval.vector_store import add_statutes
from ingestion.classifier import classify_batch

STATE = "Texas"
CITATION = "Tex. Transp. Code"
BASE = "https://statutes.capitol.texas.gov/Docs/TN/htm/TN.545.htm"

# TX Transportation Code Chapter 545 — Rules of the Road (most PI-relevant)
# Format: chapter.section
SECTIONS = [
    # Speed
    ("545", "351"), ("545", "352"), ("545", "353"), ("545", "354"), ("545", "355"),
    # Signals / signs
    ("544", "004"), ("544", "005"), ("544", "006"), ("544", "007"), ("544", "008"),
    # Turning
    ("545", "101"), ("545", "102"), ("545", "103"), ("545", "104"), ("545", "105"),
    # Lane discipline
    ("545", "060"), ("545", "061"), ("545", "062"),
    # Following
    ("545", "062"),
    # Passing
    ("545", "051"), ("545", "052"), ("545", "053"), ("545", "054"), ("545", "055"),
    # Yielding
    ("545", "151"), ("545", "152"), ("545", "153"), ("545", "154"), ("545", "155"),
    # DUI
    ("49", "04"), ("49", "045"), ("49", "07"), ("49", "08"),
    # Reckless
    ("545", "401"), ("545", "402"),
    # Phone
    ("545", "4251"),
    # Fleeing
    ("545", "421"),
    # Stop signs
    ("544", "010"),
]


async def fetch_section(
    client: httpx.AsyncClient, chapter: str, section: str
) -> dict | None:
    url = f"https://statutes.capitol.texas.gov/Docs/TN/htm/TN.{chapter}.htm"
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Find section by anchor — TX statutes use Sec. X.XXX format
        sec_id = f"{chapter}.{section}"
        target = soup.find("a", {"name": sec_id})
        if not target:
            # Try without leading zeros
            target = soup.find("a", {"name": f"Sec.{chapter}.{section}."})
        if not target:
            return None

        # Get text from next sibling paragraphs
        text_parts = []
        for sibling in target.find_next_siblings():
            if sibling.name in ("p", "div"):
                t = sibling.get_text(separator=" ", strip=True)
                if t:
                    text_parts.append(t)
                if len(text_parts) >= 5:
                    break

        text = " ".join(text_parts)
        if len(text) < 30:
            return None

        section_display = f"{chapter}.{section}"
        source_url = f"https://statutes.capitol.texas.gov/Docs/TN/htm/TN.{chapter}.htm#{sec_id}"

        return {
            "id": f"tx-transp-{chapter}-{section}",
            "text": text,
            "metadata": {
                "statute":            f"Tex. Transp. Code § {section_display}",
                "state":              STATE,
                "universal_citation": CITATION,
                "section":            section_display,
                "complete_statute":   f"Pursuant to Tex. Transp. Code § {section_display}, \"{text}\"",
                "contributing_factor": "",
                "source_url":         source_url,
            },
        }
    except Exception as e:
        print(f"  [tx_scraper] {chapter}.{section}: {e}")
        return None


async def run():
    print("Scraping Texas Transportation Code...")
    results = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (legal research tool)"},
        follow_redirects=True,
    ) as client:
        for chapter, section in tqdm(SECTIONS, desc="TX sections"):
            result = await fetch_section(client, chapter, section)
            if result:
                results.append(result)
            await asyncio.sleep(0.5)

    print(f"\nScraped {len(results)} sections — classifying...")
    results = classify_batch(results)
    add_statutes(results)
    print(f"Done. {len(results)} TX statutes added.")


if __name__ == "__main__":
    asyncio.run(run())
