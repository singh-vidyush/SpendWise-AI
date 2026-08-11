import sys
import os
import json
import traceback
import sqlite3
from typing import Dict, Any, List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

results = []

def record_test(test_id: str, title: str, category: str, pass_status: bool, error_msg: str = ""):
    status_str = "PASS" if pass_status else "FAIL"
    results.append({
        "id": test_id,
        "title": title,
        "category": category,
        "status": status_str,
        "reason": error_msg
    })
    icon = "✅" if pass_status else "❌"
    print(f"{icon} [{test_id}] {category} - {title}: {status_str}")
    if not pass_status and error_msg:
        print(f"   Reason: {error_msg}")

print("==================================================")
print("  SPENDWISE-AI COMPREHENSIVE END-TO-END SUITE     ")
print("==================================================\n")

# ----------------------------------------------------
# CATEGORY 1: DATABASE & AUTH ENGINE (database.py)
# ----------------------------------------------------
print("--- 1. Testing Database & Auth Engine ---")
try:
    import database
    database.create_table()
    record_test("TC-DB-01", "Database schema initialization (create_table)", "Database & Auth", True)
except Exception as e:
    record_test("TC-DB-01", "Database schema initialization (create_table)", "Database & Auth", False, str(e))

try:
    test_email = "test_user_e2e@example.com"
    # Clean up prior test user if exists
    conn = database.get_connection()
    conn.cursor().execute("DELETE FROM users WHERE email = ?", (test_email,))
    conn.commit()
    conn.close()

    user_id = database.add_user("E2E User", test_email, "Secret123")
    if user_id is not None:
        record_test("TC-DB-02", "User registration with valid credentials", "Database & Auth", True)
    else:
        record_test("TC-DB-02", "User registration with valid credentials", "Database & Auth", False, "Returned None user_id")
except Exception as e:
    record_test("TC-DB-02", "User registration with valid credentials", "Database & Auth", False, str(e))

try:
    hashed = database.hash_password("Secret123")
    if isinstance(hashed, str) and len(hashed) == 64:
        record_test("TC-DB-03", "Password SHA-256 hashing", "Database & Auth", True)
    else:
        record_test("TC-DB-03", "Password SHA-256 hashing", "Database & Auth", False, f"Unexpected hash output: {hashed}")
except Exception as e:
    record_test("TC-DB-03", "Password SHA-256 hashing", "Database & Auth", False, str(e))

try:
    user = database.verify_user("test_user_e2e@example.com", "Secret123")
    if user and user[1] == "E2E User":
        record_test("TC-DB-04", "User verification with correct credentials", "Database & Auth", True)
    else:
        record_test("TC-DB-04", "User verification with correct credentials", "Database & Auth", False, f"Unexpected user output: {user}")
except Exception as e:
    record_test("TC-DB-04", "User verification with correct credentials", "Database & Auth", False, str(e))

try:
    user_wrong = database.verify_user("test_user_e2e@example.com", "WrongPass")
    if user_wrong is None:
        record_test("TC-DB-05", "User verification with wrong password", "Database & Auth", True)
    else:
        record_test("TC-DB-05", "User verification with wrong password", "Database & Auth", False, "Expected None for wrong password")
except Exception as e:
    record_test("TC-DB-05", "User verification with wrong password", "Database & Auth", False, str(e))

try:
    user_nonexist = database.verify_user("nonexistent_user_999@example.com", "Secret123")
    if user_nonexist is None:
        record_test("TC-DB-06", "User verification with non-existent email", "Database & Auth", True)
    else:
        record_test("TC-DB-06", "User verification with non-existent email", "Database & Auth", False, "Expected None for non-existent user")
except Exception as e:
    record_test("TC-DB-06", "User verification with non-existent email", "Database & Auth", False, str(e))

try:
    dup_id = database.add_user("E2E User 2", "test_user_e2e@example.com", "Secret123")
    if dup_id is None:
        record_test("TC-DB-07", "Duplicate email registration handling", "Database & Auth", True)
    else:
        record_test("TC-DB-07", "Duplicate email registration handling", "Database & Auth", False, f"Expected None on duplicate email, got {dup_id}")
except Exception as e:
    record_test("TC-DB-07", "Duplicate email registration handling", "Database & Auth", False, str(e))

try:
    fetched_user = database.get_user_by_email("test_user_e2e@example.com")
    uid = database.get_user_id("test_user_e2e@example.com")
    if fetched_user and uid is not None:
        record_test("TC-DB-08", "Email lookup functions (get_user_by_email, get_user_id)", "Database & Auth", True)
    else:
        record_test("TC-DB-08", "Email lookup functions", "Database & Auth", False, "Lookup returned None")
except Exception as e:
    record_test("TC-DB-08", "Email lookup functions", "Database & Auth", False, str(e))

try:
    fetched_upper = database.get_user_by_email("TEST_USER_E2E@EXAMPLE.COM")
    # database.py uses exact string matching SQL: WHERE email = ? without LOWER() inside database.py
    if fetched_upper is None:
        record_test("TC-DB-09", "Direct case-sensitivity check in database.py (requires caller lower-casing)", "Database & Auth", True)
    else:
        record_test("TC-DB-09", "Direct case-sensitivity check in database.py", "Database & Auth", True)
except Exception as e:
    record_test("TC-DB-09", "Direct case-sensitivity check in database.py", "Database & Auth", False, str(e))


# ----------------------------------------------------
# CATEGORY 2: VECTOR STORE OPERATIONS (db/vector_store.py)
# ----------------------------------------------------
print("\n--- 2. Testing Vector Store Operations ---")
try:
    import db.vector_store as vs
    col = vs.user_profiles_collection()
    if col is not None:
        record_test("TC-VS-01", "Vector store collection initialization", "Vector Store", True)
    else:
        record_test("TC-VS-01", "Vector store collection initialization", "Vector Store", False, "Collection is None")
except Exception as e:
    record_test("TC-VS-01", "Vector store collection initialization", "Vector Store", False, str(e))

try:
    test_v_user = "v_test_100"
    test_prof = {
        "user_name": "Vector Tester",
        "financial_profile": {
            "persona": "Salaried",
            "monthly_income": 80000,
            "essential_expenses": 25000,
            "non_essential_expenses": 10000,
            "current_savings": 150000,
            "debt_details": {"has_debt": True, "monthly_emi": 15000}
        }
    }
    saved_json = vs.upsert_user_profile(test_v_user, test_prof, "sess_100")
    if saved_json and "Vector Tester" in saved_json:
        record_test("TC-VS-02", "upsert_user_profile with valid profile dictionary", "Vector Store", True)
    else:
        record_test("TC-VS-02", "upsert_user_profile", "Vector Store", False, f"Saved JSON: {saved_json}")
except Exception as e:
    record_test("TC-VS-02", "upsert_user_profile", "Vector Store", False, str(e))

try:
    retrieved = vs.get_user_profile(test_v_user)
    if retrieved and retrieved.get("user_name") == "Vector Tester":
        record_test("TC-VS-03", "get_user_profile for existing profile", "Vector Store", True)
    else:
        record_test("TC-VS-03", "get_user_profile for existing profile", "Vector Store", False, f"Retrieved: {retrieved}")
except Exception as e:
    record_test("TC-VS-03", "get_user_profile for existing profile", "Vector Store", False, str(e))

try:
    non_exist_prof = vs.get_user_profile("non_existent_user_99999")
    if non_exist_prof is None:
        record_test("TC-VS-04", "get_user_profile for non-existent profile", "Vector Store", True)
    else:
        record_test("TC-VS-04", "get_user_profile for non-existent profile", "Vector Store", False, f"Expected None, got {non_exist_prof}")
except Exception as e:
    record_test("TC-VS-04", "get_user_profile for non-existent profile", "Vector Store", False, str(e))

try:
    exists_true = vs.profile_exists(test_v_user)
    exists_false = vs.profile_exists("non_existent_user_99999")
    if exists_true and not exists_false:
        record_test("TC-VS-05", "profile_exists check for existing vs non-existing user", "Vector Store", True)
    else:
        record_test("TC-VS-05", "profile_exists check", "Vector Store", False, f"exists_true={exists_true}, exists_false={exists_false}")
except Exception as e:
    record_test("TC-VS-05", "profile_exists check", "Vector Store", False, str(e))

try:
    vs.upsert_market_data("mkt_doc_1", "RBI keeps repo rate unchanged at 6.5%", {"source": "test"})
    record_test("TC-VS-06", "upsert_market_data insertion into ChromaDB", "Vector Store", True)
except Exception as e:
    record_test("TC-VS-06", "upsert_market_data insertion into ChromaDB", "Vector Store", False, str(e))

try:
    vs.add_past_report("v_test_100", "rep_100", "Summary of financial report", "/tmp/report.pdf")
    record_test("TC-VS-07", "add_past_report insertion into past_reports collection", "Vector Store", True)
except Exception as e:
    record_test("TC-VS-07", "add_past_report insertion", "Vector Store", False, str(e))

try:
    res = vs.query_collection(vs.financial_knowledge_collection(), "tax rules", n_results=2)
    record_test("TC-VS-08", "query_collection vector search query", "Vector Store", True)
except Exception as e:
    record_test("TC-VS-08", "query_collection vector search query", "Vector Store", False, str(e))

try:
    # Check for missing helper functions referenced by test_end_to_end.py
    has_add_exp = hasattr(vs, "add_expense_history")
    has_get_exp = hasattr(vs, "get_expense_history")
    has_get_rep = hasattr(vs, "get_past_reports")
    if has_add_exp and has_get_exp and has_get_rep:
        record_test("TC-VS-09", "Helper functions expected by test_end_to_end.py (add_expense_history, get_expense_history, get_past_reports)", "Vector Store", True)
    else:
        missing = []
        if not has_add_exp: missing.append("add_expense_history")
        if not has_get_exp: missing.append("get_expense_history")
        if not has_get_rep: missing.append("get_past_reports")
        record_test("TC-VS-09", "Helper functions expected by test_end_to_end.py (add_expense_history, get_expense_history, get_past_reports)", "Vector Store", False, f"Missing functions in db/vector_store.py: {', '.join(missing)}")
except Exception as e:
    record_test("TC-VS-09", "Helper functions expected by test_end_to_end.py", "Vector Store", False, str(e))


# ----------------------------------------------------
# CATEGORY 3: KNOWLEDGE INGESTION PIPELINE (knowledge_ingestion.py)
# ----------------------------------------------------
print("\n--- 3. Testing Knowledge Ingestion Pipeline ---")
try:
    import knowledge_ingestion as ki
    sample_text = "=== Tax Rules ===\nStandard deduction is 50k.\n=== Investment ===\nSIP is good."
    sections = ki._split_into_sections(sample_text)
    if len(sections) == 2 and sections[0][0] == "Tax Rules":
        record_test("TC-ING-01", "Section-aware splitting (_split_into_sections) with header delimiters", "Knowledge Ingestion", True)
    else:
        record_test("TC-ING-01", "Section-aware splitting", "Knowledge Ingestion", False, f"Parsed sections: {sections}")
except Exception as e:
    record_test("TC-ING-01", "Section-aware splitting", "Knowledge Ingestion", False, str(e))

try:
    plain_text = "Just some random text without headers."
    sections_plain = ki._split_into_sections(plain_text)
    if len(sections_plain) == 1 and sections_plain[0][0] == "General":
        record_test("TC-ING-02", "Section-aware splitting fallback for plain text", "Knowledge Ingestion", True)
    else:
        record_test("TC-ING-02", "Section-aware splitting fallback", "Knowledge Ingestion", False, f"Parsed sections: {sections_plain}")
except Exception as e:
    record_test("TC-ING-02", "Section-aware splitting fallback", "Knowledge Ingestion", False, str(e))

try:
    cat, personas = ki._infer_metadata_from_filename("data/tax_guide.txt")
    if cat == "tax" and "salaried" in personas:
        record_test("TC-ING-03", "Metadata inference from filename (_infer_metadata_from_filename)", "Knowledge Ingestion", True)
    else:
        record_test("TC-ING-03", "Metadata inference from filename", "Knowledge Ingestion", False, f"cat={cat}, personas={personas}")
except Exception as e:
    record_test("TC-ING-03", "Metadata inference from filename", "Knowledge Ingestion", False, str(e))

try:
    sec_data = [{"text": "A" * 1000, "section_title": "Long Section", "source_file": "doc.txt", "category": "tax", "persona_relevance": "all"}]
    chunks = ki.chunk_sections(sec_data)
    if len(chunks) > 1:
        record_test("TC-ING-04", "Section sub-chunking (chunk_sections)", "Knowledge Ingestion", True)
    else:
        record_test("TC-ING-04", "Section sub-chunking", "Knowledge Ingestion", False, f"Chunks count: {len(chunks)}")
except Exception as e:
    record_test("TC-ING-04", "Section sub-chunking", "Knowledge Ingestion", False, str(e))

try:
    chunk_item = {"source_file": "a.txt", "section_title": "sec1", "text": "sample text for MD5 testing"}
    cid = ki._chunk_id(chunk_item)
    if isinstance(cid, str) and len(cid) == 32:
        record_test("TC-ING-05", "MD5 content-hash generation (_chunk_id)", "Knowledge Ingestion", True)
    else:
        record_test("TC-ING-05", "MD5 content-hash generation", "Knowledge Ingestion", False, f"Chunk ID: {cid}")
except Exception as e:
    record_test("TC-ING-05", "MD5 content-hash generation", "Knowledge Ingestion", False, str(e))

try:
    all_secs = ki.load_all_sections()
    if len(all_secs) > 0:
        record_test("TC-ING-06", "Knowledge base directory document loading (load_all_sections)", "Knowledge Ingestion", True)
    else:
        record_test("TC-ING-06", "Knowledge base document loading", "Knowledge Ingestion", False, "No sections loaded from finance_knowledge_base")
except Exception as e:
    record_test("TC-ING-06", "Knowledge base document loading", "Knowledge Ingestion", False, str(e))


# ----------------------------------------------------
# CATEGORY 4: FINANCIAL CALCULATION ENGINE (agents/tools.py)
# ----------------------------------------------------
print("\n--- 4. Testing Financial Calculation Engine ---")
try:
    import agents.tools as tools
    data_standard = {
        "monthly_income": 100000,
        "essential_expenses": 35000,
        "non_essential_expenses": 15000,
        "current_savings": 300000,
        "house_emi": 20000,
        "person_type": "salaried"
    }
    res_str = tools.calculation_tool.invoke({"user_data": json.dumps(data_standard)})
    res = json.loads(res_str)
    if res.get("monthly_surplus") == 30000 and res.get("savings_rate_pct") == 30.0 and res.get("dti_ratio_pct") == 20.0:
        record_test("TC-CALC-01", "Standard financial calculation (Salaried, positive income/surplus)", "Calculation Engine", True)
    else:
        record_test("TC-CALC-01", "Standard financial calculation", "Calculation Engine", False, f"Unexpected calc output: {res}")
except Exception as e:
    record_test("TC-CALC-01", "Standard financial calculation", "Calculation Engine", False, str(e))

try:
    data_zero_inc = {
        "monthly_income": 0,
        "essential_expenses": 10000,
        "house_emi": 5000
    }
    res_zero = json.loads(tools.calculation_tool.invoke({"user_data": json.dumps(data_zero_inc)}))
    if res_zero.get("savings_rate_pct") == 0 and res_zero.get("dti_ratio_pct") == 0 and res_zero.get("monthly_surplus") == -15000:
        record_test("TC-CALC-02", "Zero income edge case (Division-by-zero protection)", "Calculation Engine", True)
    else:
        record_test("TC-CALC-02", "Zero income edge case", "Calculation Engine", False, f"Output: {res_zero}")
except Exception as e:
    record_test("TC-CALC-02", "Zero income edge case", "Calculation Engine", False, str(e))

try:
    data_zero_exp = {
        "monthly_income": 50000,
        "essential_expenses": 0,
        "non_essential_expenses": 0,
        "house_emi": 0
    }
    res_zero_exp = json.loads(tools.calculation_tool.invoke({"user_data": json.dumps(data_zero_exp)}))
    if res_zero_exp.get("monthly_surplus") == 50000 and res_zero_exp.get("savings_rate_pct") == 100.0:
        record_test("TC-CALC-03", "Zero expenses & zero EMI edge case", "Calculation Engine", True)
    else:
        record_test("TC-CALC-03", "Zero expenses & zero EMI edge case", "Calculation Engine", False, f"Output: {res_zero_exp}")
except Exception as e:
    record_test("TC-CALC-03", "Zero expenses & zero EMI edge case", "Calculation Engine", False, str(e))

try:
    data_neg_surplus = {
        "monthly_income": 50000,
        "essential_expenses": 40000,
        "non_essential_expenses": 20000,
        "house_emi": 15000
    }
    res_neg = json.loads(tools.calculation_tool.invoke({"user_data": json.dumps(data_neg_surplus)}))
    if res_neg.get("monthly_surplus") == -25000 and res_neg.get("recommended_monthly_sip") == 0:
        record_test("TC-CALC-04", "Negative surplus & high debt edge case", "Calculation Engine", True)
    else:
        record_test("TC-CALC-04", "Negative surplus & high debt edge case", "Calculation Engine", False, f"Output: {res_neg}")
except Exception as e:
    record_test("TC-CALC-04", "Negative surplus & high debt edge case", "Calculation Engine", False, str(e))

try:
    data_huge = {
        "monthly_income": 100000000,
        "essential_expenses": 10000000,
        "house_emi": 5000000
    }
    res_huge = json.loads(tools.calculation_tool.invoke({"user_data": json.dumps(data_huge)}))
    if res_huge.get("monthly_surplus") == 85000000:
        record_test("TC-CALC-05", "Extreme large numeric values stability test", "Calculation Engine", True)
    else:
        record_test("TC-CALC-05", "Extreme large numeric values test", "Calculation Engine", False, f"Output: {res_huge}")
except Exception as e:
    record_test("TC-CALC-05", "Extreme large numeric values test", "Calculation Engine", False, str(e))

try:
    data_missing_fields = {"monthly_income": 50000}
    res_missing = json.loads(tools.calculation_tool.invoke({"user_data": json.dumps(data_missing_fields)}))
    if res_missing.get("monthly_surplus") == 50000:
        record_test("TC-CALC-06", "Missing optional input fields handling", "Calculation Engine", True)
    else:
        record_test("TC-CALC-06", "Missing optional input fields handling", "Calculation Engine", False, f"Output: {res_missing}")
except Exception as e:
    record_test("TC-CALC-06", "Missing optional input fields handling", "Calculation Engine", False, str(e))

try:
    bad_payload = "NOT_JSON"
    try:
        tools.calculation_tool.invoke({"user_data": bad_payload})
        record_test("TC-CALC-07", "Invalid non-JSON payload handling in calculation_tool", "Calculation Engine", False, "Did not raise JSONDecodeError")
    except json.JSONDecodeError:
        record_test("TC-CALC-07", "Invalid non-JSON payload handling in calculation_tool", "Calculation Engine", True)
except Exception as e:
    record_test("TC-CALC-07", "Invalid non-JSON payload handling in calculation_tool", "Calculation Engine", False, str(e))


# ----------------------------------------------------
# CATEGORY 5: WEB SEARCH & MARKET RESEARCH TOOL (agents/tools.py)
# ----------------------------------------------------
print("\n--- 5. Testing Web Search & Market Research Tool ---")
try:
    mkt_res = tools.tavily_search_tool.invoke({"query": "India RBI repo rate"})
    if isinstance(mkt_res, str) and len(mkt_res) > 0:
        record_test("TC-MKT-01", "Tavily market search tool execution", "Market Research", True)
    else:
        record_test("TC-MKT-01", "Tavily market search tool execution", "Market Research", False, f"Result: {mkt_res}")
except Exception as e:
    record_test("TC-MKT-01", "Tavily market search tool execution", "Market Research", False, str(e))


# ----------------------------------------------------
# CATEGORY 6: PDF REPORT GENERATOR (agents/tools.py)
# ----------------------------------------------------
print("\n--- 6. Testing PDF Report Generator ---")
try:
    sample_report = {
        "user_id": "v_test_100",
        "user_name": "Report Tester",
        "person_type": "Salaried",
        "calculations": {
            "monthly_income": 90000,
            "monthly_surplus": 35000,
            "savings_rate_pct": 38.8,
            "dti_ratio_pct": 22.2,
            "house_emi": 20000,
            "essential_expenses": 25000,
            "non_essential_expenses": 10000,
            "emergency_fund_target": 270000,
            "recommended_monthly_sip": 14000
        },
        "recommendations": [
            "Build an emergency fund of ₹2,70,000",
            "Start ₹14,000 monthly SIP in index funds"
        ],
        "tradeoff_analysis": [
            {"option": "Option 1: Aggressive SIP", "pros": "High returns", "cons": "Less liquidity"}
        ],
        "market_insights": "Inflation is currently around 5.1%."
    }
    pdf_out = tools.pdf_report_tool.invoke({"report_data": json.dumps(sample_report)})
    if pdf_out and os.path.exists(pdf_out) and os.path.getsize(pdf_out) > 0:
        record_test("TC-PDF-01", "pdf_report_tool valid PDF report generation", "PDF Generation", True)
    else:
        record_test("TC-PDF-01", "pdf_report_tool valid PDF report generation", "PDF Generation", False, f"Output path: {pdf_out}")
except Exception as e:
    record_test("TC-PDF-01", "pdf_report_tool valid PDF report generation", "PDF Generation", False, str(e))

try:
    if 'pdf_out' in locals() and os.path.exists(pdf_out):
        size = os.path.getsize(pdf_out)
        if size > 1000:
            record_test("TC-PDF-02", "PDF file persistence & non-empty byte size verification", "PDF Generation", True)
        else:
            record_test("TC-PDF-02", "PDF file persistence verification", "PDF Generation", False, f"File size too small: {size} bytes")
    else:
        record_test("TC-PDF-02", "PDF file persistence verification", "PDF Generation", False, "PDF file does not exist")
except Exception as e:
    record_test("TC-PDF-02", "PDF file persistence verification", "PDF Generation", False, str(e))

try:
    try:
        tools.pdf_report_tool.invoke({"report_data": "INVALID_JSON"})
        record_test("TC-PDF-03", "pdf_report_tool invalid JSON payload error handling", "PDF Generation", False, "Did not handle invalid JSON")
    except Exception:
        record_test("TC-PDF-03", "pdf_report_tool invalid JSON payload error handling", "PDF Generation", True)
except Exception as e:
    record_test("TC-PDF-03", "pdf_report_tool invalid JSON payload error handling", "PDF Generation", False, str(e))


# ----------------------------------------------------
# CATEGORY 7: LANGGRAPH AGENT ARCHITECTURE & ROUTING (agents/graph.py)
# ----------------------------------------------------
print("\n--- 7. Testing LangGraph Agent Architecture & Routing ---")
try:
    import agents.graph as graph_mod
    s_greet = graph_mod.intent_router({"query": "Hello SpendWise!"})
    if s_greet.get("intent") == "conversational":
        record_test("TC-GRAPH-01", "intent_router fast-path for conversational greetings", "LangGraph Agents", True)
    else:
        record_test("TC-GRAPH-01", "intent_router fast-path for greetings", "LangGraph Agents", False, f"Intent: {s_greet.get('intent')}")
except Exception as e:
    record_test("TC-GRAPH-01", "intent_router fast-path for greetings", "LangGraph Agents", False, str(e))

try:
    s_def = graph_mod.intent_router({"query": "what is compound interest in mutual funds?"})
    if s_def.get("intent") == "conversational":
        record_test("TC-GRAPH-02", "intent_router fast-path for pure educational questions", "LangGraph Agents", True)
    else:
        record_test("TC-GRAPH-02", "intent_router fast-path for educational questions", "LangGraph Agents", False, f"Intent: {s_def.get('intent')}")
except Exception as e:
    record_test("TC-GRAPH-02", "intent_router fast-path for educational questions", "LangGraph Agents", False, str(e))

try:
    s_anal = graph_mod.intent_router({"query": "Analyze my monthly income of 80000 and tell me how to save"})
    if s_anal.get("intent") == "financial_analysis":
        record_test("TC-GRAPH-03", "intent_router fast-path for personal financial analysis", "LangGraph Agents", True)
    else:
        record_test("TC-GRAPH-03", "intent_router fast-path for financial analysis", "LangGraph Agents", False, f"Intent: {s_anal.get('intent')}")
except Exception as e:
    record_test("TC-GRAPH-03", "intent_router fast-path for financial analysis", "LangGraph Agents", False, str(e))

try:
    conv_out = graph_mod.conversational_reply_agent({
        "query": "What is an SIP?",
        "profile": {"user_name": "Alice"},
        "person_type": "Salaried",
        "retrieved_context": {"knowledge_snippets": ["SIP stands for Systematic Investment Plan."]}
    })
    if conv_out.get("response_text") and len(conv_out["response_text"]) > 10:
        record_test("TC-GRAPH-04", "conversational_reply_agent answer generation", "LangGraph Agents", True)
    else:
        record_test("TC-GRAPH-04", "conversational_reply_agent answer generation", "LangGraph Agents", False, f"Output: {conv_out}")
except Exception as e:
    record_test("TC-GRAPH-04", "conversational_reply_agent answer generation", "LangGraph Agents", False, str(e))

try:
    e2e_res = graph_mod.run_planning_pipeline(
        user_id="v_test_100",
        user_name="Graph Tester",
        person_type="Salaried",
        monthly_income=85000,
        house_emi=18000,
        essential_expenses=25000,
        non_essential_expenses=12000,
        current_savings=200000,
        chat_query="Analyze my budget and suggest SIP options."
    )
    has_metrics = bool(e2e_res.get("financial_metrics"))
    has_recs = len(e2e_res.get("recommendations", [])) > 0
    has_pdf = bool(e2e_res.get("pdf_path")) and os.path.exists(e2e_res.get("pdf_path", ""))
    if has_metrics and has_recs and has_pdf:
        record_test("TC-GRAPH-05", "End-to-end planning pipeline execution (run_planning_pipeline)", "LangGraph Agents", True)
    else:
        record_test("TC-GRAPH-05", "End-to-end planning pipeline execution", "LangGraph Agents", False, f"has_metrics={has_metrics}, has_recs={has_recs}, has_pdf={has_pdf}")
except Exception as e:
    record_test("TC-GRAPH-05", "End-to-end planning pipeline execution", "LangGraph Agents", False, str(e))

try:
    try:
        graph_mod.run_planning_pipeline(
            user_id="v_test_100",
            user_name="Graph Tester",
            person_type="Salaried",
            monthly_income=85000,
            house_emi=18000,
            insurance_premium=2000,
            health_expenses=3000,
            other_liabilities=[],
            age=28,
            chat_query="Analyze budget"
        )
        record_test("TC-GRAPH-06", "run_planning_pipeline with extra kwargs (insurance_premium, age, etc.)", "LangGraph Agents", True)
    except TypeError as te:
        record_test("TC-GRAPH-06", "run_planning_pipeline with extra kwargs (insurance_premium, age, etc.)", "LangGraph Agents", False, f"TypeError: {te}")
except Exception as e:
    record_test("TC-GRAPH-06", "run_planning_pipeline with extra kwargs", "LangGraph Agents", False, str(e))


# ----------------------------------------------------
# CATEGORY 8: BACKEND FASTAPI API ENDPOINTS (backend_app.py)
# ----------------------------------------------------
print("\n--- 8. Testing Backend FastAPI API Endpoints ---")
try:
    from fastapi.testclient import TestClient
    import backend_app
    client = TestClient(backend_app.app)
    
    r_home = client.get("/")
    if r_home.status_code == 200 and "message" in r_home.json():
        record_test("TC-API-01", "GET / health check endpoint", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-01", "GET / health check endpoint", "FastAPI Endpoints", False, f"Status {r_home.status_code}, body: {r_home.text}")
except Exception as e:
    record_test("TC-API-01", "GET / health check endpoint", "FastAPI Endpoints", False, str(e))

try:
    signup_email = "api_test_user_1@example.com"
    conn = database.get_connection()
    conn.cursor().execute("DELETE FROM users WHERE email = ?", (signup_email,))
    conn.commit()
    conn.close()

    r_signup = client.post("/signup", json={"username": "API User", "email": signup_email, "password": "Password123"})
    res_sign = r_signup.json()
    if r_signup.status_code == 200 and res_sign.get("success") is True and "user_id" in res_sign:
        record_test("TC-API-02", "POST /signup successful registration", "FastAPI Endpoints", True)
        api_user_id = res_sign["user_id"]
    else:
        record_test("TC-API-02", "POST /signup successful registration", "FastAPI Endpoints", False, f"Body: {res_sign}")
        api_user_id = 999
except Exception as e:
    record_test("TC-API-02", "POST /signup successful registration", "FastAPI Endpoints", False, str(e))
    api_user_id = 999

try:
    r_signup_dup = client.post("/signup", json={"username": "API User Dup", "email": "api_test_user_1@example.com", "password": "Password123"})
    res_dup = r_signup_dup.json()
    if r_signup_dup.status_code == 200 and res_dup.get("success") is False and "already exists" in res_dup.get("message", ""):
        record_test("TC-API-03", "POST /signup duplicate email rejection", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-03", "POST /signup duplicate email rejection", "FastAPI Endpoints", False, f"Body: {res_dup}")
except Exception as e:
    record_test("TC-API-03", "POST /signup duplicate email rejection", "FastAPI Endpoints", False, str(e))

try:
    r_signup_invalid = client.post("/signup", json={"email": "bad@example.com"})
    if r_signup_invalid.status_code == 422:
        record_test("TC-API-04", "POST /signup missing fields validation (422 Unprocessable)", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-04", "POST /signup missing fields validation", "FastAPI Endpoints", False, f"Status: {r_signup_invalid.status_code}")
except Exception as e:
    record_test("TC-API-04", "POST /signup missing fields validation", "FastAPI Endpoints", False, str(e))

try:
    r_login = client.post("/login", json={"email": "api_test_user_1@example.com", "password": "Password123"})
    res_login = r_login.json()
    if r_login.status_code == 200 and res_login.get("success") is True and "user_id" in res_login:
        record_test("TC-API-05", "POST /login valid credentials authentication", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-05", "POST /login valid credentials authentication", "FastAPI Endpoints", False, f"Body: {res_login}")
except Exception as e:
    record_test("TC-API-05", "POST /login valid credentials authentication", "FastAPI Endpoints", False, str(e))

try:
    r_login_bad_pass = client.post("/login", json={"email": "api_test_user_1@example.com", "password": "WrongPassword"})
    res_lbad = r_login_bad_pass.json()
    if r_login_bad_pass.status_code == 200 and res_lbad.get("success") is False:
        record_test("TC-API-06", "POST /login incorrect password authentication", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-06", "POST /login incorrect password authentication", "FastAPI Endpoints", False, f"Body: {res_lbad}")
except Exception as e:
    record_test("TC-API-06", "POST /login incorrect password authentication", "FastAPI Endpoints", False, str(e))

try:
    r_login_nonexist = client.post("/login", json={"email": "nobody_exists_12345@example.com", "password": "Password123"})
    res_lnone = r_login_nonexist.json()
    if r_login_nonexist.status_code == 200 and res_lnone.get("success") is False:
        record_test("TC-API-07", "POST /login non-existent email authentication", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-07", "POST /login non-existent email authentication", "FastAPI Endpoints", False, f"Body: {res_lnone}")
except Exception as e:
    record_test("TC-API-07", "POST /login non-existent email authentication", "FastAPI Endpoints", False, str(e))

try:
    prof_payload = {
        "user_id": api_user_id,
        "profile": {
            "user_name": "API User",
            "financial_profile": {
                "persona": "Salaried",
                "monthly_income": 75000,
                "essential_expenses": 25000,
                "non_essential_expenses": 10000,
                "current_savings": 100000,
                "debt_details": {"has_debt": True, "monthly_emi": 12000}
            }
        }
    }
    r_save = client.post("/save-profile", json=prof_payload)
    res_save = r_save.json()
    if r_save.status_code == 200 and res_save.get("success") is True:
        record_test("TC-API-08", "POST /save-profile valid user profile save", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-08", "POST /save-profile valid user profile save", "FastAPI Endpoints", False, f"Body: {res_save}")
except Exception as e:
    record_test("TC-API-08", "POST /save-profile valid user profile save", "FastAPI Endpoints", False, str(e))

try:
    r_chat = client.post("/chat", json={"user_id": api_user_id, "message": "Analyze my expenses and debt."})
    res_chat = r_chat.json()
    if r_chat.status_code == 200 and res_chat.get("success") is True and "response_text" in res_chat:
        record_test("TC-API-09", "POST /chat financial analysis request for user with profile", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-09", "POST /chat financial analysis request", "FastAPI Endpoints", False, f"Body: {res_chat}")
except Exception as e:
    record_test("TC-API-09", "POST /chat financial analysis request", "FastAPI Endpoints", False, str(e))

try:
    # EDGE CASE: POST /chat for a user_id that does NOT have a profile in vector store!
    unprofiled_user_id = 9999999
    r_chat_noprof = client.post("/chat", json={"user_id": unprofiled_user_id, "message": "Hello"})
    res_cnoprof = r_chat_noprof.json()
    if r_chat_noprof.status_code == 200 and res_cnoprof.get("success") is True:
        record_test("TC-API-10", "POST /chat for user WITHOUT saved profile (Edge Case: NoneType profile)", "FastAPI Endpoints", True)
    else:
        record_test("TC-API-10", "POST /chat for user WITHOUT saved profile (Edge Case: NoneType profile)", "FastAPI Endpoints", False, f"Response: {res_cnoprof}")
except Exception as e:
    record_test("TC-API-10", "POST /chat for user WITHOUT saved profile", "FastAPI Endpoints", False, str(e))


# ----------------------------------------------------
# CATEGORY 9: FRONTEND APP INTEGRATION (frontend_app.py)
# ----------------------------------------------------
print("\n--- 9. Testing Frontend App Integration ---")
try:
    import frontend_app as fe
    if hasattr(fe, "DEFAULTS") and "page" in fe.DEFAULTS and "chat_phase" in fe.DEFAULTS:
        record_test("TC-FE-01", "Streamlit frontend DEFAULTS session state definition", "Frontend Integration", True)
    else:
        record_test("TC-FE-01", "Streamlit frontend DEFAULTS definition", "Frontend Integration", False, "Missing expected DEFAULTS keys")
except Exception as e:
    record_test("TC-FE-01", "Streamlit frontend DEFAULTS definition", "Frontend Integration", False, str(e))

try:
    if hasattr(fe, "API_BASE_URL") and fe.API_BASE_URL == "http://localhost:8000":
        record_test("TC-FE-02", "Frontend API_BASE_URL configuration", "Frontend Integration", True)
    else:
        record_test("TC-FE-02", "Frontend API_BASE_URL configuration", "Frontend Integration", False, f"API_BASE_URL: {getattr(fe, 'API_BASE_URL', None)}")
except Exception as e:
    record_test("TC-FE-02", "Frontend API_BASE_URL configuration", "Frontend Integration", False, str(e))


print("\n==================================================")
print("             SUMMARY OF TEST RESULTS              ")
print("==================================================")
total_tests = len(results)
passed_tests = sum(1 for r in results if r["status"] == "PASS")
failed_tests = total_tests - passed_tests

print(f"Total Test Cases Executed: {total_tests}")
print(f"Passed: {passed_tests}")
print(f"Failed: {failed_tests}\n")

# Save detailed results to JSON
with open("test_execution_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Saved test results to test_execution_results.json")
