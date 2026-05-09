"""
CanLII API scraper for Ontario + Federal PI cases.

Fetches L4-L5 spinal injury cases 2018-2024 and ingests into ChromaDB.
API docs: https://api.canlii.org/documentation
Register for free key at: https://api.canlii.org
"""
import asyncio
import httpx
from tqdm import tqdm
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import get_settings
from retrieval.vector_store import add_cases

settings = get_settings()

BASE_URL = "https://api.canlii.org/v1"

# Jurisdictions to target - Federal + Ontario
DATABASES = [
    "onsc",   # Ontario Superior Court
    "onca",   # Ontario Court of Appeal
    "scc",    # Supreme Court of Canada
    "fca",    # Federal Court of Appeal
    "fc",     # Federal Court
]

# PI-relevant search terms
PI_QUERIES = [
    "personal injury herniated disc",
    "motor vehicle accident spinal injury",
    "rear end collision damages",
    "slip and fall negligence Ontario",
    "tort damages chronic pain",
]


async def fetch_cases_for_query(
    client: httpx.AsyncClient,
    database: str,
    query: str,
    max_results: int = 20,
) -> list[dict]:
    """Search CanLII for cases matching a query in a given database."""
    url = f"{BASE_URL}/caseBrowse/en/{database}/"
    params = {
        "api_key": settings.canlii_api_key,
        "resultCount": max_results,
        "offset": 0,
        "fullText": query,
    }

    try:
        resp = await client.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("cases", [])
    except Exception as e:
        print(f"  [warn] {database} / '{query}': {e}")
        return []


async def fetch_case_text(
    client: httpx.AsyncClient,
    database: str,
    case_id: str,
) -> str:
    """Fetch full opinion text for a case."""
    url = f"{BASE_URL}/caseBrowse/en/{database}/{case_id}/content"
    params = {"api_key": settings.canlii_api_key}
    try:
        resp = await client.get(url, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
        # CanLII returns HTML - strip tags for embedding
        from bs4 import BeautifulSoup
        html = data.get("content", "")
        return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    except Exception as e:
        print(f"  [warn] fetch text {case_id}: {e}")
        return ""


def parse_year(date_str: str) -> int:
    try:
        return int(date_str[:4])
    except Exception:
        return 0


async def run_ingestion(max_per_query: int = 20) -> None:
    if not settings.canlii_api_key:
        print("ERROR: CANLII_API_KEY not set in .env")
        return

    print("Starting CanLII ingestion - Federal + Ontario PI cases")
    cases_to_ingest: list[dict] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient() as client:
        for db in DATABASES:
            for query in PI_QUERIES:
                print(f"  Searching {db}: '{query}'")
                raw_cases = await fetch_cases_for_query(
                    client, db, query, max_results=max_per_query
                )

                for case in tqdm(raw_cases, desc=f"  {db}", leave=False):
                    case_id = case.get("caseId", {}).get("en", "")
                    if not case_id or case_id in seen_ids:
                        continue
                    seen_ids.add(case_id)

                    year = parse_year(case.get("decisionDate", ""))
                    if year < 2018:
                        continue

                    text = await fetch_case_text(client, db, case_id)
                    if not text or len(text) < 200:
                        continue

                    cases_to_ingest.append({
                        "id": case_id,
                        "text": text[:8000],  # cap chunk size
                        "metadata": {
                            "case_name": case.get("title", ""),
                            "citation": case.get("citation", ""),
                            "url": f"https://www.canlii.org/en/{db}/{case_id}/",
                            "jurisdiction": db,
                            "year": year,
                            "date": case.get("decisionDate", ""),
                            "injury_type": "",   # Yingkai's extractor will populate
                            "verdict_amount": 0,  # Yingkai's extractor will populate
                        },
                    })

                await asyncio.sleep(0.3)  # be polite to the API

    if not cases_to_ingest:
        print("No cases found. Check your CANLII_API_KEY.")
        return

    print(f"\nIngesting {len(cases_to_ingest)} cases into ChromaDB...")
    add_cases(cases_to_ingest)
    print(f"Done. Total cases in DB: {len(cases_to_ingest)}")


if __name__ == "__main__":
    asyncio.run(run_ingestion())
