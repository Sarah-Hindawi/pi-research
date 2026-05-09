"""
Master ingestion script — runs everything in the right order.
Owner: Sarah

Usage:
    python -m ingestion.run_all

Order:
    1. Seed CSV (guaranteed 41 CA statutes — always run first)
    2. CA scraper (broader CA coverage)
    3. TX scraper
    4. NY scraper
    5. FL scraper
"""
import asyncio
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ingestion.seed_csv import run as seed_run
from ingestion.ca_scraper import run as ca_run
from ingestion.tx_scraper import run as tx_run
from ingestion.ny_scraper import run as ny_run
from ingestion.fl_scraper import run as fl_run
from retrieval.vector_store import count


async def main():
    print("=" * 50)
    print("OpenClaw Harvester — Full Ingestion Pipeline")
    print("=" * 50)

    print("\n[1/5] Seeding eval CSV (41 CA statutes)...")
    seed_run()

    print("\n[2/5] Scraping California Vehicle Code...")
    await ca_run()

    print("\n[3/5] Scraping Texas Transportation Code...")
    await tx_run()

    print("\n[4/5] Fetching New York Vehicle & Traffic Law...")
    await ny_run()

    print("\n[5/5] Scraping Florida Statutes...")
    await fl_run()

    print("\n" + "=" * 50)
    print(f"Ingestion complete. Total statutes in DB: {count()}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
