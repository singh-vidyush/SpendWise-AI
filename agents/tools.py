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
    Generate a structured PDF financial report with priority-coded recommendation
    cards, KPI summary row, charts, and trade-off comparison tables.
    """
    try:
        data = json.loads(report_data) if isinstance(report_data, str) else report_data
    except Exception:
        return "Error: Invalid JSON passed to pdf_report_tool"

    user_name   = data.get("user_name", "Valued Client")
    person_type = data.get("persona") or data.get("person_type", "Salaried")
    user_id     = str(data.get("user_id", "001"))
    report_id   = str(uuid.uuid4())[:8]
    filename    = f"financial_report_{user_name.replace(' ', '_')}_{report_id}.pdf"
    filepath    = os.path.join(PDF_OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=1.6*cm, rightMargin=1.6*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm
    )
    styles = getSampleStyleSheet()

    # ── Style palette ──────────────────────────────────────────────────────
    BRAND       = colors.HexColor("#FF6B00")
    DARK        = colors.HexColor("#111827")
    MID         = colors.HexColor("#374151")
    LIGHT_BG    = colors.HexColor("#F9FAFB")
    BORDER      = colors.HexColor("#E5E7EB")
    HIGH_COLOR  = colors.HexColor("#DC2626")   # red
    MED_COLOR   = colors.HexColor("#D97706")   # amber
    LOW_COLOR   = colors.HexColor("#16A34A")   # green
    CAT_COLORS  = {
        "savings":    colors.HexColor("#0EA5E9"),
        "investment": colors.HexColor("#8B5CF6"),
        "debt":       colors.HexColor("#EF4444"),
        "insurance":  colors.HexColor("#F59E0B"),
        "tax":        colors.HexColor("#10B981"),
        "emergency":  colors.HexColor("#6366F1"),
    }
    CAT_ICONS = {
        "savings": "💰", "investment": "📈", "debt": "💳",
        "insurance": "🛡", "tax": "🧾", "emergency": "🚨",
    }

    def _h(text, level=2):
        sz = {1: 15, 2: 12, 3: 10}[level]
        return Paragraph(text, ParagraphStyle(
            f"H{level}", parent=styles["Heading2"], fontSize=sz,
            textColor=DARK, spaceBefore=10, spaceAfter=4,
            borderPad=0,
        ))

    def _body(text):
        return Paragraph(text, ParagraphStyle(
            "B", parent=styles["BodyText"], fontSize=9.2,
            leading=13, textColor=MID, spaceAfter=3,
        ))

    def _divider():
        tbl = Table([[""]], colWidths=[17*cm])
        tbl.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.6, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl

    story = []

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1 — Cover header
    # ══════════════════════════════════════════════════════════════════════
    cover = Table(
        [[
            Paragraph(
                f"<font color='#FF6B00'><b>SpendWise</b></font> Personal Financial Report",
                ParagraphStyle("Cover", fontSize=18, leading=22, textColor=DARK)
            ),
            Paragraph(
                f"<font color='#6B7280'>{user_name} · {person_type.title()} · "
                f"{datetime.now().strftime('%d %b %Y')}</font>",
                ParagraphStyle("CoverSub", fontSize=9, leading=12, textColor=MID, alignment=2)
            )
        ]],
        colWidths=[11*cm, 6*cm]
    )
    cover.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, BRAND),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(cover)
    story.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2 — KPI Cards row
    # ══════════════════════════════════════════════════════════════════════
    calc = _parse_flex_data(data.get("metrics") or data.get("calculations", {}))
    if isinstance(calc, dict) and calc:
        story.append(_h("Financial Snapshot", 2))
        kpi_fields = [
            ("Monthly Income",   f"₹{calc.get('monthly_income',0):,.0f}",   "#0EA5E9"),
            ("Monthly Surplus",  f"₹{calc.get('monthly_surplus',0):,.0f}",  "#16A34A"),
            ("Savings Rate",     f"{calc.get('savings_rate_pct',0):.1f}%",   "#8B5CF6"),
            ("DTI Ratio",        f"{calc.get('dti_ratio_pct',0):.1f}%",      "#EF4444"),
            ("Rec. SIP/month",   f"₹{calc.get('recommended_monthly_sip',0):,.0f}", "#F59E0B"),
            ("Emergency Fund",   f"₹{calc.get('emergency_fund_target',0):,.0f}", "#6366F1"),
        ]
        kpi_cells = []
        for label, value, hex_col in kpi_fields:
            cell = Table(
                [[Paragraph(f"<b><font color='{hex_col}'>{value}</font></b>",
                            ParagraphStyle("KV", fontSize=11, leading=13, alignment=1))],
                 [Paragraph(f"<font color='#6B7280'>{label}</font>",
                            ParagraphStyle("KL", fontSize=7.5, leading=10, alignment=1))]],
                colWidths=[2.7*cm]
            )
            cell.setStyle(TableStyle([
                ("BOX",            (0,0), (-1,-1), 0.5, colors.HexColor(hex_col)),
                ("BACKGROUND",     (0,0), (-1,-1), colors.HexColor("#FAFAFA")),
                ("TOPPADDING",     (0,0), (-1,-1), 5),
                ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
                ("LEFTPADDING",    (0,0), (-1,-1), 3),
                ("RIGHTPADDING",   (0,0), (-1,-1), 3),
            ]))
            kpi_cells.append(cell)

        kpi_row = Table([kpi_cells], colWidths=[2.83*cm]*6)
        kpi_row.setStyle(TableStyle([
            ("ALIGN",   (0,0), (-1,-1), "CENTER"),
            ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",  (0,0), (-1,-1), 2),
            ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ]))
        story.append(kpi_row)
        story.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3 — Executive Summary
    # ══════════════════════════════════════════════════════════════════════
    exec_summary = data.get("summary") or data.get("executive_summary", "")
    if not exec_summary and isinstance(calc, dict):
        exec_summary = (
            f"Financial analysis for {user_name}. Monthly income ₹{calc.get('monthly_income',0):,.0f} "
            f"with surplus ₹{calc.get('monthly_surplus',0):,.0f} "
            f"(Savings Rate: {calc.get('savings_rate_pct',0):.1f}%)."
        )
    if exec_summary:
        story.append(_divider())
        story.append(_h("Executive Summary", 2))
        story.append(_body(str(exec_summary)))
        story.append(Spacer(1, 0.3*cm))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4 — Charts (Pie + Bar side by side)
    # ══════════════════════════════════════════════════════════════════════
    if isinstance(calc, dict) and calc:
        story.append(_divider())
        story.append(_h("Portfolio Visualisation", 2))
        pie_path = os.path.join(PDF_OUTPUT_DIR, f"pie_{report_id}.png")
        bar_path = os.path.join(PDF_OUTPUT_DIR, f"bar_{report_id}.png")
        _generate_pie_chart(calc, pie_path)
        _generate_bar_chart(calc, bar_path)
        if os.path.exists(pie_path) and os.path.exists(bar_path):
            chart_tbl = Table(
                [[Image(pie_path, 8*cm, 6*cm), Image(bar_path, 9*cm, 6*cm)]],
                colWidths=[8.5*cm, 9*cm]
            )
            chart_tbl.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("ALIGN",  (0,0), (-1,-1), "CENTER"),
            ]))
            story.append(chart_tbl)
            story.append(Spacer(1, 0.3*cm))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 5 — Actionable Recommendations (priority-coded cards)
    # ══════════════════════════════════════════════════════════════════════
    recs = _parse_flex_data(
        data.get("structured_recs") or data.get("recommendations", [])
    )
    if recs:
        story.append(_divider())
        story.append(_h("Actionable Recommendations", 2))
        story.append(_body(
            "Recommendations are ranked by priority. Each card shows the action, "
            "expected impact, and suggested deadline."
        ))
        story.append(Spacer(1, 0.15*cm))

        PRIORITY_META = {
            "high":   ("HIGH",   HIGH_COLOR,  colors.HexColor("#FEF2F2")),
            "medium": ("MEDIUM", MED_COLOR,   colors.HexColor("#FFFBEB")),
            "low":    ("LOW",    LOW_COLOR,   colors.HexColor("#F0FDF4")),
        }

        def _rec_card(idx, rec):
            if not isinstance(rec, dict):
                rec = {"title": f"Recommendation {idx}", "action": str(rec),
                       "priority": "medium", "category": "savings",
                       "impact": "—", "deadline": "—", "rationale": ""}
            priority     = rec.get("priority", "medium").lower()
            category     = rec.get("category", "savings").lower()
            title        = rec.get("title", f"Action {idx}")
            action       = rec.get("action", "")
            impact       = rec.get("impact", "")
            deadline     = rec.get("deadline", "")
            rationale    = rec.get("rationale", "")

            p_label, p_color, p_bg = PRIORITY_META.get(priority, PRIORITY_META["medium"])
            cat_color = CAT_COLORS.get(category, colors.HexColor("#6B7280"))
            cat_icon  = CAT_ICONS.get(category, "●")

            # Header row: priority badge | title | category tag
            header = Table([[
                Paragraph(f"<b><font color='white'> {p_label} </font></b>",
                          ParagraphStyle("PBadge", fontSize=7, leading=9, alignment=1)),
                Paragraph(f"<b>{idx}. {title}</b>",
                          ParagraphStyle("RTitle", fontSize=10, leading=12, textColor=DARK)),
                Paragraph(f"<font color='white'><b> {cat_icon} {category.upper()} </b></font>",
                          ParagraphStyle("CBadge", fontSize=7, leading=9, alignment=2)),
            ]], colWidths=[1.5*cm, 12.5*cm, 2.5*cm])
            header.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (0,0), p_color),
                ("BACKGROUND",    (1,0), (1,0), p_bg),
                ("BACKGROUND",    (2,0), (2,0), cat_color),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ("TOPPADDING",    (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ]))

            # Body rows
            body_rows = []
            if action:
                body_rows.append([
                    Paragraph("<b>Action</b>",
                              ParagraphStyle("BL", fontSize=8.5, textColor=MID)),
                    Paragraph(action,
                              ParagraphStyle("BV", fontSize=8.5, leading=12, textColor=DARK)),
                ])
            if impact:
                body_rows.append([
                    Paragraph("<b>Impact</b>",
                              ParagraphStyle("BL", fontSize=8.5, textColor=MID)),
                    Paragraph(f"<font color='#16A34A'><b>{impact}</b></font>",
                              ParagraphStyle("BV", fontSize=8.5, textColor=DARK)),
                ])
            if deadline:
                body_rows.append([
                    Paragraph("<b>Deadline</b>",
                              ParagraphStyle("BL", fontSize=8.5, textColor=MID)),
                    Paragraph(deadline,
                              ParagraphStyle("BV", fontSize=8.5, textColor=DARK)),
                ])
            if rationale:
                body_rows.append([
                    Paragraph("<i>Why</i>",
                              ParagraphStyle("BL", fontSize=8, textColor=colors.HexColor("#9CA3AF"))),
                    Paragraph(f"<i>{rationale}</i>",
                              ParagraphStyle("BV", fontSize=8, leading=11,
                                             textColor=colors.HexColor("#6B7280"))),
                ])

            body_tbl = Table(body_rows, colWidths=[2*cm, 14.5*cm])
            body_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), p_bg),
                ("TOPPADDING",    (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                ("LINEBELOW",     (0,0), (-1,-2), 0.3, BORDER),
            ]))

            outer = Table([[header], [body_tbl]], colWidths=[16.5*cm])
            outer.setStyle(TableStyle([
                ("BOX",           (0,0), (-1,-1), 0.8, p_color),
                ("LEFTPADDING",   (0,0), (-1,-1), 0),
                ("RIGHTPADDING",  (0,0), (-1,-1), 0),
                ("TOPPADDING",    (0,0), (-1,-1), 0),
                ("BOTTOMPADDING", (0,0), (-1,-1), 0),
            ]))
            return KeepTogether([outer, Spacer(1, 0.25*cm)])

        # Sort: high → medium → low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        if isinstance(recs, list) and recs and isinstance(recs[0], dict):
            recs_sorted = sorted(
                recs,
                key=lambda r: priority_order.get(r.get("priority", "medium").lower(), 1)
            )
        else:
            recs_sorted = recs if isinstance(recs, list) else [recs]

        for i, rec in enumerate(recs_sorted, 1):
            story.append(_rec_card(i, rec))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 6 — Trade-off Comparison Tables
    # ══════════════════════════════════════════════════════════════════════
    tradeoffs = _parse_flex_data(data.get("tradeoffs") or data.get("tradeoff_analysis", []))
    if tradeoffs and isinstance(tradeoffs, list) and tradeoffs:
        story.append(_divider())
        story.append(_h("Strategic Trade-off Analysis", 2))
        story.append(_body(
            "For each recommendation, two alternative strategies are compared. "
            "The recommended option is highlighted."
        ))
        story.append(Spacer(1, 0.15*cm))

        for t in tradeoffs:
            if not isinstance(t, dict):
                continue
            for_rec = t.get("for_recommendation", "Recommendation")
            sa = t.get("strategy_a", {})
            sb = t.get("strategy_b", {})
            recommended = t.get("recommended", "a").lower()
            reason = t.get("reason", "")

            story.append(KeepTogether([
                _body(f"<b>↳ {for_rec}</b>"),
                Table(
                    [
                        [
                            Paragraph("<b>Option</b>",   ParagraphStyle("TH", fontSize=8, textColor=colors.white)),
                            Paragraph("<b>Description</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white)),
                            Paragraph("<b>Monthly Cost</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white)),
                            Paragraph("<b>Benefit</b>",  ParagraphStyle("TH", fontSize=8, textColor=colors.white)),
                            Paragraph("<b>Risk</b>",     ParagraphStyle("TH", fontSize=8, textColor=colors.white)),
                        ],
                        [
                            Paragraph(f"{'✅ ' if recommended=='a' else ''}A: {sa.get('name','')}",
                                      ParagraphStyle("TC", fontSize=8, textColor=DARK,
                                                     backColor=colors.HexColor("#F0FDF4") if recommended=="a" else colors.white)),
                            Paragraph(sa.get("description",""), ParagraphStyle("TC", fontSize=8, leading=11)),
                            Paragraph(f"₹{sa.get('monthly_cost',0):,}", ParagraphStyle("TC", fontSize=8)),
                            Paragraph(sa.get("benefit",""),      ParagraphStyle("TC", fontSize=8, textColor=LOW_COLOR)),
                            Paragraph(sa.get("risk",""),         ParagraphStyle("TC", fontSize=8, textColor=HIGH_COLOR)),
                        ],
                        [
                            Paragraph(f"{'✅ ' if recommended=='b' else ''}B: {sb.get('name','')}",
                                      ParagraphStyle("TC", fontSize=8, textColor=DARK,
                                                     backColor=colors.HexColor("#F0FDF4") if recommended=="b" else colors.white)),
                            Paragraph(sb.get("description",""), ParagraphStyle("TC", fontSize=8, leading=11)),
                            Paragraph(f"₹{sb.get('monthly_cost',0):,}", ParagraphStyle("TC", fontSize=8)),
                            Paragraph(sb.get("benefit",""),      ParagraphStyle("TC", fontSize=8, textColor=LOW_COLOR)),
                            Paragraph(sb.get("risk",""),         ParagraphStyle("TC", fontSize=8, textColor=HIGH_COLOR)),
                        ],
                    ],
                    colWidths=[3.2*cm, 6*cm, 2.5*cm, 2.8*cm, 2*cm]
                ,
                style=TableStyle([
                    ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#374151")),
                    ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.HexColor("#F9FAFB"), colors.white]),
                    ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
                    ("FONTSIZE",      (0,0), (-1,-1), 8),
                    ("TOPPADDING",    (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("LEFTPADDING",   (0,0), (-1,-1), 5),
                ])),
                _body(f"<i>Recommended: Option {recommended.upper()} — {reason}</i>"),
                Spacer(1, 0.3*cm),
            ]))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 7 — Market Insights
    # ══════════════════════════════════════════════════════════════════════
    market = data.get("market_insights") or data.get("market_context", "")
    if market:
        story.append(_divider())
        story.append(_h("Market Insights", 2))
        story.append(_body(str(market)[:1200]))
        story.append(Spacer(1, 0.3*cm))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 8 — Disclaimer footer
    # ══════════════════════════════════════════════════════════════════════
    story.append(_divider())
    story.append(Paragraph(
        "<i>Disclaimer: This report is generated by SpendWise AI for informational purposes only. "
        "Please consult a SEBI-registered financial advisor before executing any investment strategy.</i>",
        ParagraphStyle("Footer", parent=styles["BodyText"], fontSize=7.5, textColor=colors.grey, leading=10)
    ))

    doc.build(story)

    # Store summary in past_reports ChromaDB collection
    if isinstance(calc, dict):
        summary_text = (
            f"Report for {user_name} ({person_type}). "
            f"Surplus: ₹{calc.get('monthly_surplus',0):,.0f}, "
            f"Savings: {calc.get('savings_rate_pct',0):.1f}%, "
            f"DTI: {calc.get('dti_ratio_pct',0):.1f}%."
        )
    else:
        summary_text = f"Report for {user_name} ({person_type})."
    add_past_report(
        user_id=user_id, report_id=report_id,
        summary=summary_text, filepath=filepath,
        metadata={"user_name": user_name, "person_type": person_type}
    )
    return filepath