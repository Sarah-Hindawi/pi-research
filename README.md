# PI Legal Research Tool

A hybrid RAG + agentic legal research assistant for personal injury law (Federal + Ontario).


## Architecture

```
User query (React chat UI)
       ↓
  FastAPI backend
       ↓
  Agent (LangGraph)
  ├── RAG tool → ChromaDB (pre-ingested CanLII cases)
  ├── Live search tool → CanLII API (real-time fallback)
  └── PDF extract tool → Claude Vision
       ↓
  LLM (Anthropic Claude — key provided day-of)
       ↓
  Cited answer + sources → chat history (SQLite)
```

---

## Quickstart

```bash
# 1. Clone and install
git clone <repo>
cd pi-research

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Set env vars
cp .env.example .env
# Edit .env - add CANLII_API_KEY (free at canlii.org/en/tools/api)
# ANTHROPIC_API_KEY left blank until day-of

# 4. Ingest seed data (Sarah runs this)
python -m ingestion.canlii_scraper

# 5. Run backend
uvicorn api.main:app --reload --port 8000

# 6. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Environment Variables

See `.env.example` for all vars. Key ones:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Leave blank until day-of |
| `CANLII_API_KEY` | Free - register at api.canlii.org |
| `LLM_PROVIDER` | `anthropic` (default) or `placeholder` |
| `CHROMA_PATH` | Path to ChromaDB storage (default: `./data/chroma`) |
| `SQLITE_PATH` | Path to chat history DB (default: `./data/chat.db`) |

---

## Stack

- **Backend**: FastAPI, LangGraph, ChromaDB, SQLite
- **LLM**: Anthropic Claude (placeholder until key provided)
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (free, local)
- **Frontend**: React + Vite
- **Data**: CanLII API (Federal + Ontario), Claude Vision for PDFs
- **Evals**: RAGAS stub + LLM-as-judge stub

---

## Folder Structure

```
openclaw/
├── backend/
│   ├── api/              # FastAPI routes
│   ├── agent/            # LangGraph agent
│   ├── ingestion/        # CanLII scraper + PDF extractor
│   ├── retrieval/        # ChromaDB wrapper + embedding
│   ├── prompts/          # All LLM prompts
│   ├── db/               # SQLite chat history
│   ├── evals/            # RAGAS + LLM-as-judge stubs
│   └── requirements.txt
├── frontend/             # React app
│   └── src/
│       ├── components/
│       ├── hooks/
│       └── api/
├── scripts/              # One-off utility scripts
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example
└── README.md
```
