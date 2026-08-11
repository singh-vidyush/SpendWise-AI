"""
LangGraph multi-agent architecture for SpendWise-AI.

Agents & Nodes:
  1. intake_agent               – validates and stores user data via vector_store.py
  2. intent_router              – classifies requests into conversational, financial_analysis, report_generation, follow_up
  3. conversational_reply_agent – handles conversational queries using profile & RAG context
  4. rag_react_agent            – ReAct: queries ChromaDB (knowledge, expense history, past reports)
  5. market_react_agent         – ReAct: queries Tavily web search for live market rates/inflation
  6. calculator_agent           – deterministic financial calculations (surplus, DTI, tax, net worth)
  7. recommendation_agent       – reflection pattern: drafts & refines personalized recommendations
  8. trade_off_agent            – generates alternative strategies with trade-offs & priority levels
  9. critic_agent               – validates correctness, consistency, and feasibility (max 2 cycles)
 10. report_agent               – generates PDF report via ReportLab, populates dashboard & summary
"""

import json
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from config import GEMINI_API_KEY
from agents.tools import calculation_tool, tavily_search_tool, pdf_report_tool
from db.vector_store import (
    upsert_user_profile,
    get_user_profile,
    query_collection,
    financial_knowledge_collection,
    expense_history_collection,
    past_reports_collection
)



# ---------------------------------------------------------------------------
# State Definition
# ---------------------------------------------------------------------------
class FinancialPlanningState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

    session_id: str
    user_id: str
    user_name: str
    person_type: str

    user_data_json: str
    profile: Dict[str, Any]

    query: str
    intent: str  # conversational | financial_analysis 

    retrieved_context: Dict[str, Any]
    market_context: str

    financial_metrics: Dict[str, Any]
    structured_recs: List[Dict]      # structured recs: priority/category/action/impact/deadline
    recommendations: List[Any]       # legacy flat list kept for backward compat
    tradeoff_analysis: List[Any]

    critic_feedback: str
    revision_count: int

    pdf_path: str
    response_text: str
    



# ---------------------------------------------------------------------------
# LLM Initialization
# ---------------------------------------------------------------------------
def _llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        api_key=GEMINI_API_KEY,
        temperature=0.3,
    )


def extract_response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                text_parts.append(item.get("text", ""))
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)
    return str(content)


# ---------------------------------------------------------------------------
# Node 1: Intake Agent
# ---------------------------------------------------------------------------
def intake_agent(state):
    profile = state.get("profile") or get_user_profile(state["user_id"]) or {}

    profile = json.loads(
        upsert_user_profile(
            state["user_id"],
            profile,
            state["session_id"]
        )
    )

    return {
        "profile": profile,
        "messages": [
            AIMessage(content="Profile processed")
        ],
    }


# ---------------------------------------------------------------------------
# Node 2: Intent Router
# Three-class: greeting | conversational | financial_analysis
# Rule-based fast path → LLM fallback with few-shot examples for ambiguous
# ---------------------------------------------------------------------------
_GREETING_WORDS = {"hi", "hello", "hey", "hii", "helo", "good morning",
                   "good evening", "good afternoon", "sup", "yo", "namaste"}

def intent_router(state):
    query = state.get("query", "").strip()
    q_lower = query.lower()

    # Fast path 1: pure greeting
    if q_lower in _GREETING_WORDS or (len(q_lower.split()) <= 3 and
       any(q_lower.startswith(g) for g in _GREETING_WORDS)):
        return {"intent": "conversational"}

    # Fast path 2: clear financial analysis signals
    _ANALYSIS_SIGNALS = [
        "my budget", "my expenses", "my savings", "my dti", "analyze my",
        "should i invest", "how much should i", "plan my", "review my",
        "for me", "my income", "my emi", "my salary",
    ]
    if any(sig in q_lower for sig in _ANALYSIS_SIGNALS):
        return {"intent": "financial_analysis"}

    # Fast path 3: pure definition queries with NO personal context
    _PURE_DEFINITION = ("what is ", "what are ", "define ", "explain ",
                        "how does ", "tell me about ")
    if any(q_lower.startswith(p) for p in _PURE_DEFINITION):
        # BUT: if it also has a personal pronoun it’s analysis
        if not any(w in q_lower for w in [" my ", " i ", " me ", " mine "]):
            return {"intent": "conversational"}

    # LLM fallback with few-shot examples for ambiguous cases
    try:
        prompt = f"""Classify the user query into EXACTLY one of: conversational, financial_analysis

Rules:
- conversational: general greetings, educational "what is X" questions with no personal context
- financial_analysis: anything involving the user’s own money, analysis, planning, or advice

Few-shot examples:
Q: "what is SIP?"             → conversational
Q: "what SIP should I start?" → financial_analysis
Q: "explain mutual funds"     → conversational
Q: "is my savings rate ok?"   → financial_analysis
Q: "how does EMI work?"       → conversational
Q: "should I prepay my EMI?"  → financial_analysis

Query: "{query}"

Respond with ONLY the class name, nothing else."""
        resp = extract_response_text(_llm().invoke([HumanMessage(content=prompt)]).content).strip().lower()
        intent = "conversational" if "conversational" in resp else "financial_analysis"
    except Exception:
        intent = "financial_analysis"

    return {"intent": intent}


def route_decision(state: FinancialPlanningState) -> str:
    return "conversational_reply_agent" if state.get("intent") == "conversational" else "rag_react_agent"


# ---------------------------------------------------------------------------
# Node 3: Conversational Reply Agent
# Uses: (a) retrieved_context already in state (avoids duplicate RAG call)
#       (b) metadata-filtered fallback query if context is empty
#       (c) chat history from messages for stateful multi-turn responses
# ---------------------------------------------------------------------------
def conversational_reply_agent(state):
    query   = state.get("query", "")
    profile = state.get("profile", {})
    fin     = profile.get("financial_profile", {})
    persona = state.get("person_type", "Salaried")

    # (a) Re-use knowledge already retrieved by rag_react if present
    ctx = state.get("retrieved_context", {})
    knowledge_snippets = ctx.get("knowledge_snippets", [])

    # (b) Fallback: do a targeted query if RAG context is empty
    if not knowledge_snippets:
        relevant_cats = _PERSONA_CATEGORIES.get(persona.lower(), _KNOWLEDGE_CATEGORIES)
        hits = []
        for cat in relevant_cats[:2]:
            try:
                hits += query_collection(
                    financial_knowledge_collection(), query,
                    n_results=2,
                    where={"category": {"$eq": cat}},
                    include_metadata=True
                )
            except Exception:
                pass
        # format with section title
        knowledge_snippets = [
            f"[{h.get('metadata',{}).get('category','').upper()} | "
            f"{h.get('metadata',{}).get('section_title','')}] {h.get('text','')}"
            if isinstance(h, dict) else str(h)
            for h in hits
        ]

    context_text = "\n\n".join(knowledge_snippets[:4])

    # (c) Build chat history for multi-turn context (last 6 messages)
    history_msgs = [
        m for m in state.get("messages", [])[-6:]
        if isinstance(m, (HumanMessage, AIMessage))
    ]

    system_msg = HumanMessage(content=f"""You are SpendWise, an expert AI financial advisor.

User: {profile.get('user_name', 'User')} | Persona: {fin.get('persona', persona)}

Behaviour rules:
- For greetings only: respond warmly in 1-2 sentences, mention the user’s name.
- For educational questions ("what is X"): answer clearly using the knowledge context below.
- For personal finance questions: use user profile data to personalise the answer.
- Never make up numbers. Only cite figures from the context provided.
- Keep answers concise (≤ 5 sentences unless the question requires more detail).

Knowledge Context:
{context_text or 'No specific context available.'}

User question: {query}""")

    messages_to_send = [system_msg] + history_msgs
    answer = extract_response_text(_llm().invoke(messages_to_send).content)
    return {"response_text": answer}


# ---------------------------------------------------------------------------
# Node 4: RAG Agent (ReAct Pattern)
# THINK: LLM reasons which topics + which collections to query
# ACT:   Multi-collection retrieval with metadata filtering by persona + category
# OBSERVE: Coverage gap detection across knowledge categories; follow-up if needed
# ---------------------------------------------------------------------------

# Knowledge categories available in ChromaDB
_KNOWLEDGE_CATEGORIES = ["tax", "investment", "debt", "insurance", "savings", "income"]

# Persona → relevant categories mapping for metadata pre-filtering
_PERSONA_CATEGORIES = {
    "salaried":  ["tax", "investment", "debt", "savings", "insurance"],
    "student":   ["savings", "debt", "income", "investment"],
    "retiree":   ["tax", "investment", "insurance", "income"],
    "freelancer":["tax", "income", "savings", "investment"],
}

def rag_react_agent(state):
    user_data = json.loads(state.get("user_data_json", "{}"))
    query     = state.get("query", "")
    profile   = state.get("profile", {})
    fin       = profile.get("financial_profile", {})
    persona   = user_data.get("person_type", state.get("person_type", "salaried")).lower()

    # Relevant categories for this persona — used for metadata filtering
    relevant_cats = _PERSONA_CATEGORIES.get(persona, _KNOWLEDGE_CATEGORIES)

    # --- THINK: generate targeted, context-aware queries ---
    think_prompt = f"""You are a financial knowledge retrieval planner.

User context:
  Persona:        {persona}
  Monthly income: ₹{user_data.get('monthly_income', 0):,}
  House EMI:      ₹{user_data.get('house_emi', 0):,}
  User question:  {query}

Available knowledge categories: {', '.join(_KNOWLEDGE_CATEGORIES)}
Most relevant for this persona ({persona}): {', '.join(relevant_cats)}

Generate EXACTLY 4 specific ChromaDB search queries that together cover:
  1. The user's direct question topic
  2. A relevant tax/investment rule for a {persona}
  3. A debt/savings guideline given their EMI level
  4. A goal-planning or SIP strategy for their income bracket

Each query should be 5-12 words and include a category keyword from the available list.
Output ONLY a valid JSON array of 4 strings. Example: ["query1","query2","query3","query4"]"""

    try:
        think_resp = _llm().invoke([HumanMessage(content=think_prompt)])
        raw = extract_response_text(think_resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        queries = json.loads(raw)
        if not isinstance(queries, list):
            raise ValueError("Not a list")
        queries = [str(q) for q in queries[:4]]
    except Exception:
        queries = [
            f"{persona} financial planning India",
            f"SIP investment strategy {persona}",
            "debt EMI management guidelines India",
            "emergency fund savings rate best practices",
        ]

    # --- ACT: multi-collection retrieval WITH metadata filtering ---
    knowledge_rich, expense_rich, report_rich = [], [], []

    for q in queries:
        # Per-category filtered queries for the top 2 most relevant categories
        for cat in relevant_cats[:2]:
            try:
                where_filter = {"category": {"$eq": cat}}
                hits = query_collection(
                    financial_knowledge_collection(), q,
                    n_results=2, where=where_filter, include_metadata=True
                )
                knowledge_rich.extend(hits)
            except Exception:
                pass
        # Also run unfiltered to avoid missing relevant content
        unfiltered = query_collection(
            financial_knowledge_collection(), q,
            n_results=2, include_metadata=True
        )
        knowledge_rich.extend(unfiltered)

    # Expense history and past reports (no persona filter needed)
    for q in queries[:2]:
        expense_rich  += query_collection(expense_history_collection(), q, n_results=2, include_metadata=True)
        report_rich   += query_collection(past_reports_collection(),    q, n_results=2, include_metadata=True)

    # Deduplicate by text
    def _dedup(items):
        seen, out = set(), []
        for item in items:
            txt = item["text"] if isinstance(item, dict) else item
            if txt not in seen:
                seen.add(txt)
                out.append(item)
        return out

    knowledge_rich = _dedup(knowledge_rich)
    expense_rich   = _dedup(expense_rich)
    report_rich    = _dedup(report_rich)

    # Format with section title as context anchor for LLM
    def _format_with_title(items: list) -> list[str]:
        out = []
        for item in items:
            if isinstance(item, dict):
                title = item.get("metadata", {}).get("section_title", "")
                text  = item.get("text", "")
                cat   = item.get("metadata", {}).get("category", "")
                label = f"[{cat.upper()} | {title}] " if (title or cat) else ""
                out.append(f"{label}{text}")
            else:
                out.append(str(item))
        return out

    knowledge_snippets = _format_with_title(knowledge_rich)
    expense_snippets   = _format_with_title(expense_rich)
    report_snippets    = _format_with_title(report_rich)

    # --- OBSERVE: category coverage gap detection ---
    # Check which knowledge categories are present in retrieved docs
    retrieved_cats = {
        item.get("metadata", {}).get("category", "")
        for item in knowledge_rich if isinstance(item, dict)
    }
    missing_cats = [c for c in relevant_cats if c not in retrieved_cats]

    gap_query = None
    if missing_cats:
        gap_cat   = missing_cats[0]
        gap_query = f"{gap_cat} planning guidelines for {persona} India"
        try:
            gap_hits = query_collection(
                financial_knowledge_collection(), gap_query,
                n_results=3, include_metadata=True
            )
            if gap_hits:
                knowledge_snippets += _format_with_title(gap_hits)
        except Exception:
            pass

    return {
        "retrieved_context": {
            "knowledge_snippets":   knowledge_snippets,
            "expense_snippets":     expense_snippets,
            "past_report_snippets": report_snippets,
            "queries_used":         queries,
            "categories_retrieved": list(retrieved_cats),
            "gap_category":         gap_cat if gap_query else None,
        },
        "messages": [AIMessage(
            content=f"[ReAct RAG] Queries: {queries}. "
                    f"Retrieved: {len(knowledge_snippets)} knowledge "
                    f"({len(retrieved_cats)} categories), "
                    f"{len(expense_snippets)} expense, {len(report_snippets)} report docs. "
                    f"Gap fill: {gap_query or 'none'}."
        )],
    }


# ---------------------------------------------------------------------------
# Node 5: Market Research Agent (ReAct Pattern)
# THINK: identify persona-relevant market topics
# ACT:   targeted Tavily searches
# OBSERVE: LLM evaluates relevance of each result; triggers corrective search if weak
# ---------------------------------------------------------------------------
def market_react_agent(state):
    persona   = state.get("person_type", "Salaried")
    query     = state.get("query", "")
    user_data = json.loads(state.get("user_data_json", "{}"))

    # --- THINK ---
    think_prompt = f"""You are a financial market research planner.
User persona: {persona}, monthly income ₹{user_data.get('monthly_income', 0):,}.
User question: {query}

Generate EXACTLY 2 specific Indian financial market web-search queries most relevant
to this user right now (e.g. interest rates, inflation, mutual fund returns, RBI policy).
Output ONLY a valid JSON array of 2 strings. Example: ["query1","query2"]"""

    try:
        think_resp = _llm().invoke([HumanMessage(content=think_prompt)])
        raw = extract_response_text(think_resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        queries = json.loads(raw)
        if not isinstance(queries, list):
            raise ValueError
        queries = [str(q) for q in queries[:2]]
    except Exception:
        queries = [
            f"India inflation RBI policy {persona} 2024",
            "India equity mutual fund SIP returns 2024",
        ]

    # --- ACT ---
    raw_results = []
    for q in queries:
        result = tavily_search_tool.invoke({"query": q})
        raw_results.append({"query": q, "result": result or ""})

    # --- OBSERVE: LLM evaluates relevance; triggers corrective search if needed ---
    observe_prompt = f"""You received these web search results for a {persona} user asking: "{query}"

Results:
{json.dumps([{"q": r['query'], "snippet": r['result'][:300]} for r in raw_results], indent=2)}

For EACH result, rate relevance: HIGH, MEDIUM, or LOW.
If ANY result is LOW relevance, provide ONE corrective search query.

Respond with a JSON object:
{{
  "ratings": [{{"query": "...", "relevance": "HIGH|MEDIUM|LOW"}}],
  "corrective_query": "<query string or null>"
}}
No extra text."""

    corrective_query = None
    try:
        obs_resp = _llm().invoke([HumanMessage(content=observe_prompt)])
        obs_raw  = extract_response_text(obs_resp.content).strip()
        if obs_raw.startswith("```"):
            obs_raw = obs_raw.split("```")[1]
            if obs_raw.startswith("json"):
                obs_raw = obs_raw[4:]
        obs_data = json.loads(obs_raw)
        corrective_query = obs_data.get("corrective_query")
        if corrective_query:
            extra = tavily_search_tool.invoke({"query": corrective_query})
            if extra:
                raw_results.append({"query": corrective_query, "result": extra})
    except Exception:
        pass

    snippets = [
        f"### {r['query']}\n{r['result']}"
        for r in raw_results if r.get("result") and "Error" not in str(r["result"])
    ]
    combined = "\n\n".join(snippets) if snippets else "Market data unavailable."
    return {
        "market_context": combined,
        "messages": [AIMessage(
            content=f"[ReAct Market] Queries: {queries}. "
                    f"Corrective: {corrective_query or 'none'}. "
                    f"Fetched {len(snippets)} final snippets."
        )],
    }


# ---------------------------------------------------------------------------
# Node 6: Calculator Agent
# ---------------------------------------------------------------------------
def calculator_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    user_data = state.get("user_data_json", "{}")
    calc_res = calculation_tool.invoke({"user_data": user_data})
    calc_dict = json.loads(calc_res)

    return {
        "financial_metrics": calc_dict,
        "messages": [AIMessage(content=f"[Calculator Agent] Surplus: ₹{calc_dict.get('monthly_surplus',0):,.2f}, Savings Rate: {calc_dict.get('savings_rate_pct',0)}%")],
    }


# ---------------------------------------------------------------------------
# Node 7: Recommendation Agent (Reflection Pattern)
# DRAFT:   Generate structured recommendations with priority/category/action/impact
# REFLECT: Self-critique for feasibility, specificity, completeness
# FINALISE: Incorporate critic feedback if present
# ---------------------------------------------------------------------------

_REC_SCHEMA = """Each recommendation MUST be a JSON object with these EXACT keys:
{
  "priority": "high" | "medium" | "low",
  "category": "savings" | "investment" | "debt" | "insurance" | "tax" | "emergency",
  "title": "Short action title (max 8 words)",
  "action": "Specific step the user must take, with exact ₹ amounts",
  "impact": "Quantified benefit e.g. ₹2,000/month saved or 12% CAGR expected",
  "deadline": "immediate" | "1 month" | "3 months" | "6 months" | "1 year",
  "rationale": "1-2 sentence justification using the user's actual numbers"
}"""

def recommendation_agent(state):
    metrics  = state.get("financial_metrics", {})
    market   = state.get("market_context", "")
    feedback = state.get("critic_feedback", "")
    ctx      = state.get("retrieved_context", {})
    profile  = state.get("profile", {})
    fin      = profile.get("financial_profile", {})
    revision = state.get("revision_count", 0)

    knowledge = "\n".join(ctx.get("knowledge_snippets", [])[:5])
    past_reports = "\n".join(ctx.get("past_report_snippets", [])[:2])

    critic_block = ""
    if feedback and feedback != "APPROVED":
        try:
            fb = json.loads(feedback) if feedback.startswith("{") else {"guidance": feedback}
            issues   = "; ".join(fb.get("issues", []))
            guidance = fb.get("guidance", feedback)
            critic_block = (
                f"\n[CRITIC FEEDBACK — revision {revision}]\n"
                f"Issues: {issues}\n"
                f"Fix: {guidance}\n"
                "You MUST address every issue above in your revised output.\n"
            )
        except Exception:
            critic_block = f"\n[CRITIC FEEDBACK]: {feedback}\n"

    # --- DRAFT ---
    draft_prompt = f"""You are SpendWise, an expert financial advisor for Indian households.

User: {state.get('user_name')} | Persona: {state.get('person_type')}

Financial Metrics:
  Monthly Income:        ₹{metrics.get('monthly_income', 0):,.0f}
  Monthly Surplus:       ₹{metrics.get('monthly_surplus', 0):,.0f}
  Savings Rate:          {metrics.get('savings_rate_pct', 0):.1f}%
  DTI Ratio:             {metrics.get('dti_ratio_pct', 0):.1f}%
  Recommended SIP:       ₹{metrics.get('recommended_monthly_sip', 0):,.0f}/month
  Emergency Fund Target: ₹{metrics.get('emergency_fund_target', 0):,.0f}

Knowledge Base Context:
{knowledge[:2000]}

Past Report Context:
{past_reports[:500]}

Market Insights:
{market[:600]}
{critic_block}
Rules:
- Generate EXACTLY 5 recommendations
- Each must reference the user’s EXACT ₹ numbers (not vague percentages)
- Do NOT suggest spending more than the monthly surplus of ₹{metrics.get('monthly_surplus', 0):,.0f}
- Distribute across at least 3 different categories
- High priority = urgent financial risk or quick win; Low = long-term nice-to-have

Schema for each recommendation:
{_REC_SCHEMA}

Output ONLY a valid JSON array of 5 objects. No markdown, no extra text."""

    try:
        draft_resp = _llm().invoke([HumanMessage(content=draft_prompt)])
        raw = extract_response_text(draft_resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        draft_recs = json.loads(raw)
        if not isinstance(draft_recs, list):
            raise ValueError
    except Exception:
        draft_recs = [{
            "priority": "high", "category": "savings",
            "title": "Build Emergency Fund",
            "action": f"Save ₹{int(metrics.get('emergency_fund_target',0)):,} over 6 months",
            "impact": "6-month financial cushion",
            "deadline": "6 months",
            "rationale": "Emergency fund protects against income disruption."
        }]

    # --- REFLECT: self-critique ---
    # Reflect gets: draft recs + user's original query + explicit check for critic feedback
    critic_addressed = ""
    if feedback and feedback != "APPROVED":
        critic_addressed = f"\nAlso verify: every issue from critic feedback below was fixed:\n{critic_block}"

    reflect_prompt = f"""You generated these financial recommendations for: {state.get('user_name')}
User\'s original question: "{state.get('query', 'general financial planning')}"
Monthly surplus available: ₹{metrics.get('monthly_surplus', 0):,.0f}

Draft recommendations:
{json.dumps(draft_recs, indent=2)}

Self-check EACH recommendation against ALL criteria:
1. Does it quote exact ₹ amounts from the user\'s data?
2. Is the total suggested allocation ≤ monthly surplus of ₹{metrics.get('monthly_surplus', 0):,.0f}?
3. Is the category accurate for the action described?
4. Is the impact quantified (not vague like "save more")?
5. Is the deadline realistic for the action?
6. Does at least one recommendation directly address the user\'s question: "{state.get('query', '')}"?
{critic_addressed}
If ALL criteria pass: output the array unchanged.
If any fail: rewrite only failing items and output the full corrected array of 5 objects.
Output ONLY a valid JSON array of 5 objects. No markdown, no extra text."""

    try:
        reflect_resp = _llm().invoke([HumanMessage(content=reflect_prompt)])
        raw = extract_response_text(reflect_resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        final_recs = json.loads(raw)
        if not isinstance(final_recs, list):
            final_recs = draft_recs
    except Exception:
        final_recs = draft_recs

    # Flat list of action strings for backward compat
    flat_recs = [r.get("action", str(r)) if isinstance(r, dict) else str(r) for r in final_recs]

    return {
        "structured_recs": final_recs,
        "recommendations": flat_recs,
        "messages": [AIMessage(
            content=f"[Reflection Advisor] Draft → Reflect complete. "
                    f"{len(final_recs)} structured recommendations (revision {revision})."
        )],
    }


# ---------------------------------------------------------------------------
# Node 8: Trade-off Agent (Constraint-Aware Reasoning)
# Detects budget-tight recommendations, generates category-specific alternatives
# ---------------------------------------------------------------------------

_TRADEOFF_HINTS = {
    "investment": "SIP: compare equity (12% CAGR) vs debt fund (7%) vs FD (6.5%). Consider ELSS for tax+returns.",
    "debt":       "Debt: avalanche (highest APR first) vs snowball (smallest balance first). Prepayment vs invest delta.",
    "savings":    "Savings: liquid MF (6-7%) vs savings account (3-4%) vs RD (5.5-6.5%).",
    "insurance":  "Insurance: term plan (10-15x income) vs ULIP (avoid mixing). Compare premium/cover ratios.",
    "tax":        "Tax: NPS Tier-I (₹50K extra 80CCD), ELSS (₹1.5L 80C), HRA, 80D medical premium.",
    "emergency":  "Emergency: 3-month minimum in liquid MF; extend to 6 months before increasing SIP.",
}

def trade_off_agent(state):
    metrics  = state.get("financial_metrics", {})
    recs     = state.get("structured_recs", []) or state.get("recommendations", [])
    surplus  = float(metrics.get("monthly_surplus", 0))

    # ── Code-level constraint pre-filter ─────────────────────────────────
    # Only generate trade-offs for recs where the action has a cost, or where
    # the category is investment/debt (always worth showing alternatives),
    # or where the total cost of all recs would exceed 80% of surplus.
    HIGH_TRADEOFF_CATS = {"investment", "debt", "savings"}
    constrained_recs = []
    if isinstance(recs, list) and recs and isinstance(recs[0], dict):
        for r in recs:
            cat = r.get("category", "").lower()
            # Always show trade-off for investment/debt/savings (multiple options exist)
            if cat in HIGH_TRADEOFF_CATS:
                constrained_recs.append(r)
            # Also include any rec that is high priority (high risk = worth showing alternative)
            elif r.get("priority", "").lower() == "high":
                constrained_recs.append(r)
    else:
        constrained_recs = recs  # flat list fallback

    if not constrained_recs:
        return {
            "tradeoff_analysis": [],
            "messages": [AIMessage(content="[Trade-off Agent] No constrained recs — skipping trade-off analysis.")],
        }

    # Build category-specific hints for constrained recs only
    if isinstance(constrained_recs, list) and constrained_recs and isinstance(constrained_recs[0], dict):
        cats = {r.get("category", "general") for r in constrained_recs}
        categories_present = ", ".join(cats)
        hints = "\n".join(
            f"[{cat}] {_TRADEOFF_HINTS.get(cat, 'Consider cost-benefit and timeline alternatives.')}"
            for cat in cats if cat in _TRADEOFF_HINTS
        )
    else:
        cats = set()
        categories_present = "general"
        hints = "\n".join(_TRADEOFF_HINTS.values())

    prompt = f"""You are a practical financial trade-off analyst for Indian households.

Monthly surplus: ₹{surplus:,.0f}
Active recommendation categories: {categories_present}

Category-specific guidance:
{hints}

Recommendations needing trade-off analysis (pre-filtered to investment/debt/savings/high-priority only):
{json.dumps(constrained_recs, indent=2)[:1500]}

For EACH recommendation where there is a meaningful strategic alternative, generate a trade-off entry.
Each entry MUST be a JSON object:
{{
  "for_recommendation": "<title of the original recommendation>",
  "strategy_a": {{
    "name": "<option name>",
    "description": "<specific action with ₹ amounts>",
    "monthly_cost": <number>,
    "benefit": "<quantified benefit>",
    "risk": "<key risk>"
  }},
  "strategy_b": {{
    "name": "<option name>",
    "description": "<specific action with ₹ amounts>",
    "monthly_cost": <number>,
    "benefit": "<quantified benefit>",
    "risk": "<key risk>"
  }},
  "recommended": "a" | "b",
  "reason": "<1 sentence why>"
}}

Output ONLY a valid JSON array of trade-off objects. No markdown, no extra text."""

    try:
        resp = _llm().invoke([HumanMessage(content=prompt)])
        raw = extract_response_text(resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tradeoffs = json.loads(raw)
        if not isinstance(tradeoffs, list):
            raise ValueError
    except Exception:
        tradeoffs = []

    return {
        "tradeoff_analysis": tradeoffs,
        "messages": [AIMessage(content=f"[Trade-off Agent] {len(tradeoffs)} trade-off analyses generated.")],
    }


# ---------------------------------------------------------------------------
# Node 9: Critic Agent (Critic Pattern)
# Validates structured recommendations against hard financial constraints
# ---------------------------------------------------------------------------
def critic_agent(state):
    recs     = state.get("structured_recs", []) or state.get("recommendations", [])
    tradeoffs = state.get("tradeoff_analysis", [])
    metrics  = state.get("financial_metrics", {})
    revision_count = state.get("revision_count", 0)

    if revision_count >= 2:
        return {"critic_feedback": "APPROVED", "revision_count": revision_count}

    surplus = float(metrics.get("monthly_surplus", 0))
    dti     = float(metrics.get("dti_ratio_pct", 0))
    savings = float(metrics.get("savings_rate_pct", 0))

    prompt = f"""You are a strict independent financial plan reviewer.

Financial Reality:
  Monthly surplus:  ₹{surplus:,.0f}
  Savings rate:     {savings:.1f}%
  DTI ratio:        {dti:.1f}%

Recommendations under review:
{json.dumps(recs, indent=2)}

Check EVERY recommendation for ALL of these failure modes:
  A) Does any single recommendation require more than the monthly surplus?
  B) Does any recommendation lack specific ₹ amounts (vague language only)?
  C) Does any recommendation contradict another?
  D) Is the priority label wrong (e.g. low-priority item given high label)?
  E) Is any deadline unrealistically short for the required action?
  F) Are any critical categories missing given DTI={dti:.0f}% and savings={savings:.0f}%?

If ALL recommendations pass ALL checks: respond with exactly: APPROVED

If issues found: respond with a JSON object:
{{"issues": ["<specific issue 1>", ...], "guidance": "<concise fix instructions>"}}

No other text."""

    try:
        feedback = _llm().invoke([HumanMessage(content=prompt)])
        feedback = extract_response_text(feedback.content).strip()
    except Exception:
        feedback = "APPROVED"

    # Normalise: if LLM added 'APPROVED' inside JSON, extract it
    if "APPROVED" in feedback and not feedback.startswith("{"):
        feedback = "APPROVED"

    return {
        "critic_feedback": feedback,
        "revision_count": revision_count + 1,
        "messages": [AIMessage(content=f"[Critic] Revision {revision_count+1}: {feedback[:80]}...")],
    }

def critique_router(state: FinancialPlanningState) -> str:

    feedback = state.get("critic_feedback", "")
    revision_count = state.get("revision_count", 0)

    # Approved -> move to report
    if feedback == "APPROVED":
        return "report_agent"

    # Max 2 revisions -> force continue
    if revision_count >= 2:
        return "report_agent"

    return "recommendation_agent"

# ---------------------------------------------------------------------------
# Node 10: Report Agent
# Assembles report_data dict; pdf_report_tool does the actual rendering
# ---------------------------------------------------------------------------
def report_agent(state):
    metrics   = state.get("financial_metrics", {})
    s_recs    = state.get("structured_recs", []) or state.get("recommendations", [])
    tradeoffs = state.get("tradeoff_analysis", [])
    market    = state.get("market_context", "")
    ctx       = state.get("retrieved_context", {})

    # Build executive summary with LLM using all context
    summary_prompt = f"""You are SpendWise, an expert financial advisor. Write a concise 3-paragraph
executive summary for {state.get('user_name')}'s financial report.

Paragraph 1 — Current financial health (use exact ₹ numbers from metrics).
Paragraph 2 — Top 2 risks and opportunities identified.
Paragraph 3 — Overall outlook and what to prioritise first.

Metrics: {json.dumps(metrics)}
Top recommendations: {json.dumps(s_recs[:3] if isinstance(s_recs, list) else [], indent=2)}
Market context: {market[:400]}

Write in professional but plain English. No bullet points. No headers."""

    try:
        summary_resp = _llm().invoke([HumanMessage(content=summary_prompt)])
        summary = extract_response_text(summary_resp.content)
    except Exception:
        summary = (
            f"{state.get('user_name')}'s financial analysis is complete. "
            f"Monthly surplus: ₹{metrics.get('monthly_surplus',0):,.0f}. "
            f"Savings rate: {metrics.get('savings_rate_pct',0):.1f}%."
        )

    report_data = {
        "user_id":        state.get("user_id"),
        "user_name":      state.get("user_name"),
        "persona":        state.get("person_type"),
        "summary":        summary,
        "metrics":        metrics,
        "structured_recs": s_recs,
        "recommendations": s_recs,   # tools.py reads this key
        "tradeoffs":      tradeoffs,
        "market_insights": market,
        "knowledge_context": "\n".join(ctx.get("knowledge_snippets", [])[:3]),
    }

    pdf_path = pdf_report_tool.invoke({"report_data": json.dumps(report_data)})

    return {
        "pdf_path": pdf_path,
        "response_text": summary,
    }

# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------
def build_graph() -> StateGraph:
    graph = StateGraph(FinancialPlanningState)

    graph.add_node("intake_agent", intake_agent)
    graph.add_node("intent_router", intent_router)
    graph.add_node("conversational_reply_agent", conversational_reply_agent)
    graph.add_node("rag_react_agent", rag_react_agent)
    graph.add_node("market_react_agent", market_react_agent)
    graph.add_node("calculator_agent", calculator_agent)
    graph.add_node("recommendation_agent", recommendation_agent)
    graph.add_node("trade_off_agent", trade_off_agent)
    graph.add_node("critic_agent", critic_agent)
    graph.add_node("report_agent", report_agent)

    # Entry point & intent routing
    graph.set_entry_point("intake_agent")
    graph.add_edge("intake_agent", "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        route_decision,
        {
            "conversational_reply_agent": "conversational_reply_agent",
            "rag_react_agent": "rag_react_agent",
        }
    )

    graph.add_edge("conversational_reply_agent", END)

    # Financial Planning Pipeline
    graph.add_edge("rag_react_agent", "market_react_agent")
    graph.add_edge("market_react_agent", "calculator_agent")
    graph.add_edge("calculator_agent", "recommendation_agent")
    graph.add_edge("recommendation_agent", "trade_off_agent")
    graph.add_edge("trade_off_agent", "critic_agent")

    graph.add_conditional_edges(
        "critic_agent",
        critique_router,
        {
            "report_agent": "report_agent",
            "recommendation_agent": "recommendation_agent",
        }
    )

    graph.add_edge("report_agent", END)

    return graph.compile()


# Global compiled graph
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def run_planning_pipeline(
    user_id: str,
    user_name: str,
    person_type: str,
    monthly_income: float,
    house_emi: float,
    essential_expenses: float = 0.0,
    non_essential_expenses: float = 0.0,
    current_savings: float = 0.0,
    chat_query: str = "",
    profile_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    user_data = {
        "monthly_income":        monthly_income,
        "house_emi":             house_emi,
        "person_type":           person_type,
        "essential_expenses":    essential_expenses,
        "non_essential_expenses": non_essential_expenses,
        "current_savings":       current_savings,
    }

    initial_state: FinancialPlanningState = {
        "messages": [HumanMessage(content=chat_query)],
        "session_id": f"session_{user_id}",
        "user_id": str(user_id),
        "user_name": user_name,
        "person_type": person_type,
        "user_data_json": json.dumps(user_data),
        "profile": profile_dict or {},
        "query": chat_query,
        "intent": "financial_analysis",
        "retrieved_context": {},
        "market_context": "",
        "financial_metrics": {},
        "structured_recs": [],
        "recommendations": [],
        "tradeoff_analysis": [],
        "critic_feedback": "",
        "revision_count": 0,
        "pdf_path": "",
        "response_text": "",
    }

    graph = get_graph()
    final_state = graph.invoke(initial_state)
    return final_state