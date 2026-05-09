"""
FastAPI backend - main entry point.
Exposes chat, history, and session endpoints.
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

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="OpenClaw API",
    description="PI Legal Research - Federal + Ontario",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str | None = None   # None = start new session
    query: str


class Source(BaseModel):
    case_name: str
    citation: str
    url: str
    year: str | int
    jurisdiction: str


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: list[Source]
    intent: str


class SessionResponse(BaseModel):
    session_id: str
    label: str | None
    created_at: str
    last_activity: str | None


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Main chat endpoint.
    - Creates a new session if session_id not provided.
    - Loads history, runs agent, saves messages, returns answer + sources.
    """
    # Session management
    session_id = req.session_id or create_session()

    # Load conversation history for context
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in get_history(session_id)
    ]

    # Save user message
    add_message(session_id, role="user", content=req.query)

    # Run agent
    try:
        result = run_agent(query=req.query, history=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save assistant message with sources for audit trail
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
        sources=[Source(**s) for s in result["sources"]],
        intent=result["intent"],
    )


@app.get("/sessions", response_model=list[SessionResponse])
def list_sessions():
    """Return all past sessions for the sidebar history."""
    return [SessionResponse(**s) for s in get_sessions()]


@app.get("/sessions/{session_id}/history")
def session_history(session_id: str):
    """Return full message history for a session (audit trail)."""
    messages = get_history(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Clear a session from history."""
    import sqlite3
    from pathlib import Path
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path)
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"deleted": session_id}


@app.get("/stats")
def stats():
    """Quick stats for the UI - cases indexed etc."""
    from retrieval.vector_store import count
    return {
        "cases_indexed": count(),
        "llm_provider": settings.llm_provider,
        "jurisdictions": ["Ontario", "Federal"],
    }
