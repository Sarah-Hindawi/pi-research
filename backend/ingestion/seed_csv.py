"""
Seed loader — ingests the eval-ca-vehicle-code.csv directly into ChromaDB.

Run first before any scraper. Guarantees all 41 CA statutes are in the DB
with correct contributing factor labels and source URLs.

Usage:
    python -m ingestion.seed_csv
"""
import sys, os, csv
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from retrieval.vector_store import add_statutes
from config import get_settings

settings = get_settings()

# Base URL for California Vehicle Code — used to build source URLs
CA_BASE_URL = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=VEH&sectionNum="


def section_to_url(section: str) -> str:
    """Convert section number like '21453(a)' to a leginfo URL."""
    # Strip subdivision like (a), (b) for the URL — leginfo uses base section
    base = section.split("(")[0].strip()
    return f"{CA_BASE_URL}{base}."


def load_csv(csv_path: str) -> list[dict]:
    statutes = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            section = row["Section #"].strip()
            statutes.append({
                "id": f"ca-veh-{section.replace(' ', '').replace('(', '').replace(')', '').replace('-', '')}",
                "text": row["Statute Language"].strip(),
                "metadata": {
                    "statute":              row["Statute"].strip(),
                    "state":                row["State"].strip(),
                    "universal_citation":   row["Universal Citation"].strip(),
                    "section":              section,
                    "complete_statute":     row["Complete Statute"].strip(),
                    "contributing_factor":  row["Contributing Factor"].strip(),
                    "source_url":           section_to_url(section),
                },
            })
    return statutes


def run():
    path = settings.eval_csv_path
    print(f"Loading eval CSV from {path}")
    statutes = load_csv(path)
    print(f"Found {len(statutes)} statutes — ingesting into ChromaDB...")
    add_statutes(statutes)
    print(f"Done. {len(statutes)} CA statutes seeded.")


if __name__ == "__main__":
    run()
