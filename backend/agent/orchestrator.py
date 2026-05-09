"""
LangGraph agent orchestrator.

Steps:
1.  Parse attorney query → identify intent + key facts
2.  Route to appropriate tools (RAG, live CanLII search, statute check)
3.  Gather results
4.  Synthesise cited answer
5-10.
"""
from __future__ import annotations
import json
import sys
import os
from datetime import date
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_client import get_llm
from retrieval.vector_store import search as chroma_search
from prompts.templates import (
    AGENT_SYSTEM_PROMPT,
    CASE_PARSER_PROMPT,
    VALUATION_PROMPT,
    STATUTE_REASONING_PROMPT,
    EXPERT_WITNESS_PROMPT,
)


# ── State ──────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[dict], add_messages]
    query: str
    intent: str                    # "valuation" | "expert" | "statute" | "general"
    retrieved_cases: list[dict]
    live_cases: list[dict]
    sources: list[dict]
    final_answer: str


# ── Nodes ──────────────────────────────────────────────────────────────────

def parse_intent(state: AgentState) -> AgentState:
    """
    Step 1: Classify the attorney's query intent so we know which
    tools and prompts to use downstream.
    """
    llm = get_llm()
    query = state["query"]

    classify_prompt = f"""Classify this PI attorney query into one of these intents:
- valuation: asking about case value, verdict amounts, damages
- expert: asking about expert witnesses
- statute: asking about thresholds, deductibles, MIG, Insurance Act
- general: case law research, causation standards, anything else

Query: "{query}"

Reply with ONLY one word: valuation, expert, statute, or general."""

    response = llm.invoke([{"role": "user", "content": classify_prompt}])
    intent = response.strip().lower()
    if intent not in ("valuation", "expert", "statute", "general"):
        intent = "general"

    return {**state, "intent": intent}


def rag_retrieval(state: AgentState) -> AgentState:
    """
    Step 2: Search ChromaDB for relevant pre-ingested cases.
    """
    results = chroma_search(
        query=state["query"],
        n_results=5,
    )
    return {**state, "retrieved_cases": results}


def live_canlii_search(state: AgentState) -> AgentState:
    """
    Step 3: If RAG results are sparse (< 3 cases), fall back to
    live CanLII API search for real-time results.
    Jeffery: expand this with actual CanLII API call when Sarah's
    scraper module is ready.
    """
    if len(state["retrieved_cases"]) >= 3:
        return {**state, "live_cases": []}

    # TODO Jeffery: wire in live CanLII search here
    # from ingestion.canlii_scraper import live_search
    # live = await live_search(state["query"])
    live_cases: list[dict] = []  # placeholder
    return {**state, "live_cases": live_cases}


def synthesise_answer(state: AgentState) -> AgentState:
    """
    Step 4: Combine RAG + live results and generate a cited answer.
    Routes to intent-specific prompt.
    """
    llm = get_llm()
    all_cases = state["retrieved_cases"] + state["live_cases"]

    # Build case summaries for the prompt
    case_summaries = "\n\n".join(
        f"[{i+1}] {c['metadata'].get('case_name', 'Unknown')} "
        f"({c['metadata'].get('citation', '')})\n"
        f"URL: {c['metadata'].get('url', '')}\n"
        f"{c['text'][:600]}"
        for i, c in enumerate(all_cases)
    )

    today = date.today().isoformat()
    system = AGENT_SYSTEM_PROMPT.format(today=today)

    intent = state["intent"]

    if intent == "valuation":
        user_content = VALUATION_PROMPT.format(
            plaintiff_facts=state["query"],
            similar_cases=case_summaries,
        )
    elif intent == "statute":
        user_content = STATUTE_REASONING_PROMPT.format(
            injury_facts=state["query"],
            relevant_cases=case_summaries,
        )
    elif intent == "expert":
        user_content = EXPERT_WITNESS_PROMPT.format(
            expert_name=state["query"],
            cases=case_summaries,
        )
    else:
        user_content = (
            f"Attorney question: {state['query']}\n\n"
            f"Relevant cases:\n{case_summaries}\n\n"
            f"Answer the question with citations."
        )

    # Prepend full conversation history for context
    history = [
        m for m in state["messages"]
        if m.get("role") in ("user", "assistant")
    ]
    messages = history + [{"role": "user", "content": user_content}]

    answer = llm.invoke(messages, system=system) if hasattr(llm, "invoke") else llm.invoke(messages)

    # Build sources list for the frontend + audit trail
    sources = [
        {
            "case_name": c["metadata"].get("case_name", ""),
            "citation": c["metadata"].get("citation", ""),
            "url": c["metadata"].get("url", ""),
            "year": c["metadata"].get("year", ""),
            "jurisdiction": c["metadata"].get("jurisdiction", ""),
        }
        for c in all_cases
    ]

    return {**state, "final_answer": answer, "sources": sources}


# ── Graph ──────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("parse_intent", parse_intent)
    graph.add_node("rag_retrieval", rag_retrieval)
    graph.add_node("live_canlii_search", live_canlii_search)
    graph.add_node("synthesise_answer", synthesise_answer)

    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "rag_retrieval")
    graph.add_edge("rag_retrieval", "live_canlii_search")
    graph.add_edge("live_canlii_search", "synthesise_answer")
    graph.add_edge("synthesise_answer", END)

    return graph.compile()


# Singleton — import this in the API
agent = build_graph()


def run_agent(
    query: str,
    history: list[dict] | None = None,
) -> dict:
    """
    Main entry point called by the FastAPI route.

    Args:
        query: attorney's question
        history: list of {"role": "user"|"assistant", "content": str}

    Returns:
        {"answer": str, "sources": list[dict], "intent": str}
    """
    initial_state: AgentState = {
        "messages": history or [],
        "query": query,
        "intent": "general",
        "retrieved_cases": [],
        "live_cases": [],
        "sources": [],
        "final_answer": "",
    }
    result = agent.invoke(initial_state)
    return {
        "answer": result["final_answer"],
        "sources": result["sources"],
        "intent": result["intent"],
    }
