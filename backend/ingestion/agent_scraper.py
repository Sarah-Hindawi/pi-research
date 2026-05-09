"""
Agentic multi-state vehicle code scraper.
Owner: Jeffery / Sarah

Uses Claude to:
1. Discover the correct URL for each state's vehicle code section
2. Scrape and extract statute text
3. Classify contributing factor
4. Return structured JSON

Falls back to Justia (aggregator) for states where direct scraping fails.

Usage:
    python -m ingestion.agent_scraper --state CA
    python -m ingestion.agent_scraper --all
"""
import asyncio
import sys
import os
import json
import argparse
from tqdm import tqdm
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_client import get_llm
from retrieval.vector_store import add_statutes
from ingestion.classifier import classify_batch
from ingestion.state_urls import STATE_SOURCES, STATE_BY_ABBR
from config import get_settings

settings = get_settings()

# Justia fallback — covers all 50 states with consistent HTML
JUSTIA_BASE = "https://law.justia.com/codes"

# PI-relevant section keywords to search for per state
PI_KEYWORDS = [
    "speed", "reckless", "DUI", "alcohol", "signal", "stop sign",
    "lane", "yield", "turn", "passing", "following", "phone",
    "wireless", "fleeing", "hit and run", "horn", "traffic control",
]


# ── Justia fallback scraper ────────────────────────────────────────────────

JUSTIA_STATE_PATHS = {
    "California": "california/vehicle-code",
    "Texas": "texas/transportation-code",
    "New York": "new-york/vat",
    "Florida": "florida/title-xxiii-motor-vehicles",
    "Illinois": "illinois/chapter-625-vehicles",
    "Pennsylvania": "pennsylvania/title-75-vehicles",
    "Ohio": "ohio/chapter-4511",
    "Georgia": "georgia/title-40",
    "North Carolina": "north-carolina/chapter-20",
    "Michigan": "michigan/chapter-257",
    "Arizona": "arizona/title-28",
    "Washington": "washington/title-46",
    "Colorado": "colorado/title-42",
    "Nevada": "nevada/chapter-484b",
    "Oregon": "oregon/chapter-811",
    "Minnesota": "minnesota/chapter-169",
    "Virginia": "virginia/title-46.2",
    "Massachusetts": "massachusetts/part-i/title-xiv/chapter-90",
    "New Jersey": "new-jersey/title-39",
    "Indiana": "indiana/title-9",
    "Tennessee": "tennessee/title-55",
    "Missouri": "missouri/title-xx/chapter-304",
    "Wisconsin": "wisconsin/chapter-346",
    "Maryland": "maryland/transportation/title-21",
    "South Carolina": "south-carolina/title-56",
    "Alabama": "alabama/title-32",
    "Louisiana": "louisiana/rs/title32",
    "Kentucky": "kentucky/title-xvi/chapter-189",
    "Oklahoma": "oklahoma/title-47",
    "Connecticut": "connecticut/title-14",
    "Iowa": "iowa/title-viii/chapter-321",
    "Utah": "utah/title-41/chapter-6a",
    "Arkansas": "arkansas/title-27",
    "Mississippi": "mississippi/title-63",
    "Kansas": "kansas/chapter-8",
    "New Mexico": "new-mexico/chapter-66",
    "Nebraska": "nebraska/chapter-60",
    "Idaho": "idaho/title-49",
    "West Virginia": "west-virginia/chapter-17c",
    "Hawaii": "hawaii/division-1/title-17/chapter-291c",
    "Maine": "maine/title-29-a",
    "New Hampshire": "new-hampshire/title-xxi/chapter-265",
    "Rhode Island": "rhode-island/title-31",
    "Montana": "montana/title-61",
    "Delaware": "delaware/title-21",
    "South Dakota": "south-dakota/title-32",
    "North Dakota": "north-dakota/title-39",
    "Alaska": "alaska/title-28",
    "Vermont": "vermont/title-23",
    "Wyoming": "wyoming/title-31",
    "District of Columbia": "district-of-columbia/division-viii/title-50/chapter-23",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_justia_section_list(
    client: httpx.AsyncClient,
    state_name: str,
) -> list[dict]:
    """Fetch section listing from Justia for a state."""
    path = JUSTIA_STATE_PATHS.get(state_name)
    if not path:
        return []

    url = f"{JUSTIA_BASE}/{path}/"
    try:
        resp = await client.get(url, timeout=20.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        sections = []
        # Justia lists sections as links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            # Filter for section-like links
            if "/section-" in href or "section" in href.lower():
                sections.append({
                    "url": href if href.startswith("http") else f"https://law.justia.com{href}",
                    "title": text,
                })
        return sections[:80]  # cap at 80 sections per state
    except Exception as e:
        print(f"  [justia] {state_name}: {e}")
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_justia_section_text(
    client: httpx.AsyncClient,
    url: str,
) -> str:
    """Fetch full text of a Justia section page."""
    try:
        resp = await client.get(url, timeout=20.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Justia puts statute text in div.has-text-align-justify or similar
        for selector in ["div.has-text-align-justify", "div#codes-body", "div.code-body", "div.primary-content"]:
            content = soup.select_one(selector)
            if content:
                return content.get_text(separator=" ", strip=True)

        # Fallback: main content area
        main = soup.find("main") or soup.find("article")
        if main:
            return main.get_text(separator=" ", strip=True)[:3000]
        return ""
    except Exception as e:
        print(f"  [justia_text] {url}: {e}")
        return ""


def is_pi_relevant(text: str, title: str = "") -> bool:
    """Quick keyword check — skip statutes that aren't PI-relevant."""
    combined = (text + " " + title).lower()
    return any(kw.lower() in combined for kw in PI_KEYWORDS)


def build_statute_id(state_abbr: str, section: str) -> str:
    clean = section.lower().replace(" ", "").replace(".", "").replace("(", "").replace(")", "").replace("-", "")
    return f"{state_abbr.lower()}-{clean}"


async def scrape_state(
    client: httpx.AsyncClient,
    state_info: dict,
) -> list[dict]:
    """
    Scrape all PI-relevant vehicle code sections for one state via Justia.
    Returns list of statute dicts ready for ChromaDB.
    """
    state_name = state_info["name"]
    state_abbr = state_info["abbr"]
    citation_prefix = state_info["citation"]

    print(f"\n  Scraping {state_name}...")
    section_links = await fetch_justia_section_list(client, state_name)

    if not section_links:
        print(f"  [warn] No sections found for {state_name}")
        return []

    results = []
    for link in section_links:
        url = link["url"]
        title = link["title"]

        # Quick title relevance check before fetching full text
        if not is_pi_relevant("", title):
            continue

        text = await fetch_justia_section_text(client, url)
        if not text or len(text) < 50:
            continue

        if not is_pi_relevant(text, title):
            continue

        # Extract section number from URL or title
        section = extract_section_from_url(url, title)

        results.append({
            "id": build_statute_id(state_abbr, section),
            "text": text[:3000],
            "metadata": {
                "statute":              f"{citation_prefix} § {section}",
                "state":                state_name,
                "universal_citation":   citation_prefix,
                "section":              section,
                "complete_statute":     f"Pursuant to {citation_prefix} § {section}, \"{text[:400]}\"",
                "contributing_factor":  "",   # filled by classifier
                "source_url":           url,
                "title":                title,
            },
        })
        await asyncio.sleep(0.3)

    print(f"  Found {len(results)} PI-relevant sections in {state_name}")
    return results


def extract_section_from_url(url: str, title: str) -> str:
    """Extract section number from Justia URL or title."""
    import re
    # Try URL pattern: /section-22350/
    m = re.search(r"/section-([^/]+)/?", url)
    if m:
        return m.group(1).replace("-", ".")

    # Try title pattern: "§ 22350" or "Section 22350"
    m = re.search(r"§\s*([\d\-\.a-zA-Z]+)", title)
    if m:
        return m.group(1)

    m = re.search(r"[Ss]ection\s+([\d\-\.a-zA-Z]+)", title)
    if m:
        return m.group(1)

    # Fallback: last path segment
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else "unknown"


async def run_all_states(priority_first: bool = True) -> None:
    """
    Scrape all 50 states + DC.
    If priority_first=True, scrapes high-population states first
    (more likely to appear in held-out eval).
    """
    # Priority order — high-population states first
    priority = [
        "California", "Texas", "New York", "Florida", "Illinois",
        "Pennsylvania", "Ohio", "Georgia", "North Carolina", "Michigan",
        "Arizona", "Washington", "Colorado", "Nevada", "Oregon",
        "Minnesota", "Virginia", "Massachusetts", "New Jersey", "Indiana",
    ]

    if priority_first:
        ordered = sorted(
            STATE_SOURCES,
            key=lambda s: priority.index(s["name"]) if s["name"] in priority else 999,
        )
    else:
        ordered = STATE_SOURCES

    total_added = 0

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (legal research tool — hackathon)",
            "Accept": "text/html,application/xhtml+xml",
        },
        follow_redirects=True,
    ) as client:
        for state_info in ordered:
            statutes = await scrape_state(client, state_info)
            if statutes:
                classified = classify_batch(statutes)
                add_statutes(classified)
                total_added += len(classified)
                print(f"  ✓ {state_info['name']}: {len(classified)} statutes added (total: {total_added})")
            await asyncio.sleep(1.0)  # polite delay between states

    print(f"\nAll states complete. Total statutes added: {total_added}")


async def run_single_state(abbr: str) -> None:
    state_info = STATE_BY_ABBR.get(abbr.upper())
    if not state_info:
        print(f"Unknown state abbreviation: {abbr}")
        return

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (legal research tool)"},
        follow_redirects=True,
    ) as client:
        statutes = await scrape_state(client, state_info)
        if statutes:
            classified = classify_batch(statutes)
            add_statutes(classified)
            print(f"Done. {len(classified)} statutes added for {state_info['name']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", help="Single state abbreviation e.g. CA, TX")
    parser.add_argument("--all", action="store_true", help="Scrape all 50 states + DC")
    args = parser.parse_args()

    if args.state:
        asyncio.run(run_single_state(args.state))
    elif args.all:
        asyncio.run(run_all_states())
    else:
        print("Usage: python -m ingestion.agent_scraper --state CA")
        print("       python -m ingestion.agent_scraper --all")
