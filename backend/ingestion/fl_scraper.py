"""
Florida Statutes scraper — Title XXIII (Motor Vehicles).

Source: https://www.flsenate.gov/Laws/Statutes/
Chapter 316 = State Uniform Traffic Control (main PI chapter)
Chapter 322 = Driver Licenses (DUI)

Usage:
    python -m ingestion.fl_scraper
"""
import asyncio, sys, os
import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from retrieval.vector_store import add_statutes
from ingestion.classifier import classify_batch

STATE = "Florida"
CITATION = "Fla. Stat."
BASE = "https://www.flsenate.gov/Laws/Statutes"

# Florida Statutes Chapter 316 — State Uniform Traffic Control
SECTIONS = [
    # Speed
    ("316", "183"), ("316", "187"), ("316", "189"),
    # Traffic signals
    ("316", "075"), ("316", "123"),
    # Turning
    ("316", "151"), ("316", "153"),
    # Lane discipline
    ("316", "085"), ("316", "089"),
    # Following
    ("316", "0895"),
    # Passing
    ("316", "081"), ("316", "083"), ("316", "084"),
    # Yielding
    ("316", "121"), ("316", "122"), ("316", "125"), ("316", "126"),
    # Stop signs
    ("316", "123"),
    # DUI
    ("316", "193"),
    # Reckless
    ("316", "192"),
    # Phone
    ("316", "305"),
    # Fleeing
    ("316", "1935"),
    # Horn
    ("316", "271"),
    # Stopping
    ("316", "1945"),
]


async def fetch_section(
    client: httpx.AsyncClient, chapter: str, section: str
) -> dict | None:
    section_full = f"{chapter}.{section}"
    url = f"{BASE}/{section_full}"
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # FL Senate site puts statute text in div.Subsection or p tags
        content = soup.find("div", class_="Subsection")
        if not content:
            content = soup.find("div", id="laws")
        if not content:
            content = soup.find("div", class_="statute-body")

        if not content:
            return None

        text = content.get_text(separator=" ", strip=True)
        if len(text) < 30:
            return None

        return {
            "id": f"fl-stat-{chapter}-{section.replace('.', '')}",
            "text": text[:3000],
            "metadata": {
                "statute":            f"Fla. Stat. § {section_full}",
                "state":              STATE,
                "universal_citation": CITATION,
                "section":            section_full,
                "complete_statute":   f"Pursuant to Fla. Stat. § {section_full}, \"{text[:500]}\"",
                "contributing_factor": "",
                "source_url":         url,
            },
        }
    except Exception as e:
        print(f"  [fl_scraper] {chapter}.{section}: {e}")
        return None


async def run():
    print("Scraping Florida Statutes...")
    results = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (legal research tool)"},
        follow_redirects=True,
    ) as client:
        for chapter, section in tqdm(SECTIONS, desc="FL sections"):
            result = await fetch_section(client, chapter, section)
            if result:
                results.append(result)
            await asyncio.sleep(0.5)

    print(f"\nScraped {len(results)} sections — classifying...")
    results = classify_batch(results)
    add_statutes(results)
    print(f"Done. {len(results)} FL statutes added.")


if __name__ == "__main__":
    asyncio.run(run())
