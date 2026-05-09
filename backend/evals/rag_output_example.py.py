# RAG Output Format

# ── What POST /chat returns ────────────────────────────────────────────────

CHAT_RESPONSE_EXAMPLE = {
    "session_id": "3f2a1b4c-...",          # UUID string — for chat history
    "message_id": "7d9e2c1a-...",          # UUID string — for audit trail
    "answer": "Cal. Veh. Code § 23152(a) makes it unlawful...",  # LLM answer (markdown)
    "sources": [                            # list of statutes used to generate answer
        {
            "statute":              "Cal. Veh. Code § 23152(a)",   # full citation
            "state":                "California",
            "section":              "23152(a)",
            "contributing_factor":  "DUI/DWI",
            "source_url":           "https://leginfo.legislature.ca.gov/...",
        },
        {
            "statute":              "Tex. Transp. Code Ann. § 49.04",
            "state":                "Texas",
            "section":              "49.04",
            "contributing_factor":  "DUI/DWI",
            "source_url":           "https://statutes.capitol.texas.gov/...",
        },
    ],
    "intent":  "factor_lookup",   # "factor_lookup" | "citation_lookup" | "comparison" | "general"
    "filters": {
        "state":  "California",   # None if no state filter detected
        "factor": "DUI/DWI",      # None if no factor filter detected
    },
}

# ── What the evals endpoint expects (POST /eval) ──────────────────────────

EVAL_REQUEST_EXAMPLE = {
    "query":   "What is the DUI statute in California?",   # original attorney query
    "answer":  "Cal. Veh. Code § 23152(a) makes it unlawful...",  # answer from /chat
    "sources": [                                            # sources[] from /chat response
        {
            "statute":             "Cal. Veh. Code § 23152(a)",
            "state":               "California",
            "section":             "23152(a)",
            "contributing_factor": "DUI/DWI",
            "source_url":          "https://leginfo.legislature.ca.gov/...",
        }
    ],
    "contexts": [                       # optional — raw statute text chunks for RAGAS
        "it is unlawful for a person who is under the influence...",
    ],
    "method": "llm_judge",              # "llm_judge" (works now) | "ragas" (wire in later)
}

# ── What POST /eval returns ────────────────────────────────────────────────

EVAL_RESPONSE_EXAMPLE = {
    "method": "llm_judge",
    "scores": {
        "faithfulness":     4,      # 1-5: does answer match sources?
        "relevance":        5,      # 1-5: does answer address the query?
        "citation_quality": 4,      # 1-5: are citations real and specific?
        "overall":          4,      # 1-5: overall score
        "reasoning":        "Answer correctly cites § 23152(a) and addresses the query directly.",
    }
}

# ── RAGAS response shape (when wired in) ──────────────────────────────────

RAGAS_RESPONSE_EXAMPLE = {
    "method": "ragas",
    "scores": {
        "faithfulness":       0.91,   # float 0-1
        "answer_relevancy":   0.87,
        "context_precision":  0.83,
        "context_recall":     None,   # requires ground_truth — optional
    }
}

# ── What GET /statutes/search returns (raw RAG, no LLM) ──────────────────

SEARCH_RESPONSE_EXAMPLE = {
    "results": [
        {
            "id":       "ca-veh-23152a",
            "text":     "it is unlawful for a person who is under the influence...",
            "metadata": {
                "statute":             "Cal. Veh. Code § 23152(a)",
                "state":               "California",
                "universal_citation":  "Cal. Veh. Code",
                "section":             "23152(a)",
                "complete_statute":    "Pursuant to Cal. Veh. Code § 23152(a), \"...\"",
                "contributing_factor": "DUI/DWI",
                "source_url":          "https://leginfo.legislature.ca.gov/...",
                "title":               "",
                "chapter_name":        "",
                "violation_type":      "criminal",
                "severity":            "misdemeanor",
                "state_abbrev":        "CA",
            },
            "distance": 0.12,    # cosine distance — lower = more similar
        }
    ],
    "count": 1,
}

# ── How to call /eval in Python for testing ───────────────────────────────
#
# import httpx
#
# # 1. Get an answer from /chat
# chat_resp = httpx.post("http://localhost:8000/chat", json={
#     "query": "What is the DUI statute in California?"
# }).json()
#
# # 2. Pass it straight to /eval
# eval_resp = httpx.post("http://localhost:8000/eval", json={
#     "query":   "What is the DUI statute in California?",
#     "answer":  chat_resp["answer"],
#     "sources": chat_resp["sources"],
#     "method":  "llm_judge",
# }).json()
#
# print(eval_resp["scores"])
