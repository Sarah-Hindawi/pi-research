"""
Synthetic eval generator.

Generates multi-state query variants from the 41 CA released rows.
Used for self-evaluation before judges test with the held-out set.

Usage:
    python -m ingestion.synthetic_evals
"""
import json
import csv
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_client import get_llm
from ingestion.state_urls import ALL_STATE_NAMES
from config import get_settings

settings = get_settings()

# States most likely to appear in held-out eval
TARGET_STATES = [
    "Texas", "New York", "Florida", "Illinois", "Pennsylvania",
    "Ohio", "Georgia", "Washington", "Nevada", "Arizona",
]

SYNTHETIC_PROMPT = """You are generating evaluation test cases for a legal research system.

Given this California vehicle code statute and its contributing factor label,
generate {n} realistic attorney-style queries that a paralegal might ask
to find equivalent statutes in other US states.

Statute: {statute}
Contributing factor: {contributing_factor}
Statute text: {text}

Generate {n} queries targeting these states: {states}

Return ONLY valid JSON array:
[
  {{
    "query": "What is the Texas statute for...",
    "target_state": "Texas",
    "target_factor": "{contributing_factor}",
    "expected_section_pattern": "rough guess at section number pattern"
  }}
]"""


def generate_synthetic_evals(
    csv_path: str,
    output_path: str,
    n_per_statute: int = 2,
) -> list[dict]:
    """
    Generate synthetic eval queries from the released CA CSV.
    """
    llm = get_llm()

    # Load CA seed statutes
    seed_statutes = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seed_statutes.append(row)

    print(f"Generating synthetic evals from {len(seed_statutes)} CA statutes...")
    all_evals = []

    for statute in seed_statutes:
        states_sample = TARGET_STATES[:4]  # 4 states per statute
        prompt = SYNTHETIC_PROMPT.format(
            n=n_per_statute,
            statute=statute["Statute"],
            contributing_factor=statute["Contributing Factor"],
            text=statute["Statute Language"][:300],
            states=", ".join(states_sample),
        )
        try:
            response = llm.invoke([{"role": "user", "content": prompt}])
            clean = response.strip().removeprefix("```json").removesuffix("```").strip()
            evals = json.loads(clean)
            for e in evals:
                e["source_statute"] = statute["Statute"]
                e["source_state"] = "California"
            all_evals.extend(evals)
        except Exception as ex:
            print(f"  [warn] {statute['Statute']}: {ex}")

    # Save to file
    with open(output_path, "w") as f:
        json.dump(all_evals, f, indent=2)

    print(f"Generated {len(all_evals)} synthetic eval queries → {output_path}")
    return all_evals


def run_self_eval(evals: list[dict], search_fn) -> dict:
    """
    Run self-evaluation against the synthetic evals.
    Returns precision metrics.
    """
    correct_factor = 0
    correct_state = 0
    total = len(evals)

    for e in evals:
        results = search_fn(
            query=e["query"],
            n_results=3,
            state=e.get("target_state"),
        )
        if not results:
            continue

        top = results[0]
        if top["metadata"].get("contributing_factor") == e["target_factor"]:
            correct_factor += 1
        if top["metadata"].get("state") == e["target_state"]:
            correct_state += 1

    return {
        "total": total,
        "factor_precision": round(correct_factor / total, 3) if total else 0,
        "state_precision": round(correct_state / total, 3) if total else 0,
    }


if __name__ == "__main__":
    output = "./data/synthetic_evals.json"
    generate_synthetic_evals(
        csv_path=settings.eval_csv_path,
        output_path=output,
        n_per_statute=2,
    )
