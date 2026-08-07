"""
Script to generate a comprehensive technical documentation PDF for SpendWise-AI.
Covers system architecture, data flow, deep file-by-file analysis, agent state graph, 
design patterns, and technical explanations suitable for expert developers.
"""

import os
import sys
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib import colors
from reportlab.pdfgen import canvas

PDF_FILENAME = "SpendWise_AI_Complete_Technical_Guide.pdf"


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and display total page count.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#6B7280"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 800, "SpendWise-AI — System Architecture & Deep Codebase Guide")
            self.setStrokeColor(colors.HexColor("#E5E7EB"))
            self.setLineWidth(0.5)
            self.line(54, 792, 541, 792)
        
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(541, 36, page_str)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — SPENDWISE AI TECHNICAL SPECIFICATION")
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(54, 48, 541, 48)
        
        self.restoreState()


def create_pdf():
    pdf_path = os.path.join(os.path.dirname(__file__), PDF_FILENAME)
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.9 * cm,
        rightMargin=1.9 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm
    )

    styles = getSampleStyleSheet()

    # Color Palette
    PRIMARY = colors.HexColor("#FF6B00")
    DARK_BG = colors.HexColor("#111827")
    TEXT_MAIN = colors.HexColor("#1F2937")
    MUTED = colors.HexColor("#6B7280")
    ACCENT_BG = colors.HexColor("#FFF7F2")
    BORDER_COLOR = colors.HexColor("#E5E7EB")

    # Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        textColor=PRIMARY,
        alignment=0,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        textColor=MUTED,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontSize=15,
        leading=19,
        textColor=DARK_BG,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontSize=11.5,
        leading=15,
        textColor=PRIMARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["BodyText"],
        fontSize=9.2,
        leading=13.5,
        textColor=TEXT_MAIN,
        spaceAfter=5
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.2,
        leading=11,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    story = []

    # =========================================================================
    # TITLE & HEADER BANNER
    # =========================================================================
    story.append(Paragraph("SpendWise-AI Technical Architecture Guide", title_style))
    story.append(Paragraph(
        f"<b>Complete Codebase Specification, Data Flow Lifecycle & 10-Agent LangGraph Blueprint</b><br/>"
        f"Generated on {datetime.now().strftime('%B %d, %Y')} | Target Audience: Lead Architects & Senior Developers",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=0, spaceAfter=12))

    # =========================================================================
    # SECTION 1: EXECUTIVE SYSTEM OVERVIEW
    # =========================================================================
    story.append(Paragraph("1. Executive System Overview & Technology Stack", h1_style))
    story.append(Paragraph(
        "SpendWise-AI is an enterprise-grade personal finance planning platform engineered around an event-driven, "
        "multi-agent orchestration workflow using <b>LangGraph</b>, <b>FastAPI</b>, and <b>ChromaDB</b>. The application "
        "transforms unstructured user financial contexts into deterministic calculations, personalized recommendations, "
        "strategic trade-off analyses, and production-ready ReportLab PDF documents.",
        body_style
    ))

    # Tech Stack Table
    tech_data = [
        ["Layer / Category", "Technology Chosen", "Architecture Purpose"],
        ["Orchestration Engine", "LangGraph (StateGraph)", "Multi-agent graph control flow, conditional routing, critic feedback loops."],
        ["LLM Provider", "Google Gemini 3.1 Flash Lite", "ReAct planning, intent routing, reflection-based advisory generation."],
        ["Vector Database", "ChromaDB (Persistent)", "Semantic search across 5 distinct collections (user profiles, history, reports, etc.)."],
        ["Embeddings Engine", "HuggingFace MiniLM-L6-v2", "Local dense vector embeddings (384 dims) for fast semantic similarity."],
        ["Structured Storage", "SQLite / SQLAlchemy", "Relational persistence for user credentials, profiles, liabilities, and expense history."],
        ["Backend REST API", "FastAPI + Uvicorn", "Asynchronous endpoints for auth, profile persistence, and chat execution."],
        ["Frontend UI", "Streamlit", "Conversational onboarding wizard, interactive advisor chat, and KPI dashboard."],
        ["PDF Generation", "ReportLab Platypus", "Programmatic, dynamic PDF document synthesis with charts and key metric tables."]
    ]
    t_tech = Table(tech_data, colWidths=[3.8 * cm, 4.8 * cm, 9.5 * cm])
    t_tech.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ACCENT_BG]),
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 0.4 * cm))

    # =========================================================================
    # SECTION 2: END-TO-END DATA FLOW & STORAGE ARCHITECTURE
    # =========================================================================
    story.append(Paragraph("2. Data Lifecycle & Zero-Bypass Storage Architecture", h1_style))
    story.append(Paragraph(
        "A foundational architectural guarantee in SpendWise-AI is the <b>Zero-Bypass Profile Guarantee</b>. "
        "No financial query or planning logic can execute without first passing user profile JSON through "
        "<code>vector_store.py</code> for schema validation, normalization, and embedding generation.",
        body_style
    ))
    
    story.append(Paragraph("Data Flow Steps:", h2_style))
    flow_steps = [
        "<b>Step 1: Onboarding / Profile Submission</b> — User inputs profile details via Streamlit UI (Income, EMIs, Expenses, Savings, Debt, Investments).",
        "<b>Step 2: REST API Persistence</b> — Frontend calls <code>POST /save-profile</code> on FastAPI backend.",
        "<b>Step 3: Intake Agent Normalization</b> — <code>intake_agent</code> receives raw JSON, applies defaults for missing fields, and calls <code>upsert_user_profile()</code>.",
        "<b>Step 4: Dual Persistence (ChromaDB + SQLite)</b> — Profile is serialized, embedded via HuggingFace MiniLM, and stored in ChromaDB (<code>user_profiles</code> collection) with timestamp versioning. Structured entities are mirrored in SQLite.",
        "<b>Step 5: Intent Classification & Graph Execution</b> — User query triggers <code>intent_router</code>, which inspects query intent and routes to either <code>conversational_reply_agent</code> or the full <code>PLANNING_PIPELINE</code>.",
        "<b>Step 6: Output Synthesis & Past Report Storage</b> — PDF report is generated by <code>pdf_report_tool</code>, and its executive summary is indexed into ChromaDB's <code>past_reports</code> collection."
    ]
    for step in flow_steps:
        story.append(Paragraph(f"• {step}", bullet_style))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("ChromaDB 5-Collection Storage Architecture:", h2_style))
    col_data = [
        ["Collection Name", "Embedded Contents", "Key Metadata Fields", "Query Purpose"],
        ["user_profiles", "Normalized JSON user profile string", "user_id, session_id, version, timestamp", "User history & financial profile context"],
        ["expense_history", "Historical expense logs & notes", "user_id, month, category, amount", "Historical spending pattern analysis"],
        ["financial_knowledge", "79 text chunks from 6 domain docs", "source, topic, category", "Domain guidelines (tax, SIP, debt, insurance)"],
        ["market_data", "Tavily live web search snippets", "query, fetched_at, domain", "Live financial market rates & inflation context"],
        ["past_reports", "Summaries of prior PDF reports", "user_id, report_id, filepath, timestamp", "Cross-session report memory & tracking"]
    ]
    t_col = Table(col_data, colWidths=[3.2 * cm, 5.0 * cm, 4.8 * cm, 5.1 * cm])
    t_col.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ACCENT_BG]),
    ]))
    story.append(t_col)
    story.append(Spacer(1, 0.4 * cm))

    # =========================================================================
    # SECTION 3: FILE-BY-FILE DEEP DIVE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. Deep File-by-File Technical Codebase Analysis", h1_style))
    story.append(Paragraph(
        "This section provides an exhaustive description of every source file in the repository, detailing its exact responsibilities, "
        "internal functions, schemas, and integration points.",
        body_style
    ))

    files_info = [
        {
            "filename": "config.py",
            "purpose": "Global Environment & Directory Configuration",
            "details": [
                "<b>Key Exports:</b> <code>GEMINI_API_KEY</code>, <code>TAVILY_API_KEY</code>, <code>CHROMA_PERSIST_DIR</code>, <code>SQLITE_DB_PATH</code>, <code>PDF_OUTPUT_DIR</code>.",
                "<b>ChromaDB Constants:</b> Defines string constants for all 5 collections (<code>CHROMA_COLLECTION_USER_PROFILES</code>, <code>CHROMA_COLLECTION_EXPENSE_HISTORY</code>, etc.).",
                "<b>Directory Initialization:</b> Automatically ensures the <code>reports/</code> and <code>chroma_db/</code> directories exist on startup."
            ]
        },
        {
            "filename": "database.py",
            "purpose": "SQLite User Authentication & Credential Management",
            "details": [
                "<b>Database Name:</b> <code>spendwise_users.db</code>.",
                "<b>Key Functions:</b> <code>create_table()</code>, <code>hash_password()</code> (SHA-256), <code>add_user()</code>, <code>verify_user()</code>, <code>get_user_by_email()</code>.",
                "<b>Security:</b> Hashes passwords prior to insertion; enforces email uniqueness constraint; handles integrity exceptions safely."
            ]
        },
        {
            "filename": "db/models.py",
            "purpose": "SQLAlchemy Relational Data Models",
            "details": [
                "<b>Engine & Session:</b> Binds to <code>financial.db</code> via SQLAlchemy ORM.",
                "<b>Entities:</b> <code>UserProfile</code> (id, name, person_type, monthly_income, age), <code>Liability</code> (user_id, liability_type, amount, frequency), <code>ExpenseHistory</code> (user_id, month, category, amount).",
                "<b>Role:</b> Serves as exact structured numerical storage for math calculations, complementing ChromaDB's vector search."
            ]
        },
        {
            "filename": "db/vector_store.py",
            "purpose": "ChromaDB Interface, Embedding Engine & Normalization Layer",
            "details": [
                "<b>Embedding Engine:</b> Lazy initializes HuggingFace <code>sentence-transformers/all-MiniLM-L6-v2</code>.",
                "<b>Schema Normalization:</b> <code>normalize_user_profile(raw_dict)</code> sanitizes raw JSON, converting missing values to safe numerical/string defaults.",
                "<b>Collection Operations:</b> Provides <code>upsert_user_profile()</code>, <code>get_user_profile()</code>, <code>add_expense_history()</code>, <code>upsert_market_data()</code>, <code>add_past_report()</code>, and generic <code>query_collection()</code>."
            ]
        },
        {
            "filename": "rag.py",
            "purpose": "Knowledge Base Ingestion & Document Chunking Script",
            "details": [
                "<b>Source Documents:</b> Reads PDF, DOCX, and TXT files from <code>finance_knowledge_base/</code>.",
                "<b>Text Splitter:</b> Uses <code>RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)</code>.",
                "<b>Execution:</b> Ingests 79 text chunks across 6 domain documents into ChromaDB's <code>financial_knowledge</code> collection."
            ]
        },
        {
            "filename": "agents/tools.py",
            "purpose": "Deterministic Math, Search & PDF Generation Tools",
            "details": [
                "<b><code>calculation_tool</code>:</b> Computes Surplus, Savings Rate (%), DTI Ratio (%), EMI Burden Warning, Indian Tax (New Regime FY24-25 with Section 87A rebate), Net Worth, Emergency Fund Target (6 months), and SIP allocations.",
                "<b><code>tavily_search_tool</code>:</b> Fetches live market snippets using Tavily API and upserts results into <code>market_data</code> collection.",
                "<b><code>pdf_report_tool</code>:</b> Builds custom ReportLab PDFs featuring Executive Summary, Key Metrics Table, Recommendations, Strategic Trade-offs, and saves summary to <code>past_reports</code>."
            ]
        },
        {
            "filename": "agents/graph.py",
            "purpose": "LangGraph StateGraph Multi-Agent Architecture",
            "details": [
                "<b>State Schema:</b> <code>FinancialPlanningState</code> containing messages, profile, query, intent, retrieved_context, market_context, financial_metrics, recommendations, tradeoff_analysis, critic_feedback, revision_count, pdf_path, response_text.",
                "<b>10 Agents/Nodes:</b> <code>intake_agent</code>, <code>intent_router</code>, <code>conversational_reply_agent</code>, <code>rag_react_agent</code>, <code>market_react_agent</code>, <code>calculator_agent</code>, <code>recommendation_agent</code>, <code>trade_off_agent</code>, <code>critic_agent</code>, <code>report_agent</code>.",
                "<b>LLM Model:</b> Google <code>gemini-3.1-flash-lite</code>."
            ]
        },
        {
            "filename": "backend_app.py",
            "purpose": "FastAPI REST API Service",
            "details": [
                "<b>Endpoints:</b> <code>POST /signup</code>, <code>POST /login</code>, <code>POST /save-profile</code>, <code>GET /profile/{user_id}</code>, <code>POST /chat</code>.",
                "<b>CORS:</b> Configured with permissive CORS middleware for Streamlit frontend communication.",
                "<b>Orchestration:</b> <code>/chat</code> endpoint invokes <code>run_planning_pipeline()</code> and returns structured response JSON."
            ]
        },
        {
            "filename": "frontend_app.py",
            "purpose": "Streamlit User Interface & Conversational Onboarding Wizard",
            "details": [
                "<b>Routing & Pages:</b> <code>home</code>, <code>signup</code>, <code>login</code>, <code>chatbot</code>.",
                "<b>Onboarding Wizard:</b> 9-step structured questionnaire collecting persona, income, expenses, debt details, investments, and monthly savings.",
                "<b>UI Aesthetics:</b> Custom CSS tokens, modern typography, glassmorphism, responsive chat bubbles, and instant advisor Q&A."
            ]
        },
        {
            "filename": "test/test_end_to_end.py",
            "purpose": "Comprehensive Production Test Suite",
            "details": [
                "<b>Test 1: Vector Store:</b> Validates profile upsert, retrieval, expense history, and past report retrieval.",
                "<b>Test 2: Calculation Engine:</b> Validates financial math accuracy.",
                "<b>Test 3: Full Pipeline:</b> Executes end-to-end multi-agent graph and verifies PDF file generation.",
                "<b>Test 4: Intent Routing:</b> Verifies conversational queries route directly to <code>conversational_reply_agent</code>."
            ]
        }
    ]

    for f_info in files_info:
        story.append(Paragraph(f"📄 {f_info['filename']} — <i>{f_info['purpose']}</i>", h2_style))
        for detail in f_info["details"]:
            story.append(Paragraph(f"• {detail}", bullet_style))
        story.append(Spacer(1, 0.2 * cm))

    # =========================================================================
    # SECTION 4: THE 10-AGENT LANGGRAPH BLUEPRINT
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. The 10-Agent LangGraph Architecture & Design Patterns", h1_style))
    story.append(Paragraph(
        "The graph is constructed as a <code>StateGraph(FinancialPlanningState)</code> where every node receives the "
        "immutable current state and returns partial dict updates that LangGraph merges into the main state.",
        body_style
    ))

    # Graph Nodes Table
    agent_data = [
        ["#", "Node Name", "Design Pattern", "Core Responsibilities & Operations"],
        ["1", "intake_agent", "Ingestion Gatekeeper", "Validates raw JSON, applies defaults, normalizes profile, and upserts to ChromaDB."],
        ["2", "intent_router", "Classifier Router", "Analyzes prompt keywords & LLM output to classify intent into conversational, analysis, report, or follow_up."],
        ["3", "conversational_reply_agent", "Direct Q&A", "Answers general queries (e.g. 'What is SIP?') using RAG context without running full calculation pipeline."],
        ["4", "rag_react_agent", "ReAct Pattern", "Think (generate queries) → Act (search financial_knowledge & expense_history) → Observe (deduplicate)."],
        ["5", "market_react_agent", "ReAct Pattern", "Think (identify required market rates) → Act (invoke Tavily search tool) → Observe (upsert to market_data)."],
        ["6", "calculator_agent", "Deterministic Math", "Invokes calculation_tool to calculate surplus, DTI ratio, savings rate, tax estimation, and emergency fund gap."],
        ["7", "recommendation_agent", "Reflection Pattern", "Drafts 5 personalized financial actions → Reflects on surplus & feasibility → Refines recommendations."],
        ["8", "trade_off_agent", "Constraint Reasoning", "Generates strategic trade-off alternatives (e.g., Aggressive Debt Payoff vs Balanced SIP) with benefits/drawbacks."],
        ["9", "critic_agent", "Critic Loop (Max 2x)", "Validates outputs for contradictions or impossible math. Returns APPROVED or triggers advisor revision."],
        ["10", "report_agent", "Document Synthesizer", "Compiles report payload, invokes pdf_report_tool to build PDF, indexes summary to past_reports."]
    ]
    t_agent = Table(agent_data, colWidths=[0.8 * cm, 4.2 * cm, 3.8 * cm, 9.3 * cm])
    t_agent.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ACCENT_BG]),
    ]))
    story.append(t_agent)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Key Design Patterns Explained for Lead Developers:", h2_style))
    patterns = [
        "<b>1. ReAct Pattern (Reasoning + Acting)</b>: Used in RAG and Market agents. The LLM first <i>Thinks</i> about what information is missing, performs an <i>Action</i> (ChromaDB vector search or Tavily API web query), and <i>Observes</i> the retrieved snippets to assemble structured context.",
        "<b>2. Reflection Pattern</b>: Used in the Recommendation Agent. The LLM drafts an initial set of recommendations, reflects on whether they exceed monthly surplus or violate financial rules, and rewrites them before passing them down the pipeline.",
        "<b>3. Critic Loop (Self-Correction)</b>: Implemented between <code>critic_agent</code> and <code>recommendation_agent</code>. If the critic detects numerical contradictions or unreasonable advice, it returns structured guidance to trigger a revision cycle (capped at 2 iterations to prevent infinite loops).",
        "<b>4. Intent-Based Fast Path Routing</b>: Prevents unnecessary heavy calculations. If a user asks a general question like 'What is an emergency fund?', the intent router immediately routes to <code>conversational_reply_agent</code>, bypassing calculation and report generation."
    ]
    for p in patterns:
        story.append(Paragraph(f"• {p}", bullet_style))
    story.append(Spacer(1, 0.4 * cm))

    # =========================================================================
    # SECTION 5: HOW TO EXPLAIN THIS TO AN EXPERT DEVELOPER
    # =========================================================================
    story.append(Paragraph("5. Technical Pitch & Explanation Guide for Experts", h1_style))
    story.append(Paragraph(
        "When explaining this architecture to a Lead Developer, System Architect, or Engineering Manager, "
        "highlight the following architectural highlights:",
        body_style
    ))

    pitch_bullets = [
        "<b>Architectural Separation:</b> 'We strictly decouple non-deterministic reasoning (LLM recommendations & trade-offs) from deterministic financial math. Math is executed in a dedicated tool (<code>calculation_tool</code>), ensuring tax slabs and DTI ratios are 100% mathematically exact.'",
        "<b>State Management in LangGraph:</b> 'We use LangGraph's <code>StateGraph</code> with a strongly typed <code>FinancialPlanningState</code> dictionary. State mutations are explicit, preventing hidden state corruption between graph nodes.'",
        "<b>Zero-Bypass Persistence:</b> 'User profile data never bypasses storage. Every profile JSON submitted via Streamlit passes through the Intake Agent into ChromaDB and SQLite before any advisory node executes.'",
        "<b>Multi-Collection Vector Retrieval:</b> 'Instead of dumping everything into a single vector database index, we maintain 5 domain-isolated ChromaDB collections: profiles, expense history, domain knowledge, market data, and past reports.'",
        "<b>Self-Correcting Quality Control:</b> 'We implement a Critic Loop with a max-2 iteration budget. If the critic agent identifies financial infeasibility in recommended actions, it sends structured feedback back to the advisor agent for automatic revision.'"
    ]
    for bullet in pitch_bullets:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("<i>End of Technical Specification — SpendWise-AI Core Architecture Document</i>", ParagraphStyle("EndNote", parent=body_style, fontSize=8, textColor=MUTED, alignment=1)))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Generated Technical Guide PDF: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    create_pdf()
