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


from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.charts.barcharts import VerticalBarChart
from config import TAVILY_API_KEY, PDF_OUTPUT_DIR

from db.vector_store import add_past_report

logger = logging.getLogger(__name__)


@tool
def calculation_tool(user_data):
    """
Calculate financial metrics such as surplus, savings rate, DTI ratio, emergency fund target, and SIP recommendations.
"""
    data = json.loads(user_data)

    income = float(data.get("monthly_income", 0))
    expenses = (
        float(data.get("essential_expenses", 0))
        + float(data.get("non_essential_expenses", 0))
    )

    emi = float(data.get("house_emi", 0))
    savings = float(data.get("current_savings", 0))

    surplus = income - expenses - emi

    result = {
        "monthly_income": income,
        "monthly_surplus": surplus,
        "savings_rate_pct": (surplus / income * 100) if income else 0,
        "dti_ratio_pct": (emi / income * 100) if income else 0,
        "recommended_monthly_sip": max(surplus * 0.4, 0),
        "emergency_fund_target": (expenses + emi) * 6,
    }

    return json.dumps(result)

@tool
def tavily_search_tool(query):
    """
    Search web for financial market information.
    """
    try:
        results = TavilyClient(
            api_key=TAVILY_API_KEY
        ).search(query=query, max_results=3)

        context = "\n".join(
            r["content"]
            for r in results.get("results", [])
        )

        return context

    except Exception as e:
        return str(e)


PDF_OUTPUT_DIR = "reports"
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

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
    print(filepath)
    return filepath