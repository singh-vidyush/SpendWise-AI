"""
LangGraph ReAct financial planning agent.

Agents and design patterns:
  1. rag_react_agent    – ReAct: reasons about financial knowledge retrieval
  2. market_react_agent – ReAct: reasons about required market information
  3. calculator_agent   – deterministic financial calculations
  4. advisor_agent      – generates personalised recommendations
  5. critic_agent       – reviews recommendations and requests revision
  6. report_agent       – generates PDF financial report
"""

import json
from typing import TypedDict, Annotated, List
import operator

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from config import GEMINI_API_KEY

from agents.tools import (
    calculation_tool,
    tavily_search_tool,
    pdf_report_tool,
)

from db.vector_store import (
    query_collection,
    financial_knowledge_collection,
    expense_history_collection,
)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class FinancialState(TypedDict):

    messages: Annotated[List[BaseMessage], operator.add]

    user_id: str
    user_name: str
    person_type: str

    user_data_json: str

    chat_history: List[BaseMessage]

    knowledge_snippets: List[str]
    expense_snippets: List[str]

    market_insights: str

    calculations: dict

    recommendations: List[str]

    critic_feedback: str

    revision_count: int

    pdf_path: str


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def _llm():

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        api_key=GEMINI_API_KEY,
        temperature=0.3,
    )

def extract_response_text(content):
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
# Node 1: RAG Agent (ReAct Pattern)
#
# Think:
#   Decide what financial knowledge is required
#
# Act:
#   Retrieve relevant documents from ChromaDB
#
# Observe:
#   Return useful knowledge snippets
# ---------------------------------------------------------------------------

def rag_react_agent(state: FinancialState) -> dict:

    llm = _llm()

    user_data = json.loads(
        state["user_data_json"]
    )

    person_type = state.get(
        "person_type",
        "salaried"
    )


    think_prompt = (
        f"You are a financial knowledge retrieval planner.\n"
        f"User type: {person_type}\n"
        f"Monthly income: ₹{user_data.get('monthly_income',0):,.0f}\n"
        f"EMI: ₹{user_data.get('house_emi',0):,.0f}\n"
        f"Insurance: ₹{user_data.get('insurance_premium',0):,.0f}\n"
        f"Health expenses: ₹{user_data.get('health_expenses',0):,.0f}\n\n"
        "Generate exactly 3 financial knowledge search queries.\n"
        "Each query should target a different financial topic.\n"
        "Return ONLY JSON array of strings."
    )


    response = llm.invoke(
        [
            HumanMessage(
                content=think_prompt
            )
        ]
    )


    try:

        queries = json.loads(
            response.content
        )

        if not isinstance(
            queries,
            list
        ):
            raise ValueError


    except Exception:

        queries = [
            "financial planning India",
            "SIP investment basics India",
            "tax planning India",
        ]


    all_docs = []


    for query in queries[:3]:

        docs = query_collection(
            financial_knowledge_collection(),
            query,
            n_results=3
        )

        all_docs.extend(
            docs
        )


    seen = set()

    unique_docs = [
        doc
        for doc in all_docs
        if not (
            doc in seen
            or seen.add(doc)
        )
    ]


    expenses = query_collection(
        expense_history_collection(),
        f"expense history {person_type}",
        n_results=3
    )


    return {

        "knowledge_snippets": unique_docs,

        "expense_snippets": expenses,

        "messages": [

            AIMessage(
                content=(
                    f"[ReAct RAG] Queries: {queries}. "
                    f"Retrieved {len(unique_docs)} documents."
                )
            )

        ],
    }
# ---------------------------------------------------------------------------
# Node 2: Market Agent (ReAct Pattern)
#
# Think:
#   Decide what market information is required
#
# Act:
#   Search Tavily
#
# Observe:
#   Combine market insights
# ---------------------------------------------------------------------------

def market_react_agent(state: FinancialState) -> dict:

    llm = _llm()

    person_type = state.get(
        "person_type",
        "salaried"
    )


    think_prompt = (
        f"You are a financial market research planner.\n"
        f"User type: {person_type}\n\n"
        "Generate exactly 2 web search queries "
        "for current financial market information.\n"
        "Focus on inflation, interest rates, "
        "investment returns and financial news.\n"
        "Return ONLY JSON array."
    )


    response = llm.invoke(
        [
            HumanMessage(
                content=think_prompt
            )
        ]
    )


    try:

        queries = json.loads(
            response.content
        )

        if not isinstance(
            queries,
            list
        ):
            raise ValueError


    except Exception:

        queries = [
            "India inflation and interest rates",
            "India mutual fund SIP returns",
        ]


    results = []


    for query in queries[:2]:

        data = tavily_search_tool.invoke(
            {
                "query": query
            }
        )

        if data and "failed" not in data.lower():

            results.append(
                f"### {query}\n{data}"
            )


    combined = (
        "\n\n".join(results)
        if results
        else "No market information available."
    )


    return {

        "market_insights": combined,

        "messages": [

            AIMessage(
                content=(
                    f"[ReAct Market] Queries: {queries}. "
                    f"Fetched {len(results)} results."
                )
            )

        ],
    }



# ---------------------------------------------------------------------------
# Node 3: Calculator Agent
#
# Performs deterministic financial calculations
# ---------------------------------------------------------------------------

def calculator_agent(state: FinancialState) -> dict:


    result = calculation_tool.invoke(
        {
            "user_data": state["user_data_json"]
        }
    )


    calculations = json.loads(
        result
    )


    return {

        "calculations": calculations,

        "messages": [

            AIMessage(
                content=(
                    "Calculations completed. "
                    f"Monthly surplus: "
                    f"₹{calculations.get('monthly_surplus',0):,.2f}"
                )
            )

        ],
    }



# ---------------------------------------------------------------------------
# Node 4: Advisor Agent (Reflection Pattern)
#
# Draft:
#   Generate recommendations
#
# Reflect:
#   Check recommendations against financial reality
#
# Finalise:
#   Return improved recommendations
# ---------------------------------------------------------------------------

def advisor_agent(state: FinancialState) -> dict:


    llm = _llm()


    calculations = state.get(
        "calculations",
        {}
    )


    knowledge = "\n".join(
        state.get(
            "knowledge_snippets",
            []
        )
    )


    market = state.get(
        "market_insights",
        ""
    )


    user_data = json.loads(
        state["user_data_json"]
    )


    history = state.get(
        "chat_history",
        []
    )[-6:]


    history_text = ""

    for message in history:

        role = (
            "User"
            if isinstance(
                message,
                HumanMessage
            )
            else "Assistant"
        )

        history_text += (
            f"{role}: {message.content}\n"
        )


    critic_feedback = state.get(
        "critic_feedback",
        ""
    )


    revision_count = state.get(
        "revision_count",
        0
    )


    critic_context = ""


    if critic_feedback and critic_feedback != "APPROVED":

        try:

            feedback = json.loads(
                critic_feedback
            )

            issues = "; ".join(
                feedback.get(
                    "issues",
                    []
                )
            )

            guidance = feedback.get(
                "revised_guidance",
                ""
            )


            critic_context = (
                "\nPrevious critic feedback:\n"
                f"Issues: {issues}\n"
                f"Guidance: {guidance}\n"
                "Fix these issues.\n"
            )


        except Exception:

            pass



    prompt = f"""

You are a certified financial planner.

Generate exactly 6 personalised financial recommendations.

User:
Name: {state['user_name']}
Profile: {state['person_type']}


Conversation History:

{history_text or "No previous conversation"}


Financial Calculations:

{json.dumps(calculations, indent=2)}


User Financial Profile:

{json.dumps(user_data, indent=2)}


Financial Knowledge:

{knowledge[:2500]}


Market Insights:

{market[:1000]}


{critic_context}


Rules:

1. Recommendations must be specific to this user.
2. Use actual calculated numbers.
3. Do not provide generic advice.
4. Do not suggest amounts above monthly surplus.
5. Include saving, investment, debt and expense advice.
6. Keep recommendations concise and actionable.


Return ONLY JSON array of 6 strings.

"""


    response = llm.invoke(
        [
            HumanMessage(
                content=prompt
            )
        ]
    )


    try:

        if isinstance(response.content, list):
            draft_recommendations = response.content

        else:
            draft_recommendations = json.loads(
                response.content
            )

        if not isinstance(
            draft_recommendations,
            list
        ):
            raise ValueError


    except Exception:

        content = (
            "\n".join(response.content)
            if isinstance(response.content, list)
            else response.content
        )

        draft_recommendations = [
            line.strip("- ")
            for line in content.split("\n")
            if line.strip()
        ]



    # Reflection step

    reflection_prompt = f"""

Review these financial recommendations.

Financial Situation:

Monthly income:
₹{calculations.get('monthly_income',0):,.0f}

Monthly surplus:
₹{calculations.get('monthly_surplus',0):,.0f}

Savings rate:
{calculations.get('savings_rate_pct',0):.1f}%


Recommendations:

{json.dumps(draft_recommendations, indent=2)}


Check:

1. Are recommendations affordable?
2. Are numbers consistent?
3. Are they personalised?
4. Are they actionable?
5. Are they free from contradictions?


If correct:
Return same JSON array.

If improvements required:
Rewrite recommendations.

Return ONLY JSON array of 6 strings.

"""


    reflection_response = llm.invoke(
        [
            HumanMessage(
                content=reflection_prompt
            )
        ]
    )


    try:

        if isinstance(reflection_response.content, list):
            final_recommendations = reflection_response.content

        else:
            final_recommendations = json.loads(
                reflection_response.content
            )

        if not isinstance(
            final_recommendations,
            list
        ):
            final_recommendations = draft_recommendations


    except Exception:

        final_recommendations = draft_recommendations



    return {

        "recommendations": final_recommendations,

        "messages": [

            AIMessage(
                content=(
                    "[Advisor Agent] "
                    f"Generated {len(final_recommendations)} "
                    f"recommendations. "
                    f"Revision count: {revision_count}"
                )
            )

        ],

    }
# ---------------------------------------------------------------------------
# Node 5: Critic Agent
#
# Reviews recommendations and decides:
#
# APPROVED
# OR
# Request revision from advisor_agent
# ---------------------------------------------------------------------------

def critic_agent(state: FinancialState) -> dict:

    llm = _llm()

    calculations = state.get(
        "calculations",
        {}
    )

    recommendations = state.get(
        "recommendations",
        []
    )

    revision_count = state.get(
        "revision_count",
        0
    )


    # Prevent infinite advisor-critic loop

    if revision_count >= 2:

        return {

            "critic_feedback": "APPROVED",

            "messages": [

                AIMessage(
                    content=
                    "[Critic] Maximum revisions reached. Approved."
                )

            ],

        }



    prompt = f"""

You are a strict financial reviewer.

Review these recommendations.


Financial Information:

Monthly Income:
₹{calculations.get('monthly_income',0):,.0f}

Monthly Surplus:
₹{calculations.get('monthly_surplus',0):,.0f}

Savings Rate:
{calculations.get('savings_rate_pct',0):.1f}%


Recommendations:

{json.dumps(recommendations,indent=2)}


Check:

1. Are recommendations affordable?
2. Are calculations realistic?
3. Are recommendations personalised?
4. Are they actionable?
5. Are there contradictions?


Respond ONLY with:

APPROVED

OR


{{
"issues":[
"problem 1"
],
"revised_guidance":
"what should improve"
}}


"""


    response = llm.invoke(
        [
            HumanMessage(
                content=prompt
            )
        ]
    )


    content = extract_response_text(response.content).strip()



    if content == "APPROVED":

        return {

            "critic_feedback": "APPROVED",

            "messages": [

                AIMessage(
                    content=
                    "[Critic] Recommendations approved."
                )

            ],

        }



    try:

        critique = json.loads(
            content
        )


        return {

            "critic_feedback":
                json.dumps(critique),

            "revision_count":
                revision_count + 1,

            "messages":[

                AIMessage(
                    content=
                    "[Critic] Revision requested."
                )

            ],

        }


    except Exception:


        return {

            "critic_feedback":
                "APPROVED",

            "messages":[

                AIMessage(
                    content=
                    "[Critic] Invalid response. Approved."
                )

            ],

        }



# ---------------------------------------------------------------------------
# Critic Router
# ---------------------------------------------------------------------------

def critique_router(state: FinancialState) -> str:


    if state.get(
        "critic_feedback",
        ""
    ) == "APPROVED":

        return "report_agent"


    return "advisor_agent"



# ---------------------------------------------------------------------------
# Node 6: Report Agent
#
# Generates final PDF report
# ---------------------------------------------------------------------------

def report_agent(state: FinancialState) -> dict:


    report_data = json.dumps({

        "user_name":
            state["user_name"],

        "person_type":
            state["person_type"],

        "calculations":
            state.get(
                "calculations",
                {}
            ),

        "recommendations":
            state.get(
                "recommendations",
                []
            ),

        "market_insights":
            state.get(
                "market_insights",
                ""
            ),

        "knowledge_snippets":
            state.get(
                "knowledge_snippets",
                []
            ),

    })


    pdf_path = pdf_report_tool.invoke(
        {
            "report_data": report_data
        }
    )


    return {

        "pdf_path": pdf_path,

        "messages":[

            AIMessage(
                content=
                f"PDF report generated: {pdf_path}"
            )

        ],

    }



# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:


    graph = StateGraph(
        FinancialState
    )


    graph.add_node(
        "rag_react_agent",
        rag_react_agent
    )


    graph.add_node(
        "market_react_agent",
        market_react_agent
    )


    graph.add_node(
        "calculator_agent",
        calculator_agent
    )


    graph.add_node(
        "advisor_agent",
        advisor_agent
    )


    graph.add_node(
        "critic_agent",
        critic_agent
    )


    graph.add_node(
        "report_agent",
        report_agent
    )



    # Entry point

    graph.set_entry_point(
        "rag_react_agent"
    )



    # Main agent pipeline

    graph.add_edge(
        "rag_react_agent",
        "market_react_agent"
    )


    graph.add_edge(
        "market_react_agent",
        "calculator_agent"
    )


    graph.add_edge(
        "calculator_agent",
        "advisor_agent"
    )


    graph.add_edge(
        "advisor_agent",
        "critic_agent"
    )



    # Critic decision loop

    graph.add_conditional_edges(

        "critic_agent",

        critique_router,

        {

            "report_agent":
                "report_agent",

            "advisor_agent":
                "advisor_agent",

        },

    )



    graph.add_edge(
        "report_agent",
        END
    )



    return graph.compile()
# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def run_planning_pipeline(
    user_id: str,
    user_name: str,
    person_type: str,
    monthly_income: float,
    house_emi: float,
    insurance_premium: float,
    health_expenses: float,
    other_liabilities: list,
    age: float,
    chat_query: str,
    chat_history: List[BaseMessage] | None = None,
    prior_calculations: dict | None = None,
    prior_recommendations: List[str] | None = None,
) -> dict:
    """
    Entry point called from Streamlit.

    LangGraph pipeline:

    RAG ReAct Agent
            |
    Market ReAct Agent
            |
    Calculator Agent
            |
    Advisor Agent
            |
    Critic Agent
            |
    Report Agent

    Goal planning removed.
    Router removed.
    """

    user_data = {

        "monthly_income": monthly_income,

        "house_emi": house_emi,

        "insurance_premium": insurance_premium,

        "health_expenses": health_expenses,

        "other_liabilities": other_liabilities,

        "person_type": person_type,

        "age": age,

    }



    initial_state: FinancialState = {

        "messages": [

            HumanMessage(
                content=chat_query
            )

        ],


        "user_id":
            user_id,


        "user_name":
            user_name,


        "person_type":
            person_type,


        "user_data_json":
            json.dumps(user_data),



        "chat_history":
            chat_history or [],



        "knowledge_snippets":
            [],


        "expense_snippets":
            [],



        "market_insights":
            "",



        "calculations":
            prior_calculations or {},



        "recommendations":
            prior_recommendations or [],



        "critic_feedback":
            "",



        "revision_count":
            0,



        "pdf_path":
            "",

    }



    graph = build_graph()



    final_state = graph.invoke(
        initial_state
    )


    return final_state