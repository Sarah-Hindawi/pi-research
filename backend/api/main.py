"""
FastAPI backend — statute harvester.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import get_settings
from db.chat_store import init_db, create_session, add_message, get_history, get_sessions
from agent.orchestrator import run_agent
from retrieval.vector_store import (
    count, list_states, list_factors,
    search, get_by_factor, get_by_citation,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="OpenClaw Harvester API",
    description="US Vehicle Code Statute Research",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str | None = None
    query: str


class StatuteSource(BaseModel):
    statute: str
    state: str
    section: str
    contributing_factor: str
    source_url: str


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: list[StatuteSource]
    intent: str
    filters: dict


# ── Chat route ─────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or create_session()
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in get_history(session_id)
    ]
    add_message(session_id, role="user", content=req.query)
    try:
        result = run_agent(query=req.query, history=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    msg_id = add_message(
        session_id,
        role="assistant",
        content=result["answer"],
        sources=result["sources"],
    )
    return ChatResponse(
        session_id=session_id,
        message_id=msg_id,
        answer=result["answer"],
        sources=[StatuteSource(**s) for s in result["sources"]],
        intent=result["intent"],
        filters=result["filters"],
    )


# ── Statute-specific routes ────────────────────────────────────────────────

@app.get("/statutes/search")
def statute_search(
    q: str,
    state: str | None = None,
    factor: str | None = None,
    n: int = 10,
):
    """Direct semantic search — for the eval queries."""
    results = search(query=q, n_results=n, state=state, contributing_factor=factor)
    return {"results": results, "count": len(results)}


@app.get("/statutes/by-factor")
def statutes_by_factor(factor: str, state: str | None = None):
    """Get all statutes for a contributing factor, optionally by state."""
    results = get_by_factor(contributing_factor=factor, state=state)
    return {"factor": factor, "state": state, "results": results, "count": len(results)}


@app.get("/statutes/by-citation")
def statute_by_citation(citation: str):
    """Exact citation lookup e.g. 'Cal. Veh. Code § 22350'"""
    result = get_by_citation(citation)
    if not result:
        raise HTTPException(status_code=404, detail=f"Citation not found: {citation}")
    return result


@app.get("/statutes/states")
def get_states():
    """List all states in the DB."""
    return {"states": list_states()}


@app.get("/statutes/factors")
def get_factors():
    """List all contributing factors in the DB."""
    return {"factors": list_factors()}


# ── Session routes ─────────────────────────────────────────────────────────

@app.get("/sessions")
def list_sessions_route():
    return get_sessions()


@app.get("/sessions/{session_id}/history")
def session_history(session_id: str):
    messages = get_history(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


# ── Health & stats ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}


@app.get("/stats")
def stats():
    return {
        "statutes_indexed": count(),
        "states":           list_states(),
        "factors":          list_factors(),
        "llm_provider":     settings.llm_provider,
    }
