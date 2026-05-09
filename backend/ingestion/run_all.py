"""
Master ingestion pipeline.

Usage:
    python -m ingestion.run_all              # full pipeline
    python -m ingestion.run_all --seed-only  # just 41 CA statutes
    python -m ingestion.run_all --no-synth   # skip synthetic evals
"""
import asyncio, argparse, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ingestion.seed_csv import run as seed_run
from ingestion.agent_scraper import run_all_states
from ingestion.coverage_gap import print_report
from ingestion.synthetic_evals import generate_synthetic_evals
from retrieval.vector_store import count
from config import get_settings

settings = get_settings()


async def main(seed_only=False, no_synth=False):
    print("=" * 55)
    print("OpenClaw Harvester — Full Ingestion Pipeline")
    print("=" * 55)

    print("\n[1/4] Seeding 41 CA eval statutes (guaranteed floor score)...")
    seed_run()
    print(f"  DB: {count()} statutes")

    if seed_only:
        print_report()
        return

    print("\n[2/4] Agentic scraper — all 50 states + DC via Justia...")
    print("  Priority states scraped first. Takes 15-30 mins.")
    await run_all_states(priority_first=True)
    print(f"  DB: {count()} statutes")

    print("\n[3/4] Coverage gap report...")
    print_report()

    if not no_synth:
        print("\n[4/4] Generating synthetic eval queries...")
        generate_synthetic_evals(
            csv_path=settings.eval_csv_path,
            output_path="./data/synthetic_evals.json",
            n_per_statute=2,
        )

    print(f"\n{'='*55}")
    print(f"Done. Total statutes: {count()}")
    print(f"{'='*55}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--no-synth", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(seed_only=args.seed_only, no_synth=args.no_synth))
