"""
California Vehicle Code scraper.

Source: https://leginfo.legislature.ca.gov
Scrapes Division 11 (Rules of Road) — most PI-relevant sections.

Usage:
    python -m ingestion.ca_scraper
"""
import asyncio, sys, os, re
import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from retrieval.vector_store import add_statutes
from ingestion.classifier import classify_batch

BASE = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
STATE = "California"
CITATION = "Cal. Veh. Code"

# Key PI-relevant sections in CA Vehicle Code
# Division 11 (Rules of Road) + DUI sections
SECTIONS = [
    # Speeding
    "22349", "22350", "22351", "22352", "22400",
    # Traffic signals / signs
    "21451", "21452", "21453", "21454", "21455", "21456", "21457",
    # Lane discipline
    "21460", "21658", "21659", "21660", "21661",
    # Turning
    "22100", "22101", "22102", "22103", "22104", "22105",
    # Yielding
    "21800", "21801", "21802", "21803", "21804",
    # Following distance
    "21703", "21704", "21705",
    # Passing
    "21750", "21751", "21752", "21753", "21754", "21755",
    # Stopping
    "22450", "22451", "22452",
    # DUI
    "23152", "23153",
    # Reckless
    "23103", "23104",
    # Phone
    "23123", "23123.5", "23124",
    # Fleeing
    "20001", "20002", "2800.1", "2800.2",
    # Horn
    "27001",
]


async def fetch_section(client: httpx.AsyncClient, section: str) -> dict | None:
    params = {"lawCode": "VEH", "sectionNum": f"{section}."}
    url = f"{BASE}?lawCode=VEH&sectionNum={section}."
    try:
        resp = await client.get(BASE, params=params, timeout=15.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # leginfo puts statute text in a div with id="codeLawSectionNoHead"
        content_div = soup.find("div", {"id": "codeLawSectionNoHead"})
        if not content_div:
            # fallback selector
            content_div = soup.find("div", class_="EnglishAmericanSign")
        if not content_div:
            return None

        text = content_div.get_text(separator=" ", strip=True)
        if len(text) < 20:
            return None

        return {
            "id": f"ca-veh-{section.replace('.', '').replace('(', '').replace(')', '')}",
            "text": text,
            "metadata": {
                "statute":            f"Cal. Veh. Code § {section}",
                "state":              STATE,
                "universal_citation": CITATION,
                "section":            section,
                "complete_statute":   f"Pursuant to Cal. Veh. Code § {section}, \"{text}\"",
                "contributing_factor": "",   # filled by classifier
                "source_url":         url,
            },
        }
    except Exception as e:
        print(f"  [ca_scraper] section {section}: {e}")
        return None


async def run():
    print("Scraping California Vehicle Code...")
    results = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (legal research tool)"},
        follow_redirects=True,
    ) as client:
        for section in tqdm(SECTIONS, desc="CA sections"):
            result = await fetch_section(client, section)
            if result:
                results.append(result)
            await asyncio.sleep(0.5)   # polite delay

    print(f"\nScraped {len(results)} sections — classifying contributing factors...")
    results = classify_batch(results)

    print(f"Ingesting into ChromaDB...")
    add_statutes(results)
    print(f"Done. {len(results)} CA statutes added.")


if __name__ == "__main__":
    asyncio.run(run())
