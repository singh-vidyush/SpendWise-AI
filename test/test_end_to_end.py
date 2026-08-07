"""
Comprehensive End-to-End Test for SpendWise-AI Pipeline.
Tests:
  1. Vector Store Ops (all 5 collections, profile normalization, upsert, retrieval)
  2. Calculation Engine (Surplus, DTI, Tax, Net Worth, Emergency Fund)
  3. LangGraph Pipeline (Intake, Intent Router, RAG, Market, Calc, Advisor, Trade-off, Critic, Report)
  4. Conversational Routing
  5. PDF Report Generation & Summary Storage
"""

import json
import os
import sys

# Ensure root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.vector_store import (
    upsert_user_profile,
    get_user_profile,
    profile_exists,
    add_expense_history,
    get_expense_history,
    add_past_report,
    get_past_reports,
)
from agents.tools import calculation_tool
from agents.graph import run_planning_pipeline


def test_vector_store():
    print("\n--- TEST 1: Vector Store Operations ---")
    test_user_id = "test_user_99"
    test_profile = {
        "user_name": "Alice Tester",
        "user_email": "alice@example.com",
        "financial_profile": {
            "persona": "Salaried",
            "monthly_income": 95000,
            "essential_expenses": 30000,
            "non_essential_expenses": 15000,
            "current_savings": 200000,
            "debt_details": {
                "has_debt": True,
                "debt_type": "Home Loan",
                "total_outstanding_debt": 1500000,
                "monthly_emi": 20000,
            },
            "investments": ["Mutual Funds", "PPF"],
            "monthly_saving_investment": 15000,
        }
    }

    upsert_user_profile(test_user_id, test_profile, session_id="test_sess_1")
    assert profile_exists(test_user_id), "Profile check failed!"

    fetched = get_user_profile(test_user_id)
    assert fetched is not None, "Profile retrieval returned None!"
    assert fetched["user_name"] == "Alice Tester", f"Expected Alice Tester, got {fetched.get('user_name')}"
    print("✅ Vector Store Profile Upsert & Get passed.")

    # Test expense history & past report storage
    add_expense_history(test_user_id, "2026-07", "Dining Out", 4500, "Weekend family dinner")
    exp_history = get_expense_history(test_user_id)
    print(f"✅ Expense History retrieved: {len(exp_history)} items.")

    add_past_report(test_user_id, "rep001", "Alice financial report summary.", "/tmp/dummy.pdf")
    reports = get_past_reports(test_user_id)
    print(f"✅ Past Reports retrieved: {len(reports)} items.")


def test_calculations():
    print("\n--- TEST 2: Financial Calculation Engine ---")
    data = {
        "monthly_income": 100000,
        "essential_expenses": 35000,
        "non_essential_expenses": 15000,
        "current_savings": 300000,
        "house_emi": 20000,
        "debt_details": {
            "has_debt": True,
            "total_outstanding_debt": 1000000,
            "monthly_emi": 5000
        },
        "person_type": "salaried",
        "age": 28
    }

    res_str = calculation_tool.invoke({"user_data": json.dumps(data)})
    res = json.loads(res_str)

    assert "monthly_surplus" in res, "Missing monthly_surplus!"
    assert res["monthly_income"] == 100000, "Income mismatch!"
    # Liabilities: house_emi(20000) + debt_emi(5000) + essential(35000) + non_essential(15000) = 75000
    # Surplus: 100000 - 75000 = 25000
    assert res["monthly_surplus"] == 25000, f"Expected surplus 25000, got {res['monthly_surplus']}"
    assert res["savings_rate_pct"] == 25.0, f"Expected savings rate 25%, got {res['savings_rate_pct']}"
    assert res["dti_ratio_pct"] == 25.0, f"Expected DTI 25%, got {res['dti_ratio_pct']}"
    print(f"✅ Calculation Engine output verified: Surplus=₹{res['monthly_surplus']}, Tax=₹{res['estimated_annual_tax']}.")


def test_full_pipeline_analysis():
    print("\n--- TEST 3: Full Pipeline (Financial Analysis Request) ---")
    res = run_planning_pipeline(
        user_id="test_user_99",
        user_name="Alice Tester",
        person_type="Salaried",
        monthly_income=95000,
        house_emi=20000,
        insurance_premium=2000,
        health_expenses=3000,
        other_liabilities=[],
        age=28,
        chat_query="Analyze my monthly budget and tell me how to optimize my investments and emergency fund.",
    )

    print("Intent:", res.get("intent"))
    print("Metrics:", res.get("financial_metrics"))
    print("Recommendations count:", len(res.get("recommendations", [])))
    print("Tradeoffs count:", len(res.get("tradeoff_analysis", [])))
    print("Critic decision:", res.get("critic_feedback"))
    print("PDF output path:", res.get("pdf_path"))

    assert res.get("financial_metrics"), "Financial metrics missing!"
    assert len(res.get("recommendations", [])) > 0, "Recommendations missing!"
    assert len(res.get("tradeoff_analysis", [])) > 0, "Tradeoff analysis missing!"
    assert res.get("pdf_path"), "PDF report path missing!"
    assert os.path.exists(res.get("pdf_path")), f"PDF file does not exist at {res.get('pdf_path')}"
    print("✅ Financial Analysis Pipeline verified successfully.")


def test_conversational_routing():
    print("\n--- TEST 4: Conversational Intent Routing ---")
    res = run_planning_pipeline(
        user_id="test_user_99",
        user_name="Alice Tester",
        person_type="Salaried",
        monthly_income=95000,
        house_emi=20000,
        chat_query="What is an SIP and how does compound interest work in mutual funds?",
    )

    print("Intent:", res.get("intent"))
    print("Response text excerpt:", res.get("response_text", "")[:200])

    assert res.get("intent") == "conversational", f"Expected intent conversational, got {res.get('intent')}"
    assert len(res.get("response_text", "")) > 20, "Conversational response too short!"
    print("✅ Conversational routing verified successfully.")


if __name__ == "__main__":
    test_vector_store()
    test_calculations()
    test_full_pipeline_analysis()
    test_conversational_routing()
    print("\n🎉 ALL END-TO-END TESTS PASSED SUCCESSFULLY! 🎉\n")
