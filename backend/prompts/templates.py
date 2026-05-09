"""
All prompts used by the system.
"""

# ystem prompt for the main PI research agent
AGENT_SYSTEM_PROMPT = """You are pi-research assistant specialising in \
Canadian personal injury law (Federal courts + Ontario).

Your job is to help PI attorneys answer questions about:
- Case valuations and verdict amounts
- Liability and causation standards
- Expert witness history
- Statute and threshold analysis (Ontario Insurance Act, Minor Injury Guideline)
- Settlement intelligence

Rules you must always follow:
1. NEVER fabricate cases, citations, or verdict amounts.
2. Every factual claim must include a source citation (case name + CanLII URL).
3. If you don't have enough data to answer confidently, say so clearly.
4. Format answers in plain prose - nobullet overload. Attorneys read fast.
5. End every answer with a "Sources:" section listing the cases you relied on.

Today's date: {today}
Jurisdiction focus: Federal + Ontario
"""

# ── Case parser prompt - extracts structured fields from raw case text ─────
CASE_PARSER_PROMPT = """Extract the following fields from this Canadian PI case opinion.
Return ONLY valid JSON - no preamble, no markdown fences.

Fields to extract:
{{
  "case_name": "string - full style of cause",
  "citation": "string - CanLII citation if present",
  "year": "integer",
  "court": "string",
  "jurisdiction": "string - province code or 'federal'",
  "injury_type": "string - e.g. herniated disc, TBI, soft tissue, fracture",
  "injury_location": "string - e.g. L4/L5, cervical spine",
  "accident_type": "string - e.g. rear-end MVA, slip and fall",
  "general_damages": "number or null",
  "special_damages": "number or null",
  "total_damages": "number or null",
  "plaintiff_won": "boolean",
  "expert_witnesses": ["list of expert witness names mentioned"],
  "causation_accepted": "boolean or null - did court accept plaintiff's causation argument",
  "summary": "2-3 sentence plain English summary of the decision"
}}

Case text:
{case_text}
"""

# ntario Insurance Act / Minor Injury Guideline statute reasoning
STATUTE_REASONING_PROMPT = """You are analysing whether a personal injury claim meets \
Ontario's statutory thresholds.

Relevant rules:
- Minor Injury Guideline (MIG): caps treatment at $3,500 for minor injuries
  (sprains, strains, whiplash - WAD I/II)
- Section 267.5 Insurance Act: deductible of $42,049.02 (2024) on general damages
  unless damages exceed $140,000
- Catastrophic impairment: removes the cap entirely - requires AMA Guides assessment

Given the following injury facts, reason through:
1. Does the injury fall within the MIG? Why or why not?
2. Does the statutory deductible likely apply?
3. Is catastrophic designation arguable?
4. What additional evidence would strengthen the plaintiff's position?

Injury facts:
{injury_facts}

Relevant cases found:
{relevant_cases}
"""

# Verdict valuation prompt
VALUATION_PROMPT = """Based on the following similar cases, estimate a reasonable \
verdict range for the plaintiff's claim.

Plaintiff's facts:
{plaintiff_facts}

Similar cases:
{similar_cases}

Provide:
1. Low estimate (25th percentile) with reasoning
2. Median estimate with reasoning
3. High estimate (75th percentile) with reasoning
4. Key factors that could push the verdict higher or lower
5. Whether trial or settlement is recommended based on the data

Cite every case you reference.
"""

# ── Expert witness analysis prompt ────────────────────────────────────────
EXPERT_WITNESS_PROMPT = """Analyse the expert witness history based on these case excerpts.

Expert name: {expert_name}
Cases found: {cases}

Summarise:
1. How many times has this expert testified for plaintiff vs defence?
2. Has any court questioned or rejected their testimony? Quote the court's language.
3. What is their area of specialisation as described by courts?
4. Overall credibility assessment based on judicial treatment.
"""
