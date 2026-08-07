"""
LangGraph agent tools for SpendWise-AI:
1. rag_tool             – query ChromaDB collections
2. calculation_tool     – deterministic financial calculations (surplus, DTI, savings rate, tax, net worth)
3. tavily_search_tool   – live market data via Tavily (upserts to market_data collection)
4. pdf_report_tool      – generate structured PDF report with ReportLab & store summary in past_reports
"""

import json
import os
import uuid
import logging
from datetime import datetime
import matplotlib.pyplot as plt
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.colors import HexColor
from langchain_core.tools import tool
from tavily import TavilyClient
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from config import TAVILY_API_KEY, PDF_OUTPUT_DIR
from db.vector_store import (
    query_collection,
    financial_knowledge_collection,
    expense_history_collection,
    market_data_collection,
    past_reports_collection,
    upsert_market_data,
    add_past_report,
)

logger = logging.getLogger(__name__)


@tool
def rag_tool(query: str, collection_name: str = "financial_knowledge") -> str:
    """
    Retrieve relevant financial knowledge from ChromaDB.
    collection_name options: financial_knowledge | expense_history | market_data | past_reports
    """
    collection_map = {
        "financial_knowledge": financial_knowledge_collection,
        "expense_history": expense_history_collection,
        "market_data": market_data_collection,
        "past_reports": past_reports_collection,
    }

    get_col = collection_map.get(collection_name, financial_knowledge_collection)
    docs = query_collection(get_col(), query, n_results=5)

    if not docs:
        return "No relevant documents found in the knowledge base."

    return "\n\n---\n\n".join(docs)


@tool
def calculation_tool(user_data: str) -> str:
    """
    Perform complete financial calculations.

    user_data JSON keys:
    monthly_income, essential_expenses, non_essential_expenses, current_savings,
    house_emi, insurance_premium, health_expenses, other_liabilities, person_type, age, debt_details
    """
    try:
        data = json.loads(user_data) if isinstance(user_data, str) else user_data
    except Exception:
        return json.dumps({"error": "Invalid JSON input to calculation_tool"})

    income = float(data.get("monthly_income", 0))
    essential = float(data.get("essential_expenses", 0))
    non_essential = float(data.get("non_essential_expenses", 0))
    savings = float(data.get("current_savings", 0))

    # Debt details & EMIs
    house_emi = float(data.get("house_emi", 0))
    insurance = float(data.get("insurance_premium", 0))
    health = float(data.get("health_expenses", 0))

    debt_details = data.get("debt_details", {})
    if isinstance(debt_details, dict):
        additional_emi = float(debt_details.get("monthly_emi", 0))
        total_outstanding_debt = float(debt_details.get("total_outstanding_debt", 0))
    else:
        additional_emi = 0.0
        total_outstanding_debt = 0.0

    others_sum = sum(
        float(x.get("amount", 0)) if isinstance(x, dict) else float(x)
        for x in data.get("other_liabilities", [])
    )

    total_emis = house_emi + additional_emi + others_sum
    total_monthly_expenses = essential + non_essential + insurance + health
    total_liabilities_and_expenses = total_emis + total_monthly_expenses

    monthly_surplus = income - total_liabilities_and_expenses
    savings_rate = (monthly_surplus / income * 100) if income > 0 else 0.0
    dti_ratio = (total_emis / income * 100) if income > 0 else 0.0
    emi_ratio = dti_ratio

    # Annual Income & Tax Estimation (Indian New Tax Regime FY 2024-25)
    annual_income = income * 12
    person_type = str(data.get("person_type", "salaried")).lower()
    taxable = max(annual_income - (75000 if person_type == "salaried" else 0), 0)

    tax = 0.0
    if taxable > 1500000:
        tax = 150000 + (taxable - 1500000) * 0.30
    elif taxable > 1200000:
        tax = 90000 + (taxable - 1200000) * 0.20
    elif taxable > 1000000:
        tax = 60000 + (taxable - 1000000) * 0.15
    elif taxable > 700000:
        tax = 45000 + (taxable - 700000) * 0.10
    elif taxable > 300000:
        tax = (taxable - 300000) * 0.05

    # 87A rebate for income <= 7,00,000
    if taxable <= 700000:
        tax = 0.0

    # Net worth analysis (Savings - Outstanding Debt)
    net_worth = savings - total_outstanding_debt

    # Emergency fund target (6 months of essential expenses & EMIs)
    monthly_must_haves = essential + total_emis
    emergency_fund_target = monthly_must_haves * 6

    recommended_sip = max(monthly_surplus * 0.40, 0.0)
    recommended_savings = max(monthly_surplus * 0.20, 0.0)

    result = {
        "monthly_income": round(income, 2),
        "essential_expenses": round(essential, 2),
        "non_essential_expenses": round(non_essential, 2),
        "total_monthly_emis": round(total_emis, 2),
        "total_monthly_liabilities": round(total_liabilities_and_expenses, 2),
        "monthly_surplus": round(monthly_surplus, 2),
        "savings_rate_pct": round(savings_rate, 2),
        "dti_ratio_pct": round(dti_ratio, 2),
        "emi_to_income_ratio_pct": round(emi_ratio, 2),
        "annual_income": round(annual_income, 2),
        "estimated_annual_tax": round(tax, 2),
        "current_savings": round(savings, 2),
        "total_outstanding_debt": round(total_outstanding_debt, 2),
        "estimated_net_worth": round(net_worth, 2),
        "emergency_fund_target": round(emergency_fund_target, 2),
        "recommended_monthly_sip": round(recommended_sip, 2),
        "recommended_monthly_savings": round(recommended_savings, 2),
        "health_status": "healthy" if savings_rate >= 20 and dti_ratio < 40 else "needs_improvement",
        "emi_warning": dti_ratio > 40,
        "emergency_fund_gap": round(max(emergency_fund_target - savings, 0), 2),
    }

    return json.dumps(result, indent=2)


@tool
def tavily_search_tool(query: str) -> str:
    """
    Search web for market information, rates, inflation, or investment news.
    """
    if not TAVILY_API_KEY:
        return "Tavily API key not configured. Skipping web search."

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(query=query, max_results=3)

        snippets = []
        for result in results.get("results", []):
            snippet = f"**{result.get('title', '')}**\n{result.get('content', '')}"
            snippets.append(snippet)

        combined = "\n\n".join(snippets) if snippets else "No market results found."

        doc_id = f"market_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{query[:20].replace(' ','_')}"
        upsert_market_data(
            doc_id,
            combined,
            {
                "query": query,
                "fetched_at": datetime.utcnow().isoformat()
            }
        )
        return combined
    except Exception as exc:
        logger.error(f"Tavily search failed: {exc}")
        return f"Tavily search failed: {exc}"


@tool
def pdf_report_tool(report_data: str) -> str:
    """
    Generate a complete PDF financial report using ReportLab.
    Stores report summary in past_reports collection.
    """
    try:
        data = json.loads(report_data) if isinstance(report_data, str) else report_data
    except Exception:
        return "Error: Invalid JSON passed to pdf_report_tool"

    user_name = data.get("user_name", "Valued Client")
    person_type = data.get("person_type", "Salaried")
    user_id = str(data.get("user_id", "001"))

    report_id = str(uuid.uuid4())[:8]
    filename = f"financial_report_{user_name.replace(' ', '_')}_{report_id}.pdf"
    filepath = os.path.join(PDF_OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#FF6B00"),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#555555"),
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#111827"),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#374151"),
        spaceAfter=4
    )

    story = []

    # Title Banner
    story.append(Paragraph("SpendWise Personal Financial Report", title_style))
    story.append(Paragraph(
        f"Client Name: <b>{user_name}</b> | Profile: <b>{person_type.title()}</b> | Generated: <b>{datetime.now().strftime('%d %b %Y, %H:%M')}</b>",
        subtitle_style
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Executive Summary
    exec_summary = data.get("executive_summary", "")
    if not exec_summary:
        calc = data.get("calculations", {})
        exec_summary = (
            f"Financial analysis for {user_name}. Monthly income is ₹{calc.get('monthly_income', 0):,.2f} "
            f"with total liabilities and expenses of ₹{calc.get('total_monthly_liabilities', 0):,.2f}, leaving a monthly surplus of "
            f"₹{calc.get('monthly_surplus', 0):,.2f} (Savings Rate: {calc.get('savings_rate_pct', 0):.1f}%)."
        )

    story.append(Paragraph("1. Executive Summary", h2_style))
    story.append(Paragraph(exec_summary, body_style))
    story.append(Spacer(1, 0.3 * cm))

    # Financial Snapshot & Key Metrics
    calc = data.get("calculations", {})
    if calc:
        story.append(Paragraph("2. Financial Snapshot & Key Metrics", h2_style))
        table_data = [
            ["Metric", "Amount / Percentage"],
            ["Monthly Income", f"₹{calc.get('monthly_income', 0):,.2f}"],
            ["Essential & Non-Essential Expenses", f"₹{calc.get('essential_expenses', 0) + calc.get('non_essential_expenses', 0):,.2f}"],
            ["Monthly EMIs / Liabilities", f"₹{calc.get('total_monthly_emis', 0):,.2f}"],
            ["Monthly Surplus", f"₹{calc.get('monthly_surplus', 0):,.2f}"],
            ["Savings Rate (%)", f"{calc.get('savings_rate_pct', 0):.1f}%"],
            ["Debt-to-Income (DTI) Ratio (%)", f"{calc.get('dti_ratio_pct', 0):.1f}%"],
            ["Estimated Net Worth", f"₹{calc.get('estimated_net_worth', 0):,.2f}"],
            ["Estimated Annual Tax (New Regime)", f"₹{calc.get('estimated_annual_tax', 0):,.2f}"],
            ["Emergency Fund Target (6 Months)", f"₹{calc.get('emergency_fund_target', 0):,.2f}"],
            ["Recommended Monthly SIP", f"₹{calc.get('recommended_monthly_sip', 0):,.2f}"],
        ]

        table = Table(table_data, colWidths=[9.5 * cm, 7.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FF6B00")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.3 * cm))

    # Recommendations
    recs = data.get("recommendations", [])
    if recs:
        story.append(Paragraph("3. Recommended Actions", h2_style))
        for i, rec in enumerate(recs, 1):
            text = rec.get("action", str(rec)) if isinstance(rec, dict) else str(rec)
            story.append(Paragraph(f"<b>Action {i}:</b> {text}", body_style))
        story.append(Spacer(1, 0.3 * cm))

    # Trade-off Analysis
    tradeoffs = data.get("tradeoff_analysis", [])
    if tradeoffs:
        story.append(Paragraph("4. Strategic Trade-Off Analysis", h2_style))
        for i, item in enumerate(tradeoffs, 1):
            if isinstance(item, dict):
                strategy = item.get("strategy", f"Strategy {i}")
                benefits = item.get("benefits", "")
                tradeoff = item.get("tradeoffs", item.get("drawbacks", ""))
                story.append(Paragraph(f"<b>{i}. {strategy}</b>", body_style))
                if benefits:
                    story.append(Paragraph(f"   • <i>Benefits:</i> {benefits}", body_style))
                if tradeoff:
                    story.append(Paragraph(f"   • <i>Trade-offs:</i> {tradeoff}", body_style))
            else:
                story.append(Paragraph(f"• {item}", body_style))
        story.append(Spacer(1, 0.3 * cm))

    # Market & Guidelines Context
    market = data.get("market_insights", "")
    if market:
        story.append(Paragraph("5. Market Context & Outlook", h2_style))
        story.append(Paragraph(market[:800], body_style))
        story.append(Spacer(1, 0.3 * cm))

    # Disclaimer
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "<i>Disclaimer: This report is generated by SpendWise AI for informational purposes. "
        "Please consult a certified financial advisor before executing investment strategies.</i>",
        ParagraphStyle("Footer", parent=body_style, fontSize=7.5, textColor=colors.grey)
    ))

    doc.build(story)

    # Store summary in past_reports collection
    summary = (
        f"Report for {user_name} ({person_type}). Monthly Surplus: ₹{calc.get('monthly_surplus', 0):,.0f}, "
        f"Savings Rate: {calc.get('savings_rate_pct', 0):.1f}%, DTI: {calc.get('dti_ratio_pct', 0):.1f}%."
    )
    add_past_report(
        user_id=user_id,
        report_id=report_id,
        summary=summary,
        filepath=filepath,
        metadata={"user_name": user_name, "person_type": person_type}
    )

    return filepath