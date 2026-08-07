# from agents.tools import calculation_tool
# import json

# data = {
#     "monthly_income": 80000,
#     "house_emi": 20000,
#     "insurance_premium": 3000,
#     "health_expenses": 2000,
#     "other_liabilities": [5000],
#     "person_type": "salaried",
#     "age": 25
# }

# result = calculation_tool.invoke(
#     {
#         "user_data": json.dumps(data)
#     }
# )

# print(result)

# from agents.tools import tavily_search_tool

# result = tavily_search_tool.invoke(
#     {
#         "query": "India inflation rate"
#     }
# )

# print(result)

# from agents.tools import rag_tool

# result = rag_tool.invoke(
#     {
#         "query": "What is a good emergency fund?"
#     }
# )

# print(result)

# from agents.tools import pdf_report_tool
# import json


# report = {

#     "user_name": "Deepak",

#     "person_type": "salaried",

#     "calculations": {
#         "monthly_income": 80000,
#         "total_monthly_liabilities": 30000,
#         "monthly_surplus": 50000,
#         "savings_rate_pct": 62.5,
#         "emi_to_income_ratio_pct": 25,
#         "estimated_annual_tax": 63500,
#         "emergency_fund_target": 180000,
#         "recommended_monthly_sip": 20000,
#         "recommended_monthly_savings": 10000
#     },

#     "recommendations": [
#         "Invest ₹20000 monthly through SIP",
#         "Build emergency fund of ₹180000"
#     ],

#     "market_insights": "Inflation is moderate",

#     "knowledge_snippets": [
#         "Emergency fund should cover 6 months of expenses"
#     ]
# }


# path = pdf_report_tool.invoke(
#     {
#         "report_data": json.dumps(report)
#     }
# )


# print(path)
from langchain_core.messages import HumanMessage

from agents.graph import run_planning_pipeline


result = run_planning_pipeline(
    user_id="001",
    user_name="Deepak",
    person_type="salaried",

    monthly_income=80000,
    house_emi=20000,
    insurance_premium=2000,
    health_expenses=3000,

    other_liabilities=[
        {
            "name": "Car Loan",
            "amount": 10000
        }
    ],

    age=24,

    chat_query=(
        "I earn 80000 per month. "
        "I have EMI and want to improve my savings "
        "and investment planning."
    ),

    chat_history=[]
)


print("\n========== FINAL STATE ==========\n")

print("Calculations:")
print(result.get("calculations"))

print("\nRecommendations:")
for r in result.get("recommendations", []):
    print("-", r)

print("\nCritic Feedback:")
print(result.get("critic_feedback"))

print("\nPDF:")
print(result.get("pdf_path"))

print("\nMessages:")
for msg in result.get("messages", []):
    print(type(msg).__name__, ":", msg.content)