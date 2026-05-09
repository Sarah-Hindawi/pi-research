"""
Evaluation stubs - RAGAS + LLM-as-judge.
Both are pluggable; swap in the real implementation during the hackathon.

Usage:
    from evals.evaluator import evaluate_response
    score = evaluate_response(query, answer, sources, method="llm_judge")
"""
from __future__ import annotations
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import get_settings

settings = get_settings()


# ── LLM-as-judge ──────────────────────────────────────────────────────────

LLM_JUDGE_PROMPT = """You are an expert evaluator of legal AI responses.

Score the following response on three criteria (1-5 each):
1. Faithfulness - does the answer accurately reflect the cited sources?
2. Relevance - does the answer address the attorney's question?
3. Citation quality - are sources real, specific, and properly cited?

Query: {query}
Answer: {answer}
Sources provided: {sources}

Return ONLY valid JSON:
{{
  "faithfulness": <1-5>,
  "relevance": <1-5>,
  "citation_quality": <1-5>,
  "overall": <1-5>,
  "reasoning": "<one sentence>"
}}"""


def llm_judge(query: str, answer: str, sources: list[dict]) -> dict:
    """
    Use Claude to score a response.
    Returns dict with scores and reasoning.
    """
    from llm_client import get_llm
    import json

    llm = get_llm()
    prompt = LLM_JUDGE_PROMPT.format(
        query=query,
        answer=answer[:1500],
        sources=str(sources)[:500],
    )
    response = llm.invoke([{"role": "user", "content": prompt}])

    try:
        clean = response.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return {
            "faithfulness": 0,
            "relevance": 0,
            "citation_quality": 0,
            "overall": 0,
            "reasoning": f"Parse error: {response[:100]}",
        }


# ── RAGAS stub ────────────────────────────────────────────────────────────

def ragas_evaluate(
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None = None,
) -> dict:
    """
    RAGAS evaluation stub.
    Plug in real RAGAS when eval dataset is ready at kickoff.

    Metrics:
    - faithfulness: is the answer grounded in the contexts?
    - answer_relevancy: does the answer address the query?
    - context_precision: are retrieved contexts actually useful?
    - context_recall: (requires ground truth)
    """
    # TODO: replace stub with real RAGAS call
    # from ragas import evaluate
    # from ragas.metrics import faithfulness, answer_relevancy, context_precision
    # dataset = Dataset.from_dict({...})
    # result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])

    return {
        "faithfulness": None,
        "answer_relevancy": None,
        "context_precision": None,
        "context_recall": None,
        "note": "RAGAS stub - wire in eval dataset at kickoff",
    }


# ── Unified entry point ────────────────────────────────────────────────────

def evaluate_response(
    query: str,
    answer: str,
    sources: list[dict],
    contexts: list[str] | None = None,
    method: str | None = None,
) -> dict:
    """
    Main eval entry point. Reads EVAL_PROVIDER from env if method not passed.

    Args:
        query: the attorney's original question
        answer: the agent's response
        sources: list of source dicts from the agent
        contexts: raw retrieved text chunks (for RAGAS)
        method: "llm_judge" | "ragas" - overrides env var

    Returns:
        dict with scores
    """
    provider = method or settings.eval_provider

    if provider == "llm_judge":
        return llm_judge(query, answer, sources)
    elif provider == "ragas":
        return ragas_evaluate(query, answer, contexts or [], ground_truth=None)
    else:
        return {"error": f"Unknown eval provider: {provider}"}
