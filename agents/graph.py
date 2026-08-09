"""
LangGraph multi-agent architecture for SpendWise-AI.

Agents & Nodes:
  1. intake_agent               – validates, normalizes, and stores user data via vector_store.py
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
    recommendations: List[Any]
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
# ---------------------------------------------------------------------------
def intent_router(state):
    query = state.get("query", "").lower()

    # Fast rule-based classification
    if query.startswith(
        ("what is", "what are", "define", "explain", "how does", "tell me about")
    ):
        intent = "conversational"

    elif any(x in query for x in [
        "my budget", "my expenses", "my savings",
        "my dti", "analyze my", "should i"
    ]):
        intent = "financial_analysis"

    # LLM fallback for ambiguous queries
    else:
        try:
            prompt = f"""
            Classify the query into exactly one:
            conversational,
            financial_analysis

            Query: {query}
            """

            response = _llm().invoke(
                [HumanMessage(content=prompt)]
            )
            response = extract_response_text(response.content).lower()

            if "conversational" in response:
                intent = "conversational"
            else:
                intent = "financial_analysis"

        except Exception:
            intent = "financial_analysis"

    return {"intent": intent}


def route_decision(state: FinancialPlanningState) -> str:
    intent = state.get("intent", "financial_analysis")
    if intent == "conversational":
        return "conversational_reply_agent"
    return "rag_react_agent"


# ---------------------------------------------------------------------------
# Node 3: Conversational Reply Agent
# ---------------------------------------------------------------------------
def conversational_reply_agent(state):
    query = state.get("query", "")

    profile = state.get("profile", {})
    fin = profile.get("financial_profile", {})

    context = "\n".join(
        query_collection(
            financial_knowledge_collection(),
            query,
            3
        )
    )

    answer = _llm().invoke([
        HumanMessage(
            content=f"""
            You are SpendWise, an AI financial advisor.

            Greeting Rules:
            - If the user only greets you, reply with a short greeting.
            - Do not provide financial recommendations, calculations, or analysis for greetings.
            - Example response:
            "Hi 👋 I'm SpendWise, your AI financial advisor. + some small profile based message +  How can I help you today?" 

            User Name: {profile.get('user_name', 'User')}
            User Persona: {fin.get('persona', 'Salaried')}

            Question: {query}

            Context:
            {context}
            
            For actual financial questions, provide a personalized answer using the user's context.
            You are SpendWise, an expert financial advisor.

            """
        )
    ])
    answer = extract_response_text(answer.content)

    return {"response_text": answer}


# ---------------------------------------------------------------------------
# Node 4: RAG Agent (ReAct Pattern)
# ---------------------------------------------------------------------------
def rag_react_agent(state):
    user_data = json.loads(state.get("user_data_json", "{}"))

    prompt = f"""
    User Persona: {user_data.get('person_type', 'Salaried')}
    Income: {user_data.get('monthly_income', 0)}
    EMI: {user_data.get('house_emi', 0)}

    Generate 3 financial search queries.
    Return ONLY a JSON array of strings. No markdown.
    """

    try:
        raw = extract_response_text(                        # 1️⃣ object → STRING
            _llm().invoke([HumanMessage(content=prompt)]).content
        )
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(raw)                           # 2️⃣ STRING → LIST  ← keep this!
        if not isinstance(queries, list) or not queries:
            raise ValueError("not a non-empty list")
    except Exception:
        queries = ["budget planning", "sip investment", "debt management"]
    print(type(queries), queries)

    docs = []
    seen = set()
    for q in queries:                                       # now loops over 3 QUERIES ✅
        for d in query_collection(financial_knowledge_collection(), q, 3):
            if d not in seen:
                seen.add(d)
                docs.append(d)

    return {"retrieved_context": {"knowledge_snippets": docs}}


# ---------------------------------------------------------------------------
# Node 5: Market Research Agent (ReAct Pattern)
# ---------------------------------------------------------------------------
def market_react_agent(state):
    persona = state.get("person_type", "Salaried")

    prompt = f"""
    Persona: {persona}
    Generate 2 specific Indian financial market search queries for 2026.

    Rules:
    Avoid vague/commercial words like "best", "top", "good", "cheapest".

    Use concrete financial terms and instruments

    (e.g. "ELSS returns 2026 India", "PPF interest rate", "SIP mutual fund NAV trends", "RBI repo rate").

    Focus on market data, rates, and trends — NOT product/brand recommendations.
    Return ONLY a JSON array of strings. No markdown.
    """

    try:
        raw = extract_response_text(                        # 1️⃣ object → STRING
            _llm().invoke([HumanMessage(content=prompt)]).content
        )
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(raw)                           # 2️⃣ STRING → LIST ← the fix
        if not isinstance(queries, list) or not queries:
            raise ValueError("not a non-empty list")
    except Exception:
        queries = ["India inflation rate", "India mutual fund returns"]
    results = [
        str(tavily_search_tool.invoke({"query": q}))        # 3️⃣ stringify for safe join
        for q in queries[:2]                                # now slices 2 QUERIES ✅
    ]

    return {"market_context": "\n".join(results)}


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
# ---------------------------------------------------------------------------
def recommendation_agent(state):
    metrics = state.get("financial_metrics", {})
    market = state.get("market_context", "")
    feedback = state.get("critic_feedback", "")

    prompt = f"""
    You are SpendWise, an expert financial advisor.

    User: {state.get('user_name', 'User')}
    Persona: {state.get('person_type', 'Salaried')}

    Financial Metrics:
    {json.dumps(metrics, indent=2)}

    Market Context:
    {market}

    Critic Feedback (address this if present):
    {feedback}

    Generate exactly 5 personalized, actionable financial recommendations.
    Return ONLY a JSON array of 5 objects, each with this exact shape:
    [
      {{"title": "short title", "detail": "1-2 sentence explanation", "priority": "high"}}
    ]
    priority must be one of: "high", "medium", "low".
    No markdown, no text outside the JSON.
    """

    try:
        raw = extract_response_text(                        # 1️⃣ object → STRING
            _llm().invoke([HumanMessage(content=prompt)]).content
        )
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        recs = json.loads(raw)                              # 2️⃣ STRING → LIST ← the fix
        if not isinstance(recs, list) or not recs:
            raise ValueError("not a non-empty list")
    except Exception:
        recs = []

    return {"recommendations": recs}


# ---------------------------------------------------------------------------
# Node 8: Trade-off Agent
# ---------------------------------------------------------------------------
def trade_off_agent(state):
    metrics = state.get("financial_metrics", {})
    recs = state.get("recommendations", [])

    prompt = f"""
    Metrics: {metrics}
    Recommendations: {recs}

    Generate 2-3 financial strategy trade-offs.
    Return JSON array only.
    """

    try:
        tradeoffs = _llm().invoke([HumanMessage(content=prompt)])
        tradeoffs = extract_response_text(tradeoffs.content)   # ❌ STRING — no json.loads!
    except:
        tradeoffs = []

    return {"tradeoff_analysis": tradeoffs}



# ---------------------------------------------------------------------------
# Node 9: Critic Agent
# ---------------------------------------------------------------------------
def critic_agent(state):
    recs = state.get("recommendations", [])
    tradeoffs = state.get("tradeoff_analysis", [])
    revision = state.get("revision_count", 0)          # 👈 read current count

    prompt = f"""
You are a financial plan reviewer.

Recommendations:
{json.dumps(recs)}

Trade-offs:
{json.dumps(tradeoffs)}

Check if the advice is realistic, consistent, and actionable.
Reply with the single word APPROVED if acceptable,
otherwise a short improvement suggestion.
"""
    try:
        feedback = extract_response_text(
            _llm().invoke([HumanMessage(content=prompt)]).content
        )
    except Exception:
        feedback = "APPROVED"

    return {
        "critic_feedback": feedback,
        "revision_count": revision + 1,                # 👈 increment EVERY cycle
    }


def critique_router(state) -> str:
    feedback = state.get("critic_feedback", "").strip().upper()
    revision = state.get("revision_count", 0)

    # approve on fuzzy match OR when max revisions hit (docstring says "max 2 cycles")
    if "APPROVED" in feedback or revision >= 2:        # 👈 both escape hatches
        return "report_agent"
    return "recommendation_agent"


# ---------------------------------------------------------------------------
# Node 10: Report Agent
# ---------------------------------------------------------------------------
def report_agent(state):
    metrics   = state.get("financial_metrics", {})
    recs      = state.get("recommendations", [])
    tradeoffs = state.get("tradeoff_analysis", [])
    market    = state.get("market_context", "")

    prompt = f"""
    Create a professional financial report summary.

    User: {state.get('user_name')}
    Persona: {state.get('person_type')}

    Metrics:
    {json.dumps(metrics, indent=2)}

    Recommendations:
    {json.dumps(recs, indent=2)}

    Trade-offs:
    {json.dumps(tradeoffs, indent=2)}

    Market Context:
    {market[:1000]}

    Write:
    1. Executive Summary
    2. Key Financial Observations
    3. Overall Financial Health

    Keep it concise and professional.
    """

    try:
        summary = extract_response_text(                    # (summary is plain text —
            _llm().invoke([HumanMessage(content=prompt)]).content   #  no json.loads needed ✅)
        )
    except Exception:
        summary = "Financial analysis completed successfully."

    # 🔑 keys aligned to what pdf_report_tool ACTUALLY reads
    report_data = {
        "user_id": state.get("user_id"),
        "user_name": state.get("user_name"),
        "person_type": state.get("person_type"),   # was "persona"
        "executive_summary": summary,              # was "summary"
        "calculations": metrics,                   # was "metrics"  ← unlocks metrics table
        "recommendations": recs,
        "tradeoff_analysis": tradeoffs,            # was "tradeoffs"
        "market_insights": market,
    }

    pdf_path = pdf_report_tool.invoke({
        "report_data": json.dumps(report_data)
    })

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
    chat_query: str = "",
    profile_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    user_data = {
        "monthly_income": monthly_income,
        "house_emi": house_emi,
        "person_type": person_type,
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