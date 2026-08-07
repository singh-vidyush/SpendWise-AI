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
import logging
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
    past_reports_collection,
)

logger = logging.getLogger(__name__)


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
    intent: str  # conversational | financial_analysis | report_generation | follow_up

    retrieved_context: Dict[str, Any]
    market_context: str

    financial_metrics: Dict[str, Any]
    recommendations: List[Any]
    tradeoff_analysis: List[Any]

    critic_feedback: str
    revision_count: int

    pdf_path: str
    response_text: str
    chat_history: List[BaseMessage]


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
def intake_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    """
    Receives user profile, normalizes data, and stores via vector_store.py before planning.
    """
    user_id = state.get("user_id", "default_user")
    session_id = state.get("session_id", "default_session")

    existing_profile = state.get("profile") or {}
    if not existing_profile:
        try:
            fetched = get_user_profile(user_id)
            if fetched:
                existing_profile = fetched
        except Exception as e:
            logger.error(f"Error reading profile in intake_agent: {e}")

    # Build raw profile dict from state if not already filled
    if not existing_profile.get("financial_profile"):
        user_data = json.loads(state.get("user_data_json", "{}")) if state.get("user_data_json") else {}
        existing_profile = {
            "user_name": state.get("user_name", "User"),
            "user_email": "",
            "financial_profile": {
                "persona": state.get("person_type", "Salaried"),
                "monthly_income": user_data.get("monthly_income", 0.0),
                "essential_expenses": user_data.get("essential_expenses", 0.0),
                "non_essential_expenses": user_data.get("non_essential_expenses", 0.0),
                "current_savings": user_data.get("current_savings", 0.0),
                "debt_details": {
                    "has_debt": bool(user_data.get("house_emi", 0) > 0 or user_data.get("other_liabilities")),
                    "debt_type": "Loan/EMI",
                    "total_outstanding_debt": 0.0,
                    "monthly_emi": float(user_data.get("house_emi", 0.0)),
                },
                "investments": [],
                "monthly_saving_investment": 0.0,
            }
        }

    # Pass through vector_store.py
    normalized_json = upsert_user_profile(user_id, existing_profile, session_id=session_id)
    normalized_dict = json.loads(normalized_json)

    fin = normalized_dict.get("financial_profile", {})
    user_data_json = json.dumps({
        "monthly_income": fin.get("monthly_income", 0.0),
        "essential_expenses": fin.get("essential_expenses", 0.0),
        "non_essential_expenses": fin.get("non_essential_expenses", 0.0),
        "current_savings": fin.get("current_savings", 0.0),
        "house_emi": fin.get("debt_details", {}).get("monthly_emi", 0.0),
        "insurance_premium": 0.0,
        "health_expenses": 0.0,
        "other_liabilities": [],
        "person_type": fin.get("persona", "Salaried"),
        "debt_details": fin.get("debt_details", {}),
    })

    return {
        "profile": normalized_dict,
        "user_data_json": user_data_json,
        "messages": [AIMessage(content="[Intake Agent] User profile normalized and persisted in vector store.")],
    }


# ---------------------------------------------------------------------------
# Node 2: Intent Router
# ---------------------------------------------------------------------------
def intent_router(state: FinancialPlanningState) -> Dict[str, Any]:
    """
    Classifies user request into:
    A. conversational
    B. financial_analysis
    C. report_generation
    D. follow_up
    """
    query = state.get("query", "").strip()
    query_lower = query.lower()

    # Rule-based heuristics for quick and accurate intent classification
    conversational_triggers = [
        "what is", "what are", "define", "explain", "how does", "what does",
        "hi", "hello", "hey", "tell me about", "difference between", "meaning of",
        "concept of", "is it good to", "can you explain"
    ]

    report_triggers = [
        "generate report", "download pdf", "create report", "make pdf", "full report", "pdf report"
    ]

    analysis_triggers = [
        "analyze my", "my budget", "my expenses", "where am i overspending",
        "how much should i save", "should i clear debt", "my savings rate", "my dti"
    ]

    if any(trigger in query_lower for trigger in report_triggers):
        intent = "report_generation"
    elif any(query_lower.startswith(trigger) or f" {trigger} " in f" {query_lower} " for trigger in conversational_triggers) and not any(trigger in query_lower for trigger in analysis_triggers):
        intent = "conversational"
    else:
        llm = _llm()
        prompt = f"""
You are a financial intent classifier.
User query: "{query}"

Classify into exactly ONE category:
- conversational: General questions, educational questions, definitions ("What is SIP?", "How does mutual fund work?").
- financial_analysis: Requesting personalized analysis of user's income, budget, expenses, debt, or savings.
- report_generation: Explicit request for generating or downloading a report/PDF.
- follow_up: Follow-up question on past plan or calculations.

Return ONLY the category name.
"""
        try:
            res = llm.invoke([HumanMessage(content=prompt)])
            raw_text = extract_response_text(res.content).strip().lower()
            if "conversational" in raw_text:
                intent = "conversational"
            elif "report" in raw_text:
                intent = "report_generation"
            elif "follow" in raw_text:
                intent = "follow_up"
            else:
                intent = "financial_analysis"
        except Exception:
            intent = "financial_analysis"

    return {
        "intent": intent,
        "messages": [AIMessage(content=f"[Intent Router] Intent classified as: {intent}")],
    }


def route_decision(state: FinancialPlanningState) -> str:
    intent = state.get("intent", "financial_analysis")
    if intent == "conversational":
        return "conversational_reply_agent"
    return "rag_react_agent"


# ---------------------------------------------------------------------------
# Node 3: Conversational Reply Agent
# ---------------------------------------------------------------------------
def conversational_reply_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    """
    Handles conversational requests using history and profile context without full pipeline execution.
    """
    llm = _llm()
    query = state.get("query", "")
    profile = state.get("profile", {})
    fin = profile.get("financial_profile", {})

    # RAG knowledge lookup
    knowledge = query_collection(financial_knowledge_collection(), query, n_results=3)
    knowledge_text = "\n".join(knowledge)

    prompt = f"""
You are SpendWise, an empathetic, expert AI Financial Advisor.
User query: "{query}"

User Profile:
- Name: {profile.get('user_name', 'User')}
- Persona: {fin.get('persona', 'Salaried')}
- Monthly Income: ₹{fin.get('monthly_income', 0):,.2f}

Relevant Knowledge:
{knowledge_text[:1500]}

Answer the user's question clearly, warmly, and accurately.
"""
    res = llm.invoke([HumanMessage(content=prompt)])
    answer = extract_response_text(res.content)

    return {
        "response_text": answer,
        "messages": [AIMessage(content=answer)],
    }


# ---------------------------------------------------------------------------
# Node 4: RAG Agent (ReAct Pattern)
# ---------------------------------------------------------------------------
def rag_react_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    llm = _llm()
    user_data = json.loads(state.get("user_data_json", "{}"))
    person_type = user_data.get("person_type", "Salaried")

    think_prompt = f"""
You are a financial knowledge retrieval planner.
User profile: {person_type}, Income: ₹{user_data.get('monthly_income',0):,.0f}, EMIs: ₹{user_data.get('house_emi',0):,.0f}.
Generate 3 financial knowledge search queries for ChromaDB.
Return ONLY JSON array of 3 strings.
"""
    try:
        res = llm.invoke([HumanMessage(content=think_prompt)])
        queries = json.loads(extract_response_text(res.content))
        if not isinstance(queries, list):
            raise ValueError
    except Exception:
        queries = ["budget planning India", "SIP investment tax India", "emergency fund debt management"]

    all_docs = []
    for q in queries[:3]:
        docs = query_collection(financial_knowledge_collection(), q, n_results=3)
        all_docs.extend(docs)

    unique_docs = list(dict.fromkeys(all_docs))
    expenses = query_collection(expense_history_collection(), f"expense history {person_type}", n_results=2)
    past_reports = query_collection(past_reports_collection(), f"report {state.get('user_id')}", n_results=2)

    retrieved = {
        "knowledge_snippets": unique_docs,
        "expense_snippets": expenses,
        "past_reports": past_reports,
    }

    return {
        "retrieved_context": retrieved,
        "messages": [AIMessage(content=f"[RAG Agent] Retrieved {len(unique_docs)} knowledge snippets.")],
    }


# ---------------------------------------------------------------------------
# Node 5: Market Research Agent (ReAct Pattern)
# ---------------------------------------------------------------------------
def market_react_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    llm = _llm()
    person_type = state.get("person_type", "Salaried")

    think_prompt = f"""
You are a financial market research planner.
User persona: {person_type}.
Generate 2 web search queries for current Indian market financial data (inflation, interest rates, mutual fund returns).
Return ONLY JSON array of 2 strings.
"""
    try:
        res = llm.invoke([HumanMessage(content=think_prompt)])
        queries = json.loads(extract_response_text(res.content))
        if not isinstance(queries, list):
            raise ValueError
    except Exception:
        queries = ["India inflation interest rates", "India SIP mutual fund returns"]

    results = []
    for q in queries[:2]:
        out = tavily_search_tool.invoke({"query": q})
        if out and "failed" not in out.lower():
            results.append(f"### {q}\n{out}")

    combined = "\n\n".join(results) if results else "Current market conditions stable. Fixed income 6.5-7.5%, Equity SIP historical 12%."

    return {
        "market_context": combined,
        "messages": [AIMessage(content=f"[Market Agent] Fetched live market data for {len(results)} queries.")],
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
# ---------------------------------------------------------------------------
def recommendation_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    llm = _llm()
    metrics = state.get("financial_metrics", {})
    retrieved = state.get("retrieved_context", {})
    knowledge = "\n".join(retrieved.get("knowledge_snippets", []))
    market = state.get("market_context", "")
    critic_feedback = state.get("critic_feedback", "")
    revision_count = state.get("revision_count", 0)

    prompt = f"""
You are a certified financial advisor.
Generate 5 personalized financial recommendations for:
User: {state.get('user_name', 'Client')} ({state.get('person_type', 'Salaried')})
Financial Metrics:
{json.dumps(metrics, indent=2)}

Knowledge Context:
{knowledge[:1500]}

Market Context:
{market[:800]}

Previous Feedback (if any):
{critic_feedback}

Return ONLY JSON array of 5 recommendation objects:
[
  {{
    "action": "Description of action with specific numbers",
    "expected_impact": "Expected financial result",
    "priority": "High/Medium/Low"
  }}
]
"""
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        recs = json.loads(extract_response_text(res.content))
        if not isinstance(recs, list):
            raise ValueError
    except Exception:
        recs = [
            {"action": f"Allocate ₹{metrics.get('recommended_monthly_sip', 0):,.0f} into diversified equity SIPs.", "expected_impact": "Long-term wealth creation", "priority": "High"},
            {"action": f"Build emergency fund of ₹{metrics.get('emergency_fund_target', 0):,.0f}.", "expected_impact": "Financial safety net", "priority": "High"},
            {"action": f"Maintain monthly expenses within ₹{metrics.get('essential_expenses', 0) + metrics.get('non_essential_expenses', 0):,.0f}.", "expected_impact": "Sustain positive cash flow", "priority": "Medium"}
        ]

    return {
        "recommendations": recs,
        "messages": [AIMessage(content=f"[Recommendation Agent] Generated {len(recs)} recommendations (Revision: {revision_count}).")],
    }


# ---------------------------------------------------------------------------
# Node 8: Trade-off Agent
# ---------------------------------------------------------------------------
def trade_off_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    llm = _llm()
    metrics = state.get("financial_metrics", {})
    recs = state.get("recommendations", [])

    prompt = f"""
Analyze the trade-offs for these financial recommendations:
Metrics: {json.dumps(metrics, indent=2)}
Recommendations: {json.dumps(recs, indent=2)}

Generate 2-3 strategic trade-off comparisons (e.g. Debt Repayment vs SIP Investing, Aggressive Savings vs Lifestyle).
Return ONLY JSON array of objects:
[
  {{
    "strategy": "Strategy Name",
    "benefits": "Key benefits",
    "tradeoffs": "Key trade-offs or drawbacks",
    "priority": "High/Medium/Low"
  }}
]
"""
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        tradeoffs = json.loads(extract_response_text(res.content))
        if not isinstance(tradeoffs, list):
            raise ValueError
    except Exception:
        tradeoffs = [
            {"strategy": "Aggressive Debt Payoff", "benefits": "Reduces interest burden quickly", "tradeoffs": "Delays equity market participation", "priority": "High"},
            {"strategy": "Balanced SIP + Emergency Corpus", "benefits": "Builds liquidity and long-term wealth simultaneously", "tradeoffs": "Slower debt clearance", "priority": "Medium"}
        ]

    return {
        "tradeoff_analysis": tradeoffs,
        "messages": [AIMessage(content=f"[Trade-off Agent] Generated {len(tradeoffs)} trade-off strategies.")],
    }


# ---------------------------------------------------------------------------
# Node 9: Critic Agent
# ---------------------------------------------------------------------------
def critic_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    llm = _llm()
    revision_count = state.get("revision_count", 0)

    if revision_count >= 2:
        return {
            "critic_feedback": "APPROVED",
            "messages": [AIMessage(content="[Critic Agent] Maximum review cycles reached. Approved.")],
        }

    metrics = state.get("financial_metrics", {})
    recs = state.get("recommendations", [])
    tradeoffs = state.get("tradeoff_analysis", [])

    prompt = f"""
You are a strict financial plan critic. Validate these outputs for consistency, feasibility, and correctness:
Metrics: {json.dumps(metrics, indent=2)}
Recommendations: {json.dumps(recs, indent=2)}
Trade-offs: {json.dumps(tradeoffs, indent=2)}

Respond ONLY with "APPROVED" or a JSON object listing issues:
APPROVED
OR
{{"issues": ["issue 1"], "revised_guidance": "guidance"}}
"""
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        text = extract_response_text(res.content).strip()
        if "APPROVED" in text.upper():
            feedback = "APPROVED"
        else:
            feedback = text
            revision_count += 1
    except Exception:
        feedback = "APPROVED"

    return {
        "critic_feedback": feedback,
        "revision_count": revision_count,
        "messages": [AIMessage(content=f"[Critic Agent] Review decision: {feedback[:50]}")],
    }


def critique_router(state: FinancialPlanningState) -> str:
    if state.get("critic_feedback", "") == "APPROVED":
        return "report_agent"
    return "recommendation_agent"


# ---------------------------------------------------------------------------
# Node 10: Report Agent
# ---------------------------------------------------------------------------
def report_agent(state: FinancialPlanningState) -> Dict[str, Any]:
    metrics = state.get("financial_metrics", {})
    recs = state.get("recommendations", [])
    tradeoffs = state.get("tradeoff_analysis", [])
    market = state.get("market_context", "")

    report_payload = {
        "user_id": state.get("user_id", "001"),
        "user_name": state.get("user_name", "User"),
        "person_type": state.get("person_type", "Salaried"),
        "executive_summary": f"Comprehensive financial review for {state.get('user_name')}. Monthly surplus: ₹{metrics.get('monthly_surplus', 0):,.2f}.",
        "calculations": metrics,
        "recommendations": recs,
        "tradeoff_analysis": tradeoffs,
        "market_insights": market,
    }

    pdf_path = pdf_report_tool.invoke({"report_data": json.dumps(report_payload)})

    # Build final response text
    response_parts = [
        f"📊 **Financial Snapshot for {state.get('user_name')}**\n",
        f"• **Monthly Income:** ₹{metrics.get('monthly_income', 0):,.2f}",
        f"• **Monthly Surplus:** ₹{metrics.get('monthly_surplus', 0):,.2f}",
        f"• **Savings Rate:** {metrics.get('savings_rate_pct', 0):.1f}%",
        f"• **Debt-to-Income Ratio:** {metrics.get('dti_ratio_pct', 0):.1f}%\n",
        "💡 **Key Recommendations:**"
    ]
    for i, r in enumerate(recs, 1):
        action = r.get("action", str(r)) if isinstance(r, dict) else str(r)
        response_parts.append(f"{i}. {action}")

    response_parts.append("\n⚖️ **Trade-Off Analysis:**")
    for i, t in enumerate(tradeoffs, 1):
        strat = t.get("strategy", f"Option {i}") if isinstance(t, dict) else str(t)
        benefits = t.get("benefits", "") if isinstance(t, dict) else ""
        response_parts.append(f"• **{strat}**: {benefits}")

    if pdf_path:
        response_parts.append(f"\n📄 **PDF Report Generated:** `{pdf_path}`")

    final_text = "\n".join(response_parts)

    return {
        "pdf_path": pdf_path,
        "response_text": final_text,
        "messages": [AIMessage(content=f"[Report Agent] Generated PDF report at {pdf_path}")],
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
    insurance_premium: float = 0.0,
    health_expenses: float = 0.0,
    other_liabilities: list = None,
    age: float = 30.0,
    chat_query: str = "",
    chat_history: Optional[List[BaseMessage]] = None,
    profile_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    user_data = {
        "monthly_income": monthly_income,
        "house_emi": house_emi,
        "insurance_premium": insurance_premium,
        "health_expenses": health_expenses,
        "other_liabilities": other_liabilities or [],
        "person_type": person_type,
        "age": age,
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
        "chat_history": chat_history or [],
    }

    graph = get_graph()
    final_state = graph.invoke(initial_state)
    return final_state