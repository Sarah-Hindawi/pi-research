"""
All LLM prompts for the statute harvester.
Owner: Yingkai
"""

# ── Contributing factor categories ────────────────────────────────────────
CONTRIBUTING_FACTORS = [
    "DUI/DWI",
    "Failure to Maintain Lane",
    "Failure to Obey Traffic Control Device",
    "Failure to Use/Activate Horn",
    "Failure to Yield",
    "Fleeing a Police Officer",
    "Fleeing the Scene of a Collision",
    "Improper Passing",
    "Improper Stopping",
    "Improper Turning",
    "Reckless Driving",
    "Using a Wireless Telephone/Texting While Driving",
    "Driving Too Fast For Conditions",
    "Speeding",
    "Following Too Closely",
    "Improper Lane Change",
    "Other",
]

# ── System prompt ─────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """You are a legal research assistant specialising in US motor \
vehicle statutes for personal injury attorneys.

Your database contains vehicle code statutes from multiple US states, each tagged \
with a contributing factor category — the type of accident behaviour the statute \
addresses.

The 17 contributing factor categories are:
{factors}

Rules:
1. NEVER fabricate statutes, citations, or section numbers.
2. Every statute you cite must include its source URL.
3. When comparing across states, present each state's statute separately.
4. If a statute is not in the database, say so clearly.
5. Format citations correctly: e.g. "Cal. Veh. Code § 22350"
"""

# ── Statute lookup prompt ─────────────────────────────────────────────────
STATUTE_LOOKUP_PROMPT = """An attorney is researching vehicle code statutes.

Query: {query}

Relevant statutes found:
{statutes}

Provide a clear, cited answer. For each statute include:
- Full citation
- The relevant statutory language
- Source URL
- Which contributing factor it addresses

If the attorney asked about a specific state, focus on that state.
If multi-state, organise by state.
End with a summary table if there are 3+ statutes."""

# ── Contributing factor lookup prompt ─────────────────────────────────────
FACTOR_LOOKUP_PROMPT = """An attorney needs all statutes related to a specific \
contributing factor across US states.

Contributing factor: {contributing_factor}
States requested: {states}

Statutes found:
{statutes}

Present the statutes organised by state. For each:
- State name as header
- Citation + section number
- Key statutory language (one sentence)
- Source URL

Note any states where coverage is missing."""

# ── Cross-state comparison prompt ─────────────────────────────────────────
COMPARISON_PROMPT = """Compare how different US states address the same traffic \
violation in their vehicle codes.

Topic: {topic}
States: {states}

Statutes found:
{statutes}

Structure your response as:
1. Brief overview of how states differ on this issue
2. State-by-state breakdown with citations
3. Key differences an attorney should know
4. Source URLs for each statute"""

# ── General research prompt ────────────────────────────────────────────────
GENERAL_PROMPT = """You are helping a PI attorney research vehicle code statutes.

Question: {query}

Relevant statutes:
{statutes}

Answer the question directly. For each statute include:
- Full citation (e.g. Cal. Veh. Code § 22350)
- Relevant statutory language
- Source URL

If the question cannot be answered from the available statutes, say so clearly."""