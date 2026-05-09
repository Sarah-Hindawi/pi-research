# Workplace - Legal Research for PI Attorneys


A queryable database of US motor vehicle statutes tagged by contributing factor, built for personal injury attorneys. Ingests vehicle codes across 14+ states, classifies every statute into 17 contributing factor categories, and exposes a paralegal-friendly chat interface with cited, source-backed answers.

---

## Quickstart

```bash
# Backend
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

# Add API key to .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
echo "LLM_PROVIDER=anthropic" >> .env

# Seed the 41 CA eval statutes (run first)
python -m rag.embedding.ingest --file data/statutes.json

# Start backend
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Architecture

```
Attorney types query (React UI)
        ↓
  FastAPI  /chat
        ↓
  LangGraph Agent
  ├── parse_query     → detects intent + state/factor filters
  ├── retrieve        → ChromaDB semantic search (RAG)
  └── synthesise      → Claude generates cited answer
        ↓
  SQLite  (chat history + audit trail)
        ↓
  LLM-as-judge eval   → confidence score on every answer
        ↓
  React UI renders answer + sources + confidence badge
```

---

## Stack

### Backend
| Layer | Technology | Why |
|---|---|---|
| API | FastAPI | Async, fast, auto-docs at `/docs` |
| Agent | LangGraph | Multi-step RAG orchestration with state |
| LLM | Anthropic Claude (claude-sonnet-4) | Cited answers, structured extraction, eval judge |
| Vector DB | ChromaDB (persistent) | Local, no infra, cosine similarity |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Free, runs locally, no API key needed |
| Chat history | SQLite | Lightweight, persistent, audit trail |
| Scraping | httpx + BeautifulSoup | Async scraping of 14 state legislature sites |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + Vite |
| Styling | Tailwind CSS |
| Markdown | react-markdown |
| PDF export | jsPDF |

### Data Pipeline
```
State legislature websites (14 states)
        ↓
  httpx async scraper (Justia fallback)
        ↓
  JSON normalizer → deduplication
        ↓
  Claude classifier → 17 contributing factor categories
        ↓
  sentence-transformers → embeddings
        ↓
  ChromaDB (386 statutes, 14 states)
```

---

## Key Numbers

| Metric | Value |
|---|---|
| Statutes indexed | 386 |
| States covered | 14 (CA, TX, NY, FL, IL, PA, OH, GA, WA, AZ, CO, MI, NJ, NC) |
| Contributing factor categories | 17 |
| Eval dimensions | 4 (correctness, faithfulness, relevance, completeness) |
| Embedding model | all-MiniLM-L6-v2 (384-dim, local) |
| Chat history | SQLite — full audit trail per session |

---

## API Routes

| Route | Description |
|---|---|
| `POST /chat` | Main chatbot — agent + RAG + LLM |
| `GET /statutes/search?q=&state=&factor=` | Direct semantic search |
| `GET /statutes/by-factor?factor=DUI/DWI&state=Texas` | Factor lookup |
| `GET /statutes/by-citation?citation=...` | Exact citation lookup |
| `GET /statutes/normalize-citation?raw=CVC 21451` | Fuzzy citation normalizer |
| `POST /eval` | LLM-as-judge scoring |
| `GET /coverage` | Which states/factors are thin |
| `GET /stats` | DB stats |
| `GET /sessions` | Chat session list |
| `GET /sessions/{id}/history` | Full audit trail for a session |

---

## Contributing Factor Categories (17)

The 17 categories from the released eval set — every statute is classified into one:

`DUI/DWI` · `Failure to Maintain Lane` · `Failure to Obey Traffic Control Device` · `Failure to Use/Activate Horn` · `Failure to Yield` · `Fleeing a Police Officer` · `Fleeing the Scene of a Collision` · `Improper Passing` · `Improper Stopping` · `Improper Turning` · `Reckless Driving` · `Using a Wireless Telephone/Texting While Driving` · `Driving Too Fast For Conditions` · `Speeding` · `Following Too Closely` · `Improper Lane Change` · `Other`

---

## Eval System

Every chat answer is automatically scored by Claude acting as a judge:

| Dimension | Weight | What it measures |
|---|---|---|
| Correctness | 35% | Do cited statutes directly answer the query? |
| Faithfulness | 30% | Does the answer accurately reflect statute text? |
| Relevance | 20% | Are the statutes relevant to the legal question? |
| Completeness | 15% | Were important statutes missed? |

Verdict: **pass** (≥75%) · **partial** (≥45%) · **fail** (<45%)

Score is shown as a confidence badge on every answer in the UI.

---

## Folder Structure

```
pi-research/
├── backend/
│   ├── api/
│   │   └── main.py              ← FastAPI routes
│   ├── agent/
│   │   └── orchestrator.py      ← LangGraph agent
│   ├── rag/
│   │   ├── embedding/
│   │   │   ├── ingest.py        ← JSON → ChromaDB
│   │   │   └── classifier.py   ← Claude contributing factor classifier
│   │   └── retrieval/
│   │       ├── store.py         ← ChromaDB wrapper
│   │       └── query.py         ← RAG query functions
│   ├── ingestion/
│   │   ├── agent_scraper.py     ← Agentic 50-state scraper
│   │   ├── citation_normalizer.py ← Fuzzy citation matching
│   │   ├── coverage_gap.py      ← Which states/factors are thin
│   │   └── state_urls.py        ← Official legislature URLs for all 50 states
│   ├── evals/
│   │   └── evaluator.py         ← LLM-as-judge + RAGAS stub 
│   ├── prompts/
│   │   └── templates.py         ← All LLM prompts
│   ├── db/
│   │   └── chat_store.py        ← SQLite chat history
│   ├── data/
│   │   ├── eval-ca-vehicle-code.csv  ← 41 CA eval statutes
│   │   └── statutes.json             ← scraped statute data
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx              ← Main UI
│       ├── hooks/useChat.js     ← Session + message state
│       └── api/client.js        ← Backend API calls
└── README.md
```
