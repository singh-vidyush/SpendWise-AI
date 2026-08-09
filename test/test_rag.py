# # # # test_rag_node.py
# # # from agents.graph import rag_react_agent
# # # import json

# # # fake_state = {
# # #     "user_data_json": json.dumps({
# # #         "person_type": "Salaried",
# # #         "monthly_income": 80000,
# # #         "house_emi": 25000
# # #     })
# # # }

# # # result = rag_react_agent(fake_state)

# # # snippets = result["retrieved_context"]["knowledge_snippets"]
# # # print("Number of snippets:", len(snippets))
# # # print("Sample:", snippets[:2])

# # # # assertions
# # # assert isinstance(snippets, list), "snippets must be a list"
# # # assert len(snippets) <= 9, "should be ≤ 3 queries × 3 docs"
# # # assert len(snippets) > 0, "should retrieve something"
# # # print("✅ PASSED")
# # # test_market.py

# # from agents.graph import market_react_agent
# # fake_state = {"person_type": "Salaried"}
# # result = market_react_agent(fake_state)

# # print("market_context type:", type(result["market_context"]))

# # print("Preview:", result["market_context"][:300])

# # assert isinstance(result["market_context"], str)

# # assert len(result["market_context"]) > 0

# # print("✅ PASSED")

# # test_tavily_raw.py

# from agents.tools import tavily_search_tool # 👈 import from wherever it's defined


# # use the SAME kind of query your node generates

# q = "best tax saving investment options for salaried employees in india"

# raw = tavily_search_tool.invoke({"query": q})

# print("=" * 60)

# print("TYPE:", type(raw)) # 👈 dict? str? list?

# print("=" * 60)

# print("RAW REPR:")

# print(repr(raw)) # 👈 shows structure incl. keys/quotes
# print("=" * 60)

# # if it's a dict, show its keys — this tells you what to extract

# if isinstance(raw, dict):

#     print("KEYS:", list(raw.keys()))
# test_reco.py
from agents.graph import recommendation_agent
import json

fake_state = {
    "user_name": "Deepak",
    "person_type": "Salaried",
    "financial_metrics": {"monthly_surplus": 20000, "savings_rate_pct": 25, "dti": 0.31},
    "market_context": "ELSS returns strong in 2026...",
    "critic_feedback": "",
}

result = recommendation_agent(fake_state)
recs = result["recommendations"]

print("TYPE:", type(recs))
print("COUNT:", len(recs))
print("SAMPLE:", recs[0] if recs else "EMPTY")

assert isinstance(recs, list), "must be a list, not a string!"
assert len(recs) > 0, "should not be empty"
assert isinstance(recs[0], dict), "each rec should be an object"
print("✅ PASSED")