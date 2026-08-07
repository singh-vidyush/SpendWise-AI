You are a Senior AI Architect, LangGraph Engineer, and Python Backend Developer.


TASK:

Perform a complete architecture review and refactoring of the entire codebase.


IMPORTANT:

Do NOT make assumptions based only on file names.


FIRST PHASE: CODEBASE ANALYSIS


1. Traverse every file, folder, module, and dependency in the repository.

2. Read and understand:

   - flow.md

   - README.md

   - architecture diagrams

   - LangGraph graph definitions

   - agent files

   - node files

   - vector_store.py

   - frontend code

   - backend APIs

   - state definitions

   - schemas

   - prompts

   - storage utilities

   - report generation logic

3. Use flow.md as the source of truth to understand intended workflow.

4. Compare:

   - Current implementation

   - Intended architecture in flow.md

5. Generate a gap analysis showing:

   - Missing agents

   - Missing nodes

   - Broken data flow

   - Unused code

   - Dead code

   - Incorrect LangGraph connections

   - Missing state propagation

   - Storage inconsistencies


--------------------------------------------------


SECOND PHASE: DATA FLOW ANALYSIS


Analyze the complete flow of user data.


Current issue:


Frontend →

Backend →

Processing


User profile data is currently bypassing vector_store.py.


Required architecture:


Frontend

  →

Backend API

  →

Intake Agent

  →

vector_store.py

  →

ChromaDB

  →

LangGraph State

  →

Other Agents


I want all user profile data to pass through vector_store.py before any planning, retrieval, or recommendation logic executes.


Verify that no components bypass vector_store.py.


--------------------------------------------------


THIRD PHASE: USER PROFILE STORAGE REFACTOR


The frontend sends user information as JSON.


Determine the exact JSON structure being received from frontend.


Example:


{

  "user_id": "...",

  "name": "...",

  "age": 30,

  "location": "...",

  "income": {...},

  "expenses": {...},

  "liabilities": {...},

  "goals": [...],

  "risk_profile": "...",

  "timestamp": "..."

}


Do NOT assume this structure.

Extract the real structure from frontend code.


Update vector_store.py so that it:


1. Accepts frontend JSON directly.

2. Validates schema.

3. Handles missing fields safely.

4. Generates embeddings.

5. Creates metadata correctly.

6. Stores profile in ChromaDB.

7. Stores financial history separately.

8. Supports profile updates.

9. Supports versioning.

10. Supports retrieval by user_id.

11. Supports retrieval by session_id.

12. Supports report history retrieval.


Create proper document chunking strategy.


Create proper collection strategy:


users_profile

financial_knowledge

expense_history

market_context

report_history


Ensure retrieval logic works across these collections.


--------------------------------------------------


FOURTH PHASE: LANGGRAPH REVIEW


Review complete graph structure.


Verify:


- State definitions

- Node transitions

- Conditional edges

- Router decisions

- Memory integration

- Checkpointing

- Error handling


Update graph so that state always contains:


UserProfile

RetrievedKnowledge

MarketData

FinancialMetrics

Recommendations

ValidationFeedback

FinalReport


Ensure no state loss occurs between nodes.


--------------------------------------------------


FIFTH PHASE: ADD MISSING AGENTS


Compare implementation against flow.md.


Implement missing agents.


1. Intake Agent


Responsibilities:

- Receive frontend JSON

- Validate user profile

- Normalize data

- Store via vector_store.py

- Populate graph state


Output:

Structured UserProfile


--------------------------------------------------


2. Conversational Reply Agent


Responsibilities:

- Handle general user questions

- Handle follow-up questions

- Use chat history

- Use profile context

- Use previous report context


Output:

Context-aware response


--------------------------------------------------


3. Intent Router


Responsibilities:

- Classify requests into:


A. Conversational

B. Financial Analysis

C. Report Generation

D. Follow-up


Return route decisions.


--------------------------------------------------


4. RAG Agent


Responsibilities:

- Query ChromaDB

- Retrieve user history

- Retrieve financial knowledge

- Remove duplicates

- Rank relevance


Output:

Retrieved Context Package


--------------------------------------------------


5. Market Research Agent


Responsibilities:

- Retrieve latest financial information

- Retrieve market conditions

- Retrieve inflation, rate, tax, investment context


Output:

Market Context


--------------------------------------------------


6. Calculator Agent


Responsibilities:

- Surplus calculation

- Savings rate

- Debt-to-income ratio

- Emergency fund estimation

- EMI burden analysis

- Tax estimation

- Net worth analysis


Output:

FinancialMetrics


--------------------------------------------------


7. Recommendation Agent


Responsibilities:

- Financial insights

- Budget recommendations

- Spending optimizations

- Debt reduction suggestions

- Savings improvements

- Investment allocation suggestions


Output:

Recommendations


--------------------------------------------------


8. Trade-off Agent


Responsibilities:

- Generate alternatives

- Compare benefits

- Compare drawbacks

- Suggest optimal strategy


Output:

TradeoffAnalysis


--------------------------------------------------


9. Critic Agent


Responsibilities:

- Validate calculations

- Validate assumptions

- Detect contradictions

- Verify recommendation quality


Allow maximum two refinement cycles.


Output:

ApprovalStatus


--------------------------------------------------


10. Report Agent


Responsibilities:

- Prepare dashboard data

- Prepare report JSON

- Prepare PDF-ready structure


Output:

FinalReport


--------------------------------------------------


SIXTH PHASE: STATE MANAGEMENT


Create or improve:


LangGraph State Schema


Include:


class FinancialPlanningState:

    session_id

    user_id

    profile

    query

    intent

    retrieved_context

    market_context

    financial_metrics

    recommendations

    tradeoff_analysis

    validation_feedback

    final_report

    chat_history


Verify every node reads from and writes to state correctly.


--------------------------------------------------


SEVENTH PHASE: MEMORY & HISTORY


Implement:


Short-Term Memory

- Current session conversation


Long-Term Memory

- User profile

- Previous reports

- Historical recommendations

- Financial history


Store embeddings in ChromaDB.


Enable retrieval across sessions.


--------------------------------------------------


EIGHTH PHASE: ERROR HANDLING


Add protection for:


- Invalid JSON

- Empty profile

- Missing income

- Missing expenses

- ChromaDB failures

- Embedding failures

- Retrieval failures

- LLM failures

- Report generation failures


Ensure graceful degradation.


--------------------------------------------------


NINTH PHASE: PERFORMANCE


Optimize:


- Duplicate retrievals

- Redundant embeddings

- Unused vector queries

- Excessive LLM calls

- State bloat


Add caching where appropriate.


--------------------------------------------------


TENTH PHASE: DELIVERABLES


Provide:


1. Architecture Review

2. Gap Analysis

3. Data Flow Diagram

4. File-by-File Change List

5. Updated LangGraph Diagram

6. Updated Agent Structure

7. Updated Node Structure

8. Updated vector_store.py

9. Updated State Models

10. Updated Routing Logic

11. Updated ChromaDB Schema

12. Refactored Code


For every modified file provide:


- Why it was changed

- Before behavior

- After behavior

- Complete updated code


Do not stop after analysis.

Perform the full implementation and provide production-ready code changes.
 