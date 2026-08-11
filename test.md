# Comprehensive End-to-End Test Report: SpendWise-AI

**Project:** SpendWise-AI (Personal Financial Planning AI Agent System)  
**Test Suite Execution Date:** August 11, 2026  
**Environment:** Linux (Ubuntu/Debian), Python 3.10, FastAPI, Streamlit, LangGraph, ChromaDB, ReportLab  
**Test Coverage Scope:** End-to-End System Testing across Database, Vector Store, Ingestion, Financial Calculator, Tavily Search, PDF Generator, LangGraph Agents, FastAPI Endpoints, and Frontend Integration.

---

## 1. Executive Summary

A total of **53 test cases** covering positive flows, negative flows, boundary conditions, rate limits, schema validation, and edge cases were executed on the SpendWise-AI codebase.

| Metric | Summary |
|---|---|
| **Total Test Cases Executed** | **53** |
| **Passed Test Cases** | **48** |
| **Failed Test Cases** | **5** |
| **Pass Rate** | **90.57%** |

---

## 2. Test Execution Matrix

Below is the complete list of test cases evaluated, their execution status (`PASS` / `FAIL`), and detailed failure reasons for any test that failed.

### 2.1 Database & Authentication Engine (`database.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-DB-01** | Database schema initialization via `create_table()` | SQLite DB `spendwise_users.db` created with `users` table | **PASS** | N/A |
| **TC-DB-02** | User registration (`add_user`) with valid name, email, and password | Returns auto-incremented integer `user_id` | **PASS** | N/A |
| **TC-DB-03** | Password hashing (`hash_password`) verification | Returns 64-character SHA-256 hexadecimal string | **PASS** | N/A |
| **TC-DB-04** | User login verification (`verify_user`) with correct password | Returns matching user tuple `(user_id, username, email, password_hash)` | **PASS** | N/A |
| **TC-DB-05** | User login verification (`verify_user`) with incorrect password | Returns `None` | **PASS** | N/A |
| **TC-DB-06** | User login verification (`verify_user`) with non-existent email | Returns `None` | **PASS** | N/A |
| **TC-DB-07** | Duplicate email registration attempt (`add_user` with existing email) | Catches `sqlite3.IntegrityError` and returns `None` | **PASS** | N/A |
| **TC-DB-08** | Email lookup functions (`get_user_by_email` and `get_user_id`) | Returns valid user tuple and user ID | **PASS** | N/A |
| **TC-DB-09** | Direct case-sensitivity handling in `database.py` | Query operates on exact string match; relies on caller lowercasing | **PASS** | N/A |

---

### 2.2 Vector Store Operations (`db/vector_store.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-VS-01** | Vector store collection initialization | ChromaDB `PersistentClient` initializes collections cleanly | **PASS** | N/A |
| **TC-VS-02** | `upsert_user_profile` with valid profile dictionary | Generates embeddings via HuggingFace and stores JSON document | **PASS** | N/A |
| **TC-VS-03** | `get_user_profile` retrieval for existing user profile | Retrieves profile document parsed as dictionary | **PASS** | N/A |
| **TC-VS-04** | `get_user_profile` retrieval for non-existent user profile | Returns `None` | **PASS** | N/A |
| **TC-VS-05** | `profile_exists` check for existing vs non-existing user | Returns `True` for existing user, `False` for non-existing user | **PASS** | N/A |
| **TC-VS-06** | `upsert_market_data` snippet insertion | Upserts document into `market_data` ChromaDB collection | **PASS** | N/A |
| **TC-VS-07** | `add_past_report` PDF summary insertion | Stores summary text and filepath metadata in `past_reports` collection | **PASS** | N/A |
| **TC-VS-08** | `query_collection` vector search query with metadata filtering | Returns relevant document snippets matching query vector | **PASS** | N/A |
| **TC-VS-09** | Helper functions expected by existing test suite `test/test_end_to_end.py` | Functions `add_expense_history`, `get_expense_history`, and `get_past_reports` exist | **FAIL** | **Missing Functions in Module:** `db/vector_store.py` does not define `add_expense_history` or `get_expense_history`, causing `ImportError` when `test/test_end_to_end.py` is run. |

---

### 2.3 Knowledge Base Ingestion Pipeline (`knowledge_ingestion.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-ING-01** | Section-aware document splitting (`_split_into_sections`) with `=== Header ===` blocks | Splits document text into title and body section tuples | **FAIL** | **Regex Header Matching Flaw:** Regex `r"={3,}[\r\n]+(.*?)[\r\n]+=={3,}"` in `knowledge_ingestion.py` expects multi-line opening and closing header blocks. Single-line `=== Tax Rules ===` headers fail regex split and fall back to 1 chunk labeled "General". |
| **TC-ING-02** | Section-aware splitting fallback for plain text documents without headers | Returns single section tuple `("General", text)` | **PASS** | N/A |
| **TC-ING-03** | Metadata inference from filename (`_infer_metadata_from_filename`) | Infers category (e.g. `tax`) and persona relevance (e.g. `salaried`) | **PASS** | N/A |
| **TC-ING-04** | Section sub-chunking (`chunk_sections`) with `RecursiveCharacterTextSplitter` | Sub-chunks text into ~600 character blocks with 80 character overlap | **PASS** | N/A |
| **TC-ING-05** | MD5 content-hash generation (`_chunk_id`) for idempotent vector storage | Generates deterministic 32-character MD5 hash string | **PASS** | N/A |
| **TC-ING-06** | Knowledge base directory document loading (`load_all_sections`) | Loads and processes all 9 documents in `finance_knowledge_base/` | **PASS** | N/A |

---

### 2.4 Financial Calculation Engine (`agents/tools.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-CALC-01** | Standard financial calculation (Salaried, positive income/surplus) | Computes surplus=₹30,000, savings_rate=30%, DTI=20%, SIP=₹12,000, emergency_fund=₹330,000 | **PASS** | N/A |
| **TC-CALC-02** | Zero income edge case (`monthly_income = 0`) | Handles zero income gracefully without `ZeroDivisionError` (savings_rate=0, DTI=0) | **PASS** | N/A |
| **TC-CALC-03** | Zero expenses & zero EMI edge case (`essential = 0, non_essential = 0, house_emi = 0`) | Calculates surplus=income, savings_rate=100%, DTI=0% | **PASS** | N/A |
| **TC-CALC-04** | Negative surplus scenario (High EMI + Expenses > Income) | Calculates negative surplus (e.g. -₹25,000) and clamps recommended SIP to ₹0 (`max(surplus*0.4, 0)`) | **PASS** | N/A |
| **TC-CALC-05** | Extreme large numeric inputs (e.g. ₹100,000,000 income) | Maintains 64-bit float precision without numerical overflow | **PASS** | N/A |
| **TC-CALC-06** | Missing optional input fields in JSON input string | Defaults missing expense/EMI fields to 0 without throwing `KeyError` | **PASS** | N/A |
| **TC-CALC-07** | Non-JSON invalid payload string passed to `calculation_tool` | Raises `json.JSONDecodeError` cleanly | **PASS** | N/A |

---

### 2.5 Web Search & Market Research Tool (`agents/tools.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-MKT-01** | `tavily_search_tool` live market search query execution | Fetches top 3 web search snippets via Tavily API client | **PASS** | N/A |

---

### 2.6 PDF Report Generator & Disk Persistence (`agents/tools.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-PDF-01** | `pdf_report_tool` valid PDF report generation | Generates formatted A4 PDF containing summary, metrics tables, pie charts, and recommendations | **PASS** | N/A |
| **TC-PDF-02** | PDF output file persistence on disk | PDF file created under `reports/` folder with file size > 1,000 bytes | **PASS** | N/A |
| **TC-PDF-03** | `pdf_report_tool` invalid non-JSON payload error handling | Catches parsing exception gracefully or returns error message | **FAIL** | **Unhandled Exception:** `pdf_report_tool` attempts `json.loads(report_data)` without a `try/except` guard, crashing with an unhandled `json.decoder.JSONDecodeError` when invalid input is provided. |

---

### 2.7 Multi-Agent LangGraph Architecture & Intent Routing (`agents/graph.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-GRAPH-01** | `intent_router` fast-path for conversational greetings ("Hello SpendWise!") | Classifies query as `conversational` | **PASS** | N/A |
| **TC-GRAPH-02** | `intent_router` fast-path for educational questions ("what is compound interest?") | Classifies query as `conversational` | **PASS** | N/A |
| **TC-GRAPH-03** | `intent_router` fast-path for personal financial analysis ("Analyze my monthly budget") | Classifies query as `financial_analysis` | **PASS** | N/A |
| **TC-GRAPH-04** | `conversational_reply_agent` answer generation | Generates warm, context-aware answer using RAG snippets | **PASS** | N/A |
| **TC-GRAPH-05** | Multi-agent graph execution (`run_planning_pipeline`) | Orchestrates graph nodes (Intake, Router, RAG, Market, Calculator, Recs, Critic, Report) | **PASS** | N/A |
| **TC-GRAPH-06** | `run_planning_pipeline` invocation with extra/legacy keyword arguments (`insurance_premium`, `age`, etc.) | Accepts extra keyword arguments or ignores them safely | **FAIL** | **Rigid Function Signature:** `run_planning_pipeline` signature in `agents/graph.py` explicitly lists parameters without `**kwargs`. Passing `insurance_premium`, `health_expenses`, `other_liabilities`, or `age` raises `TypeError: run_planning_pipeline() got an unexpected keyword argument 'insurance_premium'`. |

---

### 2.8 FastAPI Backend REST API Endpoints (`backend_app.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-API-01** | GET `/` - Health check endpoint | Returns HTTP 200 with `{"message": "SpendWise Backend API Running"}` | **PASS** | N/A |
| **TC-API-02** | POST `/signup` - Successful user registration | Returns HTTP 200 with `{"success": True, "user_id": ...}` | **PASS** | N/A |
| **TC-API-03** | POST `/signup` - Duplicate email rejection | Returns HTTP 200 with `{"success": False, "message": "Email already exists"}` | **PASS** | N/A |
| **TC-API-04** | POST `/signup` - Missing request fields validation | Returns HTTP 422 Unprocessable Entity (Pydantic validation) | **PASS** | N/A |
| **TC-API-05** | POST `/login` - Valid credentials authentication | Returns HTTP 200 with `{"success": True, "user_id": ..., "profile_exists": ...}` | **PASS** | N/A |
| **TC-API-06** | POST `/login` - Incorrect password authentication failure | Returns HTTP 200 with `{"success": False, "message": "Invalid email or password"}` | **PASS** | N/A |
| **TC-API-07** | POST `/login` - Non-existent email authentication failure | Returns HTTP 200 with `{"success": False, "message": "Invalid email or password"}` | **PASS** | N/A |
| **TC-API-08** | POST `/save-profile` - User profile vector store save endpoint | Upserts user profile in ChromaDB and returns HTTP 200 with `{"success": True}` | **PASS** | N/A |
| **TC-API-09** | POST `/chat` - Financial analysis request for user with profile | Executes planning pipeline and returns HTTP 200 with `response_text`, `recommendations`, `pdf_path` | **PASS** | N/A |
| **TC-API-10** | POST `/chat` - Chat request for user WITHOUT saved profile in ChromaDB | Returns HTTP 200 with error message or default profile handling | **FAIL** | **Null Pointer Exception:** `get_user_profile(user_id_str)` returns `None` for users who haven't saved a profile. `backend_app.py` line 99 executes `fin = profile.get("financial_profile", {})` directly, crashing with `AttributeError: 'NoneType' object has no attribute 'get'`. |

---

### 2.9 Streamlit Frontend Architecture & Integration (`frontend_app.py`)

| Test ID | Test Description & Coverage | Expected Result | Status | Failure Reason (If FAILED) |
|---|---|---|---|---|
| **TC-FE-01** | Streamlit session state default configuration (`DEFAULTS`) | Initializes required session state keys (`page`, `chat_phase`, `financial_answers`) | **PASS** | N/A |
| **TC-FE-02** | Frontend `API_BASE_URL` target configuration | Points to valid FastAPI backend server address (`http://localhost:8000`) | **PASS** | N/A |

---

## 3. Deep-Dive Analysis of Failed Test Cases & Root Causes

### Failure 1: Missing Helper Functions in `db/vector_store.py` (TC-VS-09)
* **Impact:** High (Breaks existing unit test runner `test/test_end_to_end.py`).
* **Root Cause:** `test/test_end_to_end.py` attempts to import `add_expense_history`, `get_expense_history`, and `get_past_reports` from `db.vector_store`. However, `db/vector_store.py` only defined `expense_history_collection()` and `past_reports_collection()`, missing high-level helper functions for history retrieval.
* **Fix Required:** Add explicit wrapper functions in `db/vector_store.py`:
  ```python
  def add_expense_history(user_id, month, category, amount, notes=""):
      col = expense_history_collection()
      doc_id = f"exp_{user_id}_{month}_{category}"
      text = f"Month: {month} | Category: {category} | Amount: ₹{amount} | Notes: {notes}"
      embed = get_embed_model().embed_query(text)
      col.upsert(ids=[doc_id], documents=[text], embeddings=[embed], metadatas={"user_id": str(user_id), "month": month, "category": category})

  def get_expense_history(user_id: str):
      col = expense_history_collection()
      res = col.get(where={"user_id": str(user_id)})
      return res.get("documents", []) if res else []

  def get_past_reports(user_id: str):
      col = past_reports_collection()
      res = col.get(where={"user_id": str(user_id)})
      return res.get("documents", []) if res else []
  ```

---

### Failure 2: Section-Aware Splitting Regex Header Mismatch (TC-ING-01)
* **Impact:** Medium (Reduces semantic chunking quality in knowledge ingestion).
* **Root Cause:** The regex pattern `_SECTION_HEADER_RE = re.compile(r"={3,}[\r\n]+(.*?)[\r\n]+=={3,}", re.MULTILINE)` expects a title block enclosed between top and bottom multi-line equal bars. However, `.txt` files in `finance_knowledge_base/` use single-line headers formatted as `=== Tax Planning ===`.
* **Fix Required:** Update regex pattern in `knowledge_ingestion.py`:
  ```python
  _SECTION_HEADER_RE = re.compile(r"^={3,}\s*(.*?)\s*={3,}$", re.MULTILINE)
  ```

---

### Failure 3: Unhandled JSON Decoding Exception in `pdf_report_tool` (TC-PDF-03)
* **Impact:** Low/Medium (Tool robustness).
* **Root Cause:** `pdf_report_tool` in `agents/tools.py` directly executes `data = json.loads(report_data)` without a `try/except` block. Passing malformed or non-JSON strings causes the process to crash rather than returning a clean error string.
* **Fix Required:** Wrap `json.loads` inside a try-except block:
  ```python
  try:
      data = json.loads(report_data)
  except Exception as e:
      return f"Error parsing report data: {str(e)}"
  ```

---

### Failure 4: Unexpected Keyword Arguments in `run_planning_pipeline` (TC-GRAPH-06)
* **Impact:** High (Breaks legacy calls from test scripts).
* **Root Cause:** In `agents/graph.py`, `run_planning_pipeline` lists explicit parameters (`user_id`, `user_name`, `person_type`, `monthly_income`, `house_emi`, etc.) without `**kwargs`. Legacy test scripts (`test/test_end_to_end.py` and `test/test.py`) pass additional arguments such as `insurance_premium`, `health_expenses`, `other_liabilities`, `age`, raising a `TypeError`.
* **Fix Required:** Add `**kwargs` to `run_planning_pipeline` signature:
  ```python
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
      **kwargs,
  ) -> Dict[str, Any]:
  ```

---

### Failure 5: NullPointer Crash on Chat Request for Users Without Profile (TC-API-10)
* **Impact:** Critical (API endpoint crash for new users).
* **Root Cause:** In `backend_app.py` `/chat` endpoint (lines 97-99):
  ```python
  profile = get_user_profile(user_id_str)
  fin  = profile.get("financial_profile", {})
  ```
  If a user has registered via `/signup` but has not yet completed `/save-profile`, `get_user_profile()` returns `None`. `profile.get(...)` then raises `AttributeError: 'NoneType' object has no attribute 'get'`, leading to a pipeline error.
* **Fix Required:** Add null check fallback in `backend_app.py`:
  ```python
  profile = get_user_profile(user_id_str) or {}
  fin = profile.get("financial_profile", {})
  ```

---

## 4. Conclusion & Recommendations

1. **Overall Health:** The core business logic of SpendWise-AI — including SQLite authentication, standard ChromaDB vector store upserts/retrievals, financial calculation formulas (surplus, DTI, savings rate), Tavily web search integration, ReportLab PDF generation, and multi-agent LangGraph execution — is **working correctly (48/53 test cases passed)**.
2. **Key Bug Fixes Recommended:**
   - **`backend_app.py`**: Add `profile = get_user_profile(user_id_str) or {}` to prevent crashes when new users chat before saving a profile.
   - **`agents/graph.py`**: Add `**kwargs` to `run_planning_pipeline` to accept additional user parameters gracefully.
   - **`db/vector_store.py`**: Implement `add_expense_history`, `get_expense_history`, and `get_past_reports` to resolve existing test runner import errors.
   - **`knowledge_ingestion.py`**: Update header splitting regex to support single-line `=== Section ===` formatting.
   - **`agents/tools.py`**: Add JSON decoding try-except block inside `pdf_report_tool`.
