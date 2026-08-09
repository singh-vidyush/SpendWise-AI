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


import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

PDF_OUTPUT_DIR = "reports"
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


def _generate_pie_chart(calc_data: dict, filepath: str):
    try:
        income = float(calc_data.get("monthly_income", 0))
        emi = float(calc_data.get("house_emi", 0) or calc_data.get("total_monthly_emis", 0))
        surplus = float(calc_data.get("monthly_surplus", 0))
        expenses = float(calc_data.get("essential_expenses", 0) + calc_data.get("non_essential_expenses", 0))

        if expenses == 0 and income > 0:
            expenses = max(income - emi - surplus, 0)

        labels = []
        sizes = []
        colors_list = []

        if expenses > 0:
            labels.append("Expenses")
            sizes.append(expenses)
            colors_list.append("#FF6B00")
        if emi > 0:
            labels.append("EMI / Debt")
            sizes.append(emi)
            colors_list.append("#3B82F6")
        if surplus > 0:
            labels.append("Savings / Surplus")
            sizes.append(surplus)
            colors_list.append("#10B981")

        if not sizes or sum(sizes) == 0:
            labels = ["Expenses", "EMI", "Surplus"]
            sizes = [50, 20, 30]
            colors_list = ["#FF6B00", "#3B82F6", "#10B981"]

        fig, ax = plt.subplots(figsize=(4.2, 3.2))
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors_list,
            autopct='%1.1f%%',
            startangle=140,
            textprops=dict(color="#111827", fontsize=8)
        )
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_weight('bold')

        ax.set_title("Income Allocation", fontsize=10, fontweight='bold', color='#111827', pad=10)
        plt.tight_layout()
        plt.savefig(filepath, dpi=200, bbox_inches='tight')
        plt.close(fig)
    except Exception as e:
        logger.error(f"Error generating pie chart: {e}")


def _generate_bar_chart(calc_data: dict, filepath: str):
    try:
        income = float(calc_data.get("monthly_income", 0))
        expenses = float(calc_data.get("essential_expenses", 0) + calc_data.get("non_essential_expenses", 0))
        emi = float(calc_data.get("house_emi", 0) or calc_data.get("total_monthly_emis", 0))
        if expenses == 0 and income > 0:
            expenses = max(income - emi - float(calc_data.get("monthly_surplus", 0)), 0)
        surplus = float(calc_data.get("monthly_surplus", 0))
        emergency_target = float(calc_data.get("emergency_fund_target", 0))

        categories = ['Income', 'Expenses', 'EMI', 'Savings', 'Emergency Target']
        values = [income, expenses, emi, max(surplus, 0), emergency_target]
        bar_colors = ['#FF6B00', '#EF4444', '#F59E0B', '#10B981', '#6366F1']

        fig, ax = plt.subplots(figsize=(5.2, 3.2))
        bars = ax.bar(categories, values, color=bar_colors, width=0.55)

        ax.set_title("Financial Metrics Comparison (₹)", fontsize=10, fontweight='bold', color='#111827', pad=10)
        ax.set_ylabel("Amount (₹)", fontsize=8, color='#374151')
        plt.xticks(rotation=20, ha='right', fontsize=8)
        plt.yticks(fontsize=8)

        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(
                    f"₹{int(height):,}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=7, fontweight='bold'
                )

        plt.tight_layout()
        plt.savefig(filepath, dpi=200, bbox_inches='tight')
        plt.close(fig)
    except Exception as e:
        logger.error(f"Error generating bar chart: {e}")


def _parse_flex_data(val):
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.startswith("{") or val_str.startswith("["):
            try:
                return json.loads(val_str)
            except Exception:
                pass
    return val


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
    person_type = data.get("persona") or data.get("person_type", "Salaried")
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
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#555555"),
        spaceAfter=14
    )

    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=12.5,
        leading=15.5,
        textColor=colors.HexColor("#111827"),
        spaceBefore=10,
        spaceAfter=5
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

    # 1. Cover Section Banner
    story.append(Paragraph("SpendWise Personal Financial Report", title_style))
    story.append(Paragraph(
        f"Client Name: <b>{user_name}</b> | Persona: <b>{person_type.title()}</b> | Generated: <b>{datetime.now().strftime('%d %b %Y, %H:%M')}</b>",
        subtitle_style
    ))
    story.append(Spacer(1, 0.2 * cm))

    # 2. Executive Summary
    exec_summary = data.get("summary") or data.get("executive_summary", "")
    if not exec_summary:
        calc = _parse_flex_data(data.get("metrics") or data.get("calculations", {}))
        exec_summary = (
            f"Financial analysis for {user_name}. Monthly income is ₹{calc.get('monthly_income', 0):,.2f} "
            f"with a monthly surplus of ₹{calc.get('monthly_surplus', 0):,.2f} (Savings Rate: {calc.get('savings_rate_pct', 0):.1f}%)."
        )

    story.append(Paragraph("1. Executive Summary", h2_style))
    story.append(Paragraph(str(exec_summary), body_style))
    story.append(Spacer(1, 0.3 * cm))

    # 3. Financial Metrics Section
    calc = _parse_flex_data(data.get("metrics") or data.get("calculations", {}))
    if isinstance(calc, dict) and calc:
        story.append(Paragraph("2. Financial Metrics", h2_style))
        table_data = [
            ["Metric", "Value"],
            ["Monthly Income", f"₹{calc.get('monthly_income', 0):,.2f}"],
            ["Monthly Surplus", f"₹{calc.get('monthly_surplus', 0):,.2f}"],
            ["Savings Rate (%)", f"{calc.get('savings_rate_pct', 0):.1f}%"],
            ["Debt-to-Income (DTI) Ratio (%)", f"{calc.get('dti_ratio_pct', 0):.1f}%"],
            ["Recommended Monthly SIP", f"₹{calc.get('recommended_monthly_sip', 0):,.2f}"],
            ["Emergency Fund Target (6 Months)", f"₹{calc.get('emergency_fund_target', 0):,.2f}"],
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

    # 4. Recommendations Section
    recs = _parse_flex_data(data.get("recommendations", []))
    if recs:
        story.append(Paragraph("3. Recommendations", h2_style))
        if isinstance(recs, list):
            for i, rec in enumerate(recs, 1):
                text = rec.get("action", str(rec)) if isinstance(rec, dict) else str(rec)
                story.append(Paragraph(f"<b>{i}.</b> {text}", body_style))
        else:
            story.append(Paragraph(str(recs), body_style))
        story.append(Spacer(1, 0.3 * cm))

    # 5. Trade-Off Analysis Section
    tradeoffs = _parse_flex_data(data.get("tradeoffs") or data.get("tradeoff_analysis", []))
    if tradeoffs:
        story.append(Paragraph("4. Trade-Off Analysis", h2_style))
        if isinstance(tradeoffs, list):
            for i, item in enumerate(tradeoffs, 1):
                if isinstance(item, dict):
                    strategy = item.get("strategy", f"Strategy {i}")
                    benefits = item.get("benefits", "")
                    drawbacks = item.get("tradeoffs") or item.get("drawbacks", "")
                    story.append(Paragraph(f"<b>Strategy {i}: {strategy}</b>", body_style))
                    if benefits:
                        story.append(Paragraph(f"   • <i>Benefits:</i> {benefits}", body_style))
                    if drawbacks:
                        story.append(Paragraph(f"   • <i>Drawbacks / Trade-offs:</i> {drawbacks}", body_style))
                else:
                    story.append(Paragraph(f"• {item}", body_style))
        else:
            story.append(Paragraph(str(tradeoffs), body_style))
        story.append(Spacer(1, 0.3 * cm))

    # 6. Market Insights Section
    market = data.get("market_insights") or data.get("market_context", "")
    if market:
        story.append(Paragraph("5. Market Insights", h2_style))
        story.append(Paragraph(str(market)[:1000], body_style))
        story.append(Spacer(1, 0.3 * cm))

    # 7. Portfolio Visualization Section (Pie & Bar Charts)
    if isinstance(calc, dict) and calc:
        story.append(Paragraph("6. Portfolio Visualization Section", h2_style))
        pie_img_path = os.path.join(PDF_OUTPUT_DIR, f"chart_pie_{report_id}.png")
        bar_img_path = os.path.join(PDF_OUTPUT_DIR, f"chart_bar_{report_id}.png")

        _generate_pie_chart(calc, pie_img_path)
        _generate_bar_chart(calc, bar_img_path)

        if os.path.exists(pie_img_path) and os.path.exists(bar_img_path):
            pie_img = Image(pie_img_path, width=8.0 * cm, height=6.0 * cm)
            bar_img = Image(bar_img_path, width=9.0 * cm, height=6.0 * cm)

            charts_table = Table([[pie_img, bar_img]], colWidths=[8.5 * cm, 9.0 * cm])
            charts_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(charts_table)
            story.append(Spacer(1, 0.3 * cm))

    # 8. Closing Summary Section
    story.append(Paragraph("7. Closing Summary", h2_style))
    closing_text = (
        f"<b>Overall Financial Health & Key Observations:</b> {user_name}'s financial portfolio shows a strong surplus foundation. "
        f"Follow the recommended action items above to maintain high savings efficiency while optimizing long-term wealth growth."
    )
    story.append(Paragraph(closing_text, body_style))
    story.append(Spacer(1, 0.4 * cm))

    # 9. Disclaimer Section
    story.append(Paragraph(
        "<i>Disclaimer: This report is generated by SpendWise AI for informational purposes. "
        "Please consult a certified financial advisor before executing investment strategies.</i>",
        ParagraphStyle("Footer", parent=body_style, fontSize=7.5, textColor=colors.grey)
    ))

    doc.build(story)

    # Store summary in past_reports collection
    summary_text = (
        f"Report for {user_name} ({person_type}). Monthly Surplus: ₹{calc.get('monthly_surplus', 0):,.0f}, "
        f"Savings Rate: {calc.get('savings_rate_pct', 0):.1f}%, DTI: {calc.get('dti_ratio_pct', 0):.1f}%."
    )
    add_past_report(
        user_id=user_id,
        report_id=report_id,
        summary=summary_text,
        filepath=filepath,
        metadata={"user_name": user_name, "person_type": person_type}
    )

    return filepath