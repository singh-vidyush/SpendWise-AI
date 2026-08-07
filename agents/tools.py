"""
LangGraph agent tools:
1. rag_tool             – query ChromaDB collections
2. calculation_tool     – financial math (surplus, savings rate, tax estimate)
3. tavily_search_tool   – live market data via Tavily
4. pdf_report_tool      – generate PDF report with ReportLab
"""
import json
import os
import uuid
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
    # past_reports_collection,
    upsert_market_data
    # add_past_report,
)

@tool
def rag_tool(query: str, collection_name: str = "financial_knowledge") -> str:
    """
    Retrieve relevant financial knowledge from ChromaDB.
    collection_name options:
    financial_knowledge | expense_history | market_data
    """
    collection_map = {
        "financial_knowledge": financial_knowledge_collection,
        "expense_history": expense_history_collection,
        "market_data": market_data_collection
        # "past_reports": past_reports_collection,
    }

    get_col = collection_map.get(
        collection_name,
        financial_knowledge_collection
    )

    docs = query_collection(
        get_col(),
        query,
        n_results=5
    )

    if not docs:
        return "No relevant documents found in the knowledge base."

    return "\n\n---\n\n".join(docs)


@tool
def calculation_tool(user_data: str) -> str:
    """
    Perform financial calculations.

    user_data JSON keys:
    monthly_income,
    house_emi,
    insurance_premium,
    health_expenses,
    other_liabilities,
    person_type,
    age
    """
    try:
        data = json.loads(user_data)
    except json.JSONDecodeError:
        return json.dumps(
            {"error": "Invalid JSON input to calculation_tool"}
        )

    income = float(data.get("monthly_income", 0))
    house_emi = float(data.get("house_emi", 0))
    insurance = float(data.get("insurance_premium", 0))
    health = float(data.get("health_expenses", 0))

    others = sum(
    float(x.get("amount", 0)) if isinstance(x, dict) else float(x)
    for x in data.get("other_liabilities", [])
)

    person_type = data.get("person_type", "salaried")

    total_liabilities = (
        house_emi +
        insurance +
        health +
        others
    )

    monthly_surplus = income - total_liabilities

    savings_rate = (
        monthly_surplus / income * 100
        if income > 0
        else 0
    )

    annual_income = income * 12

    tax = 0.0

    if person_type == "salaried":
        taxable = annual_income - 75000

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

        tax = max(tax, 0)

    emergency_fund_target = total_liabilities * 6

    recommended_sip = max(
        monthly_surplus * 0.40,
        0
    )

    recommended_savings = max(
        monthly_surplus * 0.20,
        0
    )

    emi_ratio = (
        house_emi / income * 100
        if income > 0
        else 0
    )

    result = {
        "monthly_income": income,
        "total_monthly_liabilities": round(total_liabilities, 2),
        "monthly_surplus": round(monthly_surplus, 2),
        "savings_rate_pct": round(savings_rate, 2),
        "annual_income": round(annual_income, 2),
        "estimated_annual_tax": round(tax, 2),
        "emi_to_income_ratio_pct": round(emi_ratio, 2),
        "emergency_fund_target": round(emergency_fund_target, 2),
        "recommended_monthly_sip": round(recommended_sip, 2),
        "recommended_monthly_savings": round(recommended_savings, 2),
        "health_status": (
            "healthy"
            if savings_rate >= 20
            else "needs_improvement"
        ),
        "emi_warning": emi_ratio > 40,
    }

    return json.dumps(
        result,
        indent=2
    )

@tool
def tavily_search_tool(query: str) -> str:
    """
    Search the web for current financial market data,
    interest rates, inflation figures, or investment news.
    """
    if not TAVILY_API_KEY:
        return "Tavily API key not configured. Skipping web search."

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)

        results = client.search(
            query=query,
            max_results=3
        )

        snippets = []

        for result in results.get("results", []):
            snippet = (
                f"**{result.get('title', '')}**\n"
                f"{result.get('content', '')}"
            )
            snippets.append(snippet)

        combined = (
            "\n\n".join(snippets)
            if snippets
            else "No results found."
        )

        doc_id = (
            f"market_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_"
            f"{query[:20].replace(' ','_')}"
        )

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
        return f"Tavily search failed: {exc}"

def generate_financial_chart(calc):

    income = calc.get(
        "monthly_income",
        0
    )

    liabilities = calc.get(
        "total_monthly_liabilities",
        0
    )

    savings = calc.get(
        "monthly_surplus",
        0
    )


    chart_path = os.path.join(
        PDF_OUTPUT_DIR,
        "financial_distribution.png"
    )


    plt.figure(figsize=(6,4))

    plt.bar(
        ["Income", "Liabilities", "Savings"],
        [
            income,
            liabilities,
            savings
        ]
    )

    plt.title(
        "Monthly Financial Distribution"
    )

    plt.ylabel(
        "Amount (₹)"
    )

    plt.tight_layout()

    plt.savefig(
        chart_path,
        dpi=300
    )

    plt.close()


    return chart_path

@tool
def pdf_report_tool(report_data: str) -> str:
    """
    Generate a financial planning PDF report.

    report_data JSON keys:
    user_name,
    person_type,
    calculations,
    recommendations,
    market_insights,
    knowledge_snippets

    Returns generated PDF file path.
    """
    try:
        data = json.loads(report_data)

    except json.JSONDecodeError:
        return "Error: Invalid JSON passed to pdf_report_tool"

    report_id = str(uuid.uuid4())[:8]

    filename = (
        f"financial_report_"
        f"{data.get('user_name','user').replace(' ','_')}_"
        f"{report_id}.pdf"
    )

    filepath = os.path.join(
        PDF_OUTPUT_DIR,
        filename
    )

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=13,
        spaceAfter=6
    )

    body_style = styles["BodyText"]
    body_style.spaceAfter = 4

    story = []

    story.append(
        Paragraph(
            "Personal Financial Planning Report",
            title_style
        )
    )

    story.append(
        Paragraph(
            f"Prepared for: <b>{data.get('user_name','N/A')}</b>",
            body_style
        )
    )

    story.append(
        Paragraph(
            f"Profile Type: <b>{data.get('person_type','N/A').title()}</b>",
            body_style
        )
    )

    story.append(
        Paragraph(
            f"Generated on: {datetime.now().strftime('%d %B %Y, %H:%M')}",
            body_style
        )
    )

    story.append(
        Spacer(
            1,
            0.5 * cm
        )
    )

    calc = data.get(
        "calculations",
        {}
    )

    if calc:
        story.append(
            Paragraph(
                "Financial Summary",
                h2_style
            )
        )
        # Financial Health Score

        income = calc.get("monthly_income",0)
        surplus = calc.get("monthly_surplus",0)
        emi_ratio = calc.get("emi_to_income_ratio_pct",0)

        score = 0


        if calc.get("savings_rate_pct",0) >= 30:
            score += 40
        else:
            score += 25


        if emi_ratio < 30:
            score += 30
        else:
            score += 15


        if calc.get("emergency_fund_target",0) > 0:
            score += 30


        story.append(
            Paragraph(
                f"Financial Health Score: {score}/100",
                h2_style
            )
        )


        status = (
            "Healthy"
            if score >=70
            else "Needs Improvement"
        )


        story.append(
            Paragraph(
                f"Overall Status: <b>{status}</b>",
                body_style
            )
        )
        drawing = Drawing(300,200)

        pie = Pie()
        pie.x = 50
        pie.y = 20
        pie.width = 120
        pie.height = 120

        pie.data = [
            calc.get("total_monthly_liabilities",0),
            calc.get("recommended_monthly_sip",0),
            calc.get("recommended_monthly_savings",0),
            calc.get("monthly_surplus",0)
        ]

        pie.labels = [
            "Liabilities",
            "Investments",
            "Savings",
            "Remaining"
        ]

        drawing.add(pie)

        story.append(
            Paragraph(
                "Expense Distribution",
                h2_style
            )
        )

        story.append(drawing)

        table_data = [
            ["Metric", "Value"],
            [
                "Monthly Income",
                f"₹{calc.get('monthly_income',0):,.2f}"
            ],
            [
                "Total Monthly Liabilities",
                f"₹{calc.get('total_monthly_liabilities',0):,.2f}"
            ],
            [
                "Monthly Surplus",
                f"₹{calc.get('monthly_surplus',0):,.2f}"
            ],
            [
                "Savings Rate",
                f"{calc.get('savings_rate_pct',0):.1f}%"
            ],
            [
                "EMI-to-Income Ratio",
                f"{calc.get('emi_to_income_ratio_pct',0):.1f}%"
            ],
            [
                "Estimated Annual Tax",
                f"₹{calc.get('estimated_annual_tax',0):,.2f}"
            ],
            [
                "Emergency Fund Target",
                f"₹{calc.get('emergency_fund_target',0):,.2f}"
            ],
            [
                "Recommended Monthly SIP",
                f"₹{calc.get('recommended_monthly_sip',0):,.2f}"
            ],
            [
                "Recommended Monthly Savings",
                f"₹{calc.get('recommended_monthly_savings',0):,.2f}"
            ],
        ]

        table = Table(
            table_data,
            colWidths=[
                9 * cm,
                7 * cm
            ]
        )

        table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0,0),
                    (-1,0),
                    colors.HexColor("#2E4057")
                ),
                (
                    "TEXTCOLOR",
                    (0,0),
                    (-1,0),
                    colors.white
                ),
                (
                    "FONTNAME",
                    (0,0),
                    (-1,0),
                    "Helvetica-Bold"
                ),
                (
                    "GRID",
                    (0,0),
                    (-1,-1),
                    0.5,
                    colors.HexColor("#CCCCCC")
                ),
                (
                    "FONTSIZE",
                    (0,0),
                    (-1,-1),
                    10
                ),
                (
                    "PADDING",
                    (0,0),
                    (-1,-1),
                    6
                ),
            ])
        )

        story.append(table)

        story.append(
            Spacer(
                1,
                0.4 * cm
            )
        )

        health = calc.get(
            "health_status",
            ""
        )

        emi_warn = calc.get(
            "emi_warning",
            False
        )

        if health == "needs_improvement":
            story.append(
                Paragraph(
                    "⚠ Savings rate is below 20%. Consider reducing discretionary expenses.",
                    body_style
                )
            )

        if emi_warn:
            story.append(
                Paragraph(
                    "⚠ EMI-to-income ratio exceeds 40%. Debt burden is high.",
                    body_style
                )
            )
        recommendations = data.get(
    "recommendations",
        []
)

    if recommendations:
        story.append(
            Paragraph(
                "Personalized Recommendations",
                h2_style
            )
        )

        for i, rec in enumerate(recommendations, 1):

            if isinstance(rec, dict):
                text = rec.get(
                    "recommendation",
                    ""
                )
            else:
                text = str(rec)

            story.append(
                Paragraph(
                    f"{i}. {text}",
                    body_style
                )
            )

        story.append(
            Spacer(
                1,
                0.4 * cm
            )
        )

    market_insights = data.get(
        "market_insights",
        ""
    )

    if market_insights:
        story.append(
            Paragraph(
                "Current Market Insights",
                h2_style
            )
        )

        story.append(
            Paragraph(
                market_insights[:1500],
                body_style
            )
        )

        story.append(
            Spacer(
                1,
                0.4 * cm
            )
        )

    snippets = data.get(
        "knowledge_snippets",
        []
    )

    if snippets:
        story.append(
            Paragraph(
                "Financial Guidelines Applied",
                h2_style
            )
        )

        for snippet in snippets[:3]:
            story.append(
                Paragraph(
                    f"• {snippet[:300]}",
                    body_style
                )
            )

    story.append(
        Spacer(
            1,
            0.5 * cm
        )
    )
    story.append(
    Paragraph(
        "AI Agent Workflow Summary",
        h2_style
    )
)

    workflow = """
    RAG Agent:
    Retrieved financial knowledge using ChromaDB.

    Market Agent:
    Collected current market information.

    Calculator Agent:
    Performed financial calculations.

    Advisor Agent:
    Generated personalized recommendations.

    Critic Agent:
    Validated recommendations.

    Report Agent:
    Generated this PDF report.
    """

    story.append(
        Paragraph(
            workflow.replace("\n","<br/>"),
            body_style
        )
    )
    story.append(
        Paragraph(
            "<i>Disclaimer: This report is AI-generated for informational purposes only. "
            "Consult a SEBI-registered financial advisor before making investment decisions.</i>",
            ParagraphStyle(
                "Footer",
                parent=body_style,
                fontSize=8,
                textColor=colors.grey
            )
        )
    )

    doc.build(story)

    rec_text = []

    for rec in recommendations[:2]:

        if isinstance(rec, dict):
            rec_text.append(
                rec.get(
                    "recommendation",
                    str(rec)
                )
            )

        else:
            rec_text.append(str(rec))


    summary = (
        f"Report for {data.get('user_name')} "
        f"({data.get('person_type')}). "
        f"Surplus: ₹{calc.get('monthly_surplus',0):,.0f}/month. "
        f"Savings rate: {calc.get('savings_rate_pct',0):.1f}%. "
        f"Recommendations: {'; '.join(rec_text)}"
    )

    # add_past_report(
    #     report_id,
    #     summary,
    #     {
    #         "user_name": data.get("user_name", ""),
    #         "person_type": data.get("person_type", ""),
    #         "generated_at": datetime.utcnow().isoformat(),
    #         "filepath": filepath
    #     }
    # )

    return filepath