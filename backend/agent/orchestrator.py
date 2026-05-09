"""
LangGraph agent — statute research orchestrator.
Owner: Jeffery

Steps:
1. Parse query → identify intent + extract state/factor filters
2. RAG retrieval from ChromaDB
3. Synthesise cited answer using appropriate prompt
"""
from __future__ import annotations
import json, sys, os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_client import get_llm
from retrieval.vector_store import search, get_by_factor, get_by_citation, list_states
from prompts.templates import (
    AGENT_SYSTEM_PROMPT,
    STATUTE_LOOKUP_PROMPT,
    FACTOR_LOOKUP_PROMPT,
    COMPARISON_PROMPT,
    GENERAL_PROMPT,
    CONTRIBUTING_FACTORS,
)

KNOWN_STATES = [
    "California", "Texas", "New York", "Florida", "Illinois",
    "Ohio", "Pennsylvania", "Georgia", "North Carolina", "Michigan",
]


# ── State ──────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:           Annotated[list[dict], add_messages]
    query:              str
    intent:             str        # "factor_lookup" | "citation_lookup" | "comparison" | "general"
    state_filter:       str | None # e.g. "California"
    factor_filter:      str | None # e.g. "DUI/DWI"
    retrieved_statutes: list[dict]
    sources:            list[dict]
    final_answer:       str


# ── Nodes ──────────────────────────────────────────────────────────────────

def parse_query(state: AgentState) -> AgentState:
    """
    Step 1: Extract intent, state filter, and contributing factor from query.
    """
    llm = get_llm()
    query = state["query"]

    prompt = f"""Analyse this legal research query and extract structured information.

Query: "{query}"

Known US states: {", ".join(KNOWN_STATES)}
Contributing factors: {", ".join(CONTRIBUTING_FACTORS)}

Reply with ONLY valid JSON:
{{
  "intent": "factor_lookup" | "citation_lookup" | "comparison" | "general",
  "state_filter": "state name or null",
  "factor_filter": "exact contributing factor name or null"
}}

intent meanings:
- factor_lookup: asking for all statutes in a contributing factor category
- citation_lookup: asking for a specific statute by section number
- comparison: comparing the same law across multiple states
- general: anything else"""

    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        clean = response.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(clean)
        return {
            **state,
            "intent":        parsed.get("intent", "general"),
            "state_filter":  parsed.get("state_filter"),
            "factor_filter": parsed.get("factor_filter"),
        }
    except Exception:
        return {**state, "intent": "general", "state_filter": None, "factor_filter": None}


def retrieve_statutes(state: AgentState) -> AgentState:
    """
    Step 2: Retrieve relevant statutes from ChromaDB based on intent.
    """
    intent = state["intent"]
    query = state["query"]

    if intent == "factor_lookup" and state["factor_filter"]:
        results = get_by_factor(
            contributing_factor=state["factor_filter"],
            state=state["state_filter"],
        )
    else:
        results = search(
            query=query,
            n_results=8,
            state=state["state_filter"],
            contributing_factor=state["factor_filter"],
        )

    return {**state, "retrieved_statutes": results}


def synthesise_answer(state: AgentState) -> AgentState:
    """
    Step 3: Generate a cited answer using the right prompt.
    """
    llm = get_llm()
    statutes = state["retrieved_statutes"]

    # Format statutes for the prompt
    formatted = "\n\n".join(
        f"[{i+1}] {s['metadata'].get('statute', '')}\n"
        f"State: {s['metadata'].get('state', '')}\n"
        f"Contributing Factor: {s['metadata'].get('contributing_factor', '')}\n"
        f"Text: {s['text'][:400]}\n"
        f"Source: {s['metadata'].get('source_url', '')}"
        for i, s in enumerate(statutes)
    )

    if not formatted:
        formatted = "No statutes found in the database for this query."

    intent = state["intent"]
    system = AGENT_SYSTEM_PROMPT.format(factors="\n".join(f"- {f}" for f in CONTRIBUTING_FACTORS))

    if intent == "factor_lookup":
        user_content = FACTOR_LOOKUP_PROMPT.format(
            contributing_factor=state["factor_filter"] or state["query"],
            states=state["state_filter"] or "all available states",
            statutes=formatted,
        )
    elif intent == "comparison":
        user_content = COMPARISON_PROMPT.format(
            topic=state["query"],
            states=state["state_filter"] or "all available states",
            statutes=formatted,
        )
    elif intent == "citation_lookup":
        user_content = STATUTE_LOOKUP_PROMPT.format(
            query=state["query"],
            statutes=formatted,
        )
    else:
        user_content = GENERAL_PROMPT.format(
            query=state["query"],
            statutes=formatted,
        )

    history = [m for m in state["messages"] if m.get("role") in ("user", "assistant")]
    messages = history + [{"role": "user", "content": user_content}]

    answer = llm.invoke(messages, system=system) if hasattr(llm, "invoke") else llm.invoke(messages)

    sources = [
        {
            "statute":            s["metadata"].get("statute", ""),
            "state":              s["metadata"].get("state", ""),
            "section":            s["metadata"].get("section", ""),
            "contributing_factor": s["metadata"].get("contributing_factor", ""),
            "source_url":         s["metadata"].get("source_url", ""),
        }
        for s in statutes
    ]

    return {**state, "final_answer": answer, "sources": sources}


# ── Graph ──────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("parse_query", parse_query)
    graph.add_node("retrieve_statutes", retrieve_statutes)
    graph.add_node("synthesise_answer", synthesise_answer)
    graph.set_entry_point("parse_query")
    graph.add_edge("parse_query", "retrieve_statutes")
    graph.add_edge("retrieve_statutes", "synthesise_answer")
    graph.add_edge("synthesise_answer", END)
    return graph.compile()


agent = build_graph()


def run_agent(query: str, history: list[dict] | None = None) -> dict:
    initial_state: AgentState = {
        "messages":           history or [],
        "query":              query,
        "intent":             "general",
        "state_filter":       None,
        "factor_filter":      None,
        "retrieved_statutes": [],
        "sources":            [],
        "final_answer":       "",
    }
    result = agent.invoke(initial_state)
    return {
        "answer":  result["final_answer"],
        "sources": result["sources"],
        "intent":  result["intent"],
        "filters": {
            "state":  result["state_filter"],
            "factor": result["factor_filter"],
        },
    }
