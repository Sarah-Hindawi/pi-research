"""
Coverage gap detector — shows which states and factors are thin.
Owner: Sushumma / Yingkai

Usage:
    python -m ingestion.coverage_gap
    from ingestion.coverage_gap import get_coverage_report
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from retrieval.vector_store import _get_collection
from ingestion.state_urls import ALL_STATE_NAMES
from ingestion.classifier import CONTRIBUTING_FACTORS


def get_coverage_report() -> dict:
    """
    Returns a full coverage report:
    {
        "by_state": {"California": {"count": 41, "factors": [...]}},
        "by_factor": {"DUI/DWI": {"count": 12, "states": [...]}},
        "missing_states": [...],
        "thin_factors": [...],    # factors with < 3 statutes
        "total": 412,
    }
    """
    collection = _get_collection()
    all_data = collection.get(include=["metadatas"])
    metadatas = all_data.get("metadatas", [])

    by_state: dict = {}
    by_factor: dict = {}

    for m in metadatas:
        state = m.get("state", "Unknown")
        factor = m.get("contributing_factor", "Unknown")

        if state not in by_state:
            by_state[state] = {"count": 0, "factors": set()}
        by_state[state]["count"] += 1
        by_state[state]["factors"].add(factor)

        if factor not in by_factor:
            by_factor[factor] = {"count": 0, "states": set()}
        by_factor[factor]["count"] += 1
        by_factor[factor]["states"].add(state)

    # Convert sets to lists for JSON serialization
    for s in by_state:
        by_state[s]["factors"] = sorted(by_state[s]["factors"])
    for f in by_factor:
        by_factor[f]["states"] = sorted(by_factor[f]["states"])

    missing_states = [s for s in ALL_STATE_NAMES if s not in by_state]
    thin_factors = [
        f for f in CONTRIBUTING_FACTORS
        if by_factor.get(f, {}).get("count", 0) < 3
    ]

    return {
        "by_state": by_state,
        "by_factor": by_factor,
        "missing_states": missing_states,
        "thin_factors": thin_factors,
        "total": len(metadatas),
        "states_covered": len(by_state),
        "factors_covered": len([f for f in CONTRIBUTING_FACTORS if f in by_factor]),
    }


def print_report() -> None:
    report = get_coverage_report()
    print(f"\n{'='*50}")
    print(f"COVERAGE REPORT — {report['total']} total statutes")
    print(f"States: {report['states_covered']}/{len(ALL_STATE_NAMES)}")
    print(f"Factors: {report['factors_covered']}/{len(CONTRIBUTING_FACTORS)}")

    print(f"\nMissing states ({len(report['missing_states'])}):")
    for s in report["missing_states"]:
        print(f"  ✗ {s}")

    print(f"\nThin factors (< 3 statutes):")
    for f in report["thin_factors"]:
        count = report["by_factor"].get(f, {}).get("count", 0)
        print(f"  ⚠ {f}: {count} statutes")

    print(f"\nTop states by coverage:")
    top = sorted(report["by_state"].items(), key=lambda x: -x[1]["count"])[:10]
    for state, data in top:
        print(f"  {state}: {data['count']} statutes, {len(data['factors'])} factors")
    print("=" * 50)


if __name__ == "__main__":
    print_report()
