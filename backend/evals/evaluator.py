"""
LLM-judge evaluator for the legal research agent.

Input:  same format as EVAL_REQUEST_EXAMPLE (query + answer + sources + contexts)
Output: structured scores with reasoning

Dimensions scored:
  correctness   (0.35) — cited statutes directly answer the query
  faithfulness  (0.30) — answer accurately reflects the statute text
  relevance     (0.20) — statutes are relevant to the legal question
  completeness  (0.15) — no important statutes were missed

Verdict: pass (>=0.75) | partial (>=0.45) | fail (<0.45)

Backward-compatible: evaluate_response() matches the original stub signature.
"""
from __future__ import annotations

import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from typing import Literal, Optional

from pydantic import BaseModel

from llm_client import get_llm
from config import get_settings
from evals.constants import state_to_code, factor_name_to_code

settings = get_settings()


# ── Data models ───────────────────────────────────────────────────────────── #

class EvalSource(BaseModel):
    statute: str
    state: str
    section: str
    contributing_factor: str
    source_url: str


class EvalRequest(BaseModel):
    query: str
    answer: str
    sources: list[EvalSource]
    contexts: list[str] = []
    method: Literal["llm_judge", "ragas"] = "llm_judge"


class DimensionScore(BaseModel):
    score: float       # 0.0 – 1.0
    reasoning: str


class EvalResult(BaseModel):
    correctness:   DimensionScore
    faithfulness:  DimensionScore
    relevance:     DimensionScore
    completeness:  DimensionScore
    overall_score: float
    confidence:    float    # how certain the judge is about this evaluation, 0.0 – 1.0
    verdict:       Literal["pass", "fail", "partial"]
    summary:       str


# ── Prompt ────────────────────────────────────────────────────────────────── #

JUDGE_SYSTEM = """\
You are an expert legal research evaluator specializing in motor vehicle law and \
personal injury cases. You review the output of an AI legal research assistant and \
score it on four dimensions.

Scoring rules:
- Score each dimension 0.0 to 1.0 (two decimal places).
- 1.0 = perfect, 0.0 = completely wrong, 0.5 = partially correct.
- Be strict: a cited statute that is tangentially related scores no higher than 0.5.
- Base your judgment only on what is provided — do not hallucinate case law.

Confidence score (0.0 – 1.0):
- Reflects how certain you are about your own evaluation, not the quality of the answer.
- High (0.8–1.0): case facts are clear, statutes are unambiguous, ground truth is available.
- Medium (0.5–0.7): some facts are vague, statutes are borderline applicable, or ground truth is missing.
- Low (0.0–0.4): case is highly ambiguous, insufficient context to judge reliably.

Return ONLY valid JSON matching this schema exactly:
{
  "correctness":   { "score": <float>, "reasoning": "<string>" },
  "faithfulness":  { "score": <float>, "reasoning": "<string>" },
  "relevance":     { "score": <float>, "reasoning": "<string>" },
  "completeness":  { "score": <float>, "reasoning": "<string>" },
  "confidence":    <float>,
  "summary": "<one sentence verdict>"
}
"""


def _build_judge_prompt(req: EvalRequest, db_statutes: Optional[list] = None) -> str:
    sources_text = "\n".join(
        f"  - {s.statute} [{s.contributing_factor}] — {s.source_url}"
        for s in req.sources
    )
    contexts_text = "\n".join(f'  "{c}"' for c in req.contexts) or "  (none provided)"

    if db_statutes:
        db_text = "\n".join(
            f"  - {s['citation']} [{s.get('factor_name') or s.get('title', '')}]"
            for s in db_statutes
        )
        completeness_section = f"""
## All statutes in the database relevant to this query (ground truth)
{db_text}

For completeness: compare the sources cited above against this list.
Any statute in the ground truth that was NOT cited is a potential miss.
"""
    else:
        completeness_section = """
## Ground truth
Not provided — score completeness based only on the sources and contexts given.
"""

    return f"""\
## Attorney query
{req.query}

## System answer
{req.answer}

## Sources cited by the system
{sources_text}

## Raw statute text (contexts)
{contexts_text}
{completeness_section}
---
Score this response on:
1. **Correctness** — Do the cited statutes directly answer the query?
2. **Faithfulness** — Does the answer accurately reflect what the statute text actually says?
3. **Relevance** — Are the cited statutes relevant to the legal question asked?
4. **Completeness** — Compare cited sources against the ground truth list. Which statutes were missed?
"""


# ── Weights & verdict ─────────────────────────────────────────────────────── #

WEIGHTS = {
    "correctness":  0.35,
    "faithfulness": 0.30,
    "relevance":    0.20,
    "completeness": 0.15,
}


def _overall(scores: dict) -> float:
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS), 3)


def _verdict(score: float) -> str:
    if score >= 0.75:
        return "pass"
    if score >= 0.45:
        return "partial"
    return "fail"


def _parse_judge_response(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


# ── Core evaluate functions ───────────────────────────────────────────────── #

def evaluate(req: EvalRequest, db=None) -> EvalResult:
    """
    Run the LLM judge on one query/answer/sources triple.

    db (optional): any object with get_statutes_by_factor(factor_code, jurisdiction)
    that returns rows with a "citation" key. When provided, the judge sees all
    statutes sharing the same contributing factor as ground truth for completeness.
    """
    db_statutes = None
    if db is not None and req.sources:
        seen_citations: set = set()
        db_statutes = []
        for source in req.sources:
            factor_code = factor_name_to_code(source.contributing_factor)
            if factor_code:
                rows = db.get_statutes_by_factor(
                    factor_code,
                    jurisdiction=state_to_code(source.state),
                )
                for row in rows:
                    if row["citation"] not in seen_citations:
                        seen_citations.add(row["citation"])
                        db_statutes.append(row)

    llm = get_llm()
    raw = llm.invoke(
        messages=[{"role": "user", "content": _build_judge_prompt(req, db_statutes)}],
        system=JUDGE_SYSTEM,
    )

    data = _parse_judge_response(raw)

    dim_scores = {
        "correctness":  data["correctness"]["score"],
        "faithfulness": data["faithfulness"]["score"],
        "relevance":    data["relevance"]["score"],
        "completeness": data["completeness"]["score"],
    }
    overall = _overall(dim_scores)

    return EvalResult(
        correctness=DimensionScore(**data["correctness"]),
        faithfulness=DimensionScore(**data["faithfulness"]),
        relevance=DimensionScore(**data["relevance"]),
        completeness=DimensionScore(**data["completeness"]),
        overall_score=overall,
        confidence=round(float(data.get("confidence", 0.5)), 2),
        verdict=_verdict(overall),
        summary=data.get("summary", ""),
    )


def evaluate_batch(requests: list[EvalRequest], db=None) -> dict:
    """Evaluate a list of requests and return a summary report."""
    results = []
    for req in requests:
        result = evaluate(req, db=db)
        results.append({
            "query":         req.query,
            "verdict":       result.verdict,
            "overall_score": result.overall_score,
            "confidence":    result.confidence,
            "correctness":   result.correctness.score,
            "faithfulness":  result.faithfulness.score,
            "relevance":     result.relevance.score,
            "completeness":  result.completeness.score,
            "summary":       result.summary,
        })

    pass_count    = sum(1 for r in results if r["verdict"] == "pass")
    partial_count = sum(1 for r in results if r["verdict"] == "partial")
    fail_count    = sum(1 for r in results if r["verdict"] == "fail")
    avg_score     = (
        round(sum(r["overall_score"] for r in results) / len(results), 3)
        if results else 0.0
    )

    return {
        "summary": {
            "total":         len(results),
            "pass":          pass_count,
            "partial":       partial_count,
            "fail":          fail_count,
            "average_score": avg_score,
        },
        "results": results,
    }


# ── Backward-compatible shim ──────────────────────────────────────────────── #

def evaluate_response(
    query: str,
    answer: str,
    sources: list[dict],
    contexts: Optional[list] = None,
    method: Optional[str] = None,
) -> dict:
    """
    Original stub signature — kept so existing callers don't break.
    Routes to evaluate() for llm_judge, returns RAGAS stub otherwise.
    """
    provider = method or settings.eval_provider

    if provider == "ragas":
        return {
            "faithfulness":      None,
            "answer_relevancy":  None,
            "context_precision": None,
            "context_recall":    None,
            "note": "RAGAS stub — wire in eval dataset when ready",
        }

    eval_sources = [
        EvalSource(
            statute=s.get("statute", ""),
            state=s.get("state", ""),
            section=s.get("section", ""),
            contributing_factor=s.get("contributing_factor", ""),
            source_url=s.get("source_url", ""),
        )
        for s in sources
    ]

    req = EvalRequest(
        query=query,
        answer=answer,
        sources=eval_sources,
        contexts=contexts or [],
        method="llm_judge",
    )
    result = evaluate(req)

    return {
        "method": "llm_judge",
        "scores": {
            "correctness":  result.correctness.score,
            "faithfulness": result.faithfulness.score,
            "relevance":    result.relevance.score,
            "completeness": result.completeness.score,
            "overall":      result.overall_score,
            "confidence":   result.confidence,
            "verdict":      result.verdict,
            "reasoning":    result.summary,
        },
    }
