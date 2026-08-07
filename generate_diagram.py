"""
Generates the agent pipeline architecture diagram as a PNG.
Uses mermaid.ink API (no Node.js required).
Output: financial_goals_planner/agent_pipeline.png
"""
import base64
import os
import urllib.request
import urllib.error

MERMAID_DEFINITION = """
flowchart TD
    UI([Streamlit UI\\nProfile Form + Chat])

    UI -->|JSON profile| API([FastAPI Backend])
    API -->|raw JSON| IA[intake_agent\\nValidate · Normalize · Save]
    IA -->|upsert| VDB[(ChromaDB\\nuser_profiles)]
    IA -->|save| SQ[(SQLite\\nspendwise_users.db)]
    IA --> IR[intent_router]

    subgraph PIPELINE [LangGraph Multi-Agent Architecture]
        IR -->|conversational| CR[conversational_reply_agent\\nLLM + Chat History + RAG]

        subgraph PLANNING_FLOW [Financial Planning Pipeline]
            subgraph REACT [ReAct Pattern]
                RR[rag_react_agent\\nThink: targets?\\nAct: ChromaDB query\\nObserve: deduplicate]
                MR[market_react_agent\\nThink: market info?\\nAct: Tavily search\\nObserve: market snippets]
            end

            IR -->|financial analysis / report| RR
            RR --> MR

            subgraph DET [Deterministic Calculations]
                CA[calculator_agent\\nSurplus · Savings Rate · DTI\\nTax · Net Worth · Emergency Fund]
            end

            MR --> CA

            subgraph REF [Reflection Pattern]
                AD[recommendation_agent\\nDRAFT: 5 recommendations\\nREFLECT: affordable & feasible?]
            end

            CA --> AD

            subgraph TRADE [Trade-off Analysis]
                TA[trade_off_agent\\nAlternatives · Impact\\nBenefits · Drawbacks]
            end

            AD --> TA

            subgraph CRIT [Critic Review Loop - max 2x]
                CK{critic_agent\\nAPPROVED?}
            end

            TA --> CK
            CK -->|APPROVED| RP[report_agent\\nGenerate PDF Report\\nPrepare Dashboard Data]
            CK -->|critique + guidance| AD
        end
    end

    CR --> CHAT([Conversational Response])
    RP -->|PDF| DL([Download PDF Report])
    RP -->|summary| VDB2[(ChromaDB\\npast_reports)]
    RP --> DASH([Dashboard KPIs & Charts])

    subgraph VDB_GROUP [ChromaDB Collections]
        VDB
        VDB2
        KC[(financial_knowledge)]
        MD[(market_data)]
        EH[(expense_history)]
    end

    RR -->|reads| KC
    RR -->|reads| EH
    MR -->|writes + reads| MD

    style REACT fill:#EBF5FB,stroke:#2E86C1
    style DET  fill:#EAFAF1,stroke:#1E8449
    style REF  fill:#F4ECF7,stroke:#7D3C98
    style TRADE fill:#FEF9E7,stroke:#D4AC0D
    style CRIT fill:#FDEDEC,stroke:#CB4335
    style PIPELINE fill:#FDFEFE,stroke:#717D7E
    style VDB_GROUP fill:#F8F9FA,stroke:#AEB6BF
"""

def generate_png():
    # Encode for mermaid.ink
    encoded = base64.urlsafe_b64encode(MERMAID_DEFINITION.encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded}?type=png&width=1400"

    output_path = os.path.join(os.path.dirname(__file__), "agent_pipeline.png")

    print(f"Fetching diagram from mermaid.ink ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            png_data = response.read()

        with open(output_path, "wb") as f:
            f.write(png_data)

        size_kb = len(png_data) // 1024
        print(f"Saved: {output_path}  ({size_kb} KB)")
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code}: {e.reason}")
        print("Falling back to matplotlib diagram ...")
        _generate_matplotlib_fallback(output_path)
    except Exception as e:
        print(f"Error: {e}")
        print("Falling back to matplotlib diagram ...")
        _generate_matplotlib_fallback(output_path)


def _generate_matplotlib_fallback(output_path: str):
    """Simple matplotlib fallback diagram."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    fig, ax = plt.subplots(figsize=(18, 22))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 22)
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")

    def box(x, y, w, h, label, color, textcolor="black", fontsize=9, radius=0.3):
        rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                              boxstyle=f"round,pad=0.1,rounding_size={radius}",
                              facecolor=color, edgecolor="#555", linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=fontsize,
                color=textcolor, wrap=True, multialignment="center",
                fontfamily="monospace")

    def arrow(x1, y1, x2, y2, label="", color="#555"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.4))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx+0.15, my, label, fontsize=7.5, color="#333", style="italic")

    def subgraph_bg(x, y, w, h, title, color):
        rect = FancyBboxPatch((x, y), w, h,
                              boxstyle="round,pad=0.2",
                              facecolor=color, edgecolor="#AAA", linewidth=1,
                              linestyle="--", alpha=0.4)
        ax.add_patch(rect)
        ax.text(x + 0.15, y + h - 0.2, title, fontsize=8, color="#444",
                fontstyle="italic", fontweight="bold")

    # Title
    ax.text(9, 21.4, "Financial Goals Planner — Agent Pipeline",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#1a1a2e")

    # --- Nodes ---
    # UI
    box(9, 20.5, 4, 0.7, "Streamlit UI  (Profile Form + Chat)", "#D6EAF8", fontsize=9)

    # Databases
    box(2.5, 19.2, 2.8, 0.6, "SQLite\nUserProfile · Liability", "#D5F5E3", fontsize=8)
    box(6.0, 19.2, 2.8, 0.6, "ChromaDB\nuser_profiles", "#D5F5E3", fontsize=8)
    box(9.5, 19.2, 2.2, 0.6, "router\nintent_router", "#F8F9FA", fontsize=8)

    # Conversation
    box(14.5, 18.0, 2.8, 0.7, "conversational_reply\nLLM + history + prior calc", "#F4ECF7", fontsize=7.5)

    # ReAct
    subgraph_bg(5.5, 15.8, 6.5, 2.0, "ReAct Pattern", "#EBF5FB")
    box(7.0, 17.2, 3.0, 0.7, "rag_react_agent\nThink→Act→Observe\nTargeted ChromaDB queries", "#D6EAF8", fontsize=7.5)
    box(10.5, 17.2, 2.8, 0.7, "market_react_agent\nThink→Act→Observe\nTargeted Tavily searches", "#D6EAF8", fontsize=7.5)

    # Deterministic
    subgraph_bg(5.5, 13.6, 6.5, 1.8, "Deterministic Math", "#EAFAF1")
    box(7.0, 14.8, 2.8, 0.7, "calculator_agent\nSurplus · Tax · EMI ratio", "#A9DFBF", fontsize=7.5)
    box(10.5, 14.8, 2.8, 0.7, "goals_agent\nFV=PV×1.06ⁿ  SIP/goal", "#A9DFBF", fontsize=7.5)

    # Trade-off
    subgraph_bg(5.5, 11.4, 6.5, 1.8, "Constraint-Aware Reasoning", "#FEF9E7")
    box(8.75, 12.3, 5.8, 0.9,
        "trade_off_agent\nvehicle→2nd-hand/CNG  education→public college  home→smaller city\nGenerates 2 alternatives + recalculated SIPs per shortfall goal",
        "#FAD7A0", fontsize=7.5)

    # Reflection
    subgraph_bg(5.5, 9.2, 6.5, 1.8, "Reflection Pattern", "#F4ECF7")
    box(8.75, 10.1, 5.8, 0.9,
        "advisor_agent\nDRAFT (with trade-offs) → REFLECT (specific? feasible? named ₹?) → FINALISE",
        "#D7BDE2", fontsize=7.5)

    # Critic
    subgraph_bg(5.5, 7.0, 6.5, 1.8, "Critic Loop (max 2×)", "#FDEDEC")
    box(8.75, 7.9, 5.8, 0.9,
        "critic_agent\nCheck: impossible amounts? vague? contradictions? infeasible goals unaddressed?\nAPPROVED  or  critique + revised_guidance → back to advisor",
        "#F1948A", fontsize=7.5)

    # Report
    box(8.75, 5.8, 5.8, 1.0,
        "report_agent  →  PDF\nFinancial summary · Goals table · Trade-off alternatives · Recommendations",
        "#D5F5E3", fontsize=8)

    # ChromaDB collections
    subgraph_bg(0.2, 4.5, 4.2, 6.0, "ChromaDB Collections", "#F8F9FA")
    box(2.3, 9.9, 3.2, 0.6, "financial_knowledge\nTax·SIP·Debt·Inflation·Goals", "#D5F5E3", fontsize=7.5)
    box(2.3, 9.0, 3.2, 0.5, "expense_history", "#D5F5E3", fontsize=7.5)
    box(2.3, 8.2, 3.2, 0.5, "market_data  (Tavily)", "#D5F5E3", fontsize=7.5)
    box(2.3, 7.4, 3.2, 0.5, "user_profiles", "#D5F5E3", fontsize=7.5)
    box(2.3, 6.6, 3.2, 0.5, "past_reports", "#D5F5E3", fontsize=7.5)

    # Outputs
    box(14.5, 5.8, 2.8, 0.6, "Dashboard\nPie · Goals chart · Trade-offs", "#FDEBD0", fontsize=8)
    box(14.5, 4.8, 2.8, 0.5, "Download PDF", "#FDEBD0", fontsize=8)

    # --- Arrows ---
    arrow(9, 20.15, 2.5, 19.5, "save")
    arrow(9, 20.15, 6.0, 19.5, "embed")
    arrow(9, 20.15, 9.5, 19.5, "query")
    arrow(9.5, 18.9, 14.5, 18.35, "follow-up")
    arrow(9.5, 18.9, 7.0, 17.55, "plan")
    arrow(7.0, 16.85, 10.5, 16.85)
    arrow(10.5, 16.85, 10.5, 15.15)
    arrow(10.5, 15.15, 7.0, 15.15)
    arrow(7.0, 14.45, 7.0, 12.75)
    arrow(10.5, 14.45, 10.5, 12.75)
    arrow(8.75, 11.85, 8.75, 10.55)
    arrow(8.75, 9.65, 8.75, 8.35)
    arrow(8.75, 7.45, 8.75, 6.3, "APPROVED")
    arrow(11.65, 7.9, 11.65, 10.1, "critique")
    arrow(8.75, 5.3, 14.5, 6.1)
    arrow(8.75, 5.3, 14.5, 5.05)
    arrow(8.75, 5.3, 2.3, 6.85, "summary")
    arrow(7.0, 16.85, 2.3, 9.6, "reads", "#2E86C1")
    arrow(10.5, 16.85, 2.3, 8.5, "writes/reads", "#2E86C1")

    # Legend
    legend_items = [
        ("#D6EAF8", "ReAct"),
        ("#A9DFBF", "Deterministic"),
        ("#FAD7A0", "Constraint-Aware Reasoning"),
        ("#D7BDE2", "Reflection"),
        ("#F1948A", "Critic"),
    ]
    for i, (color, label) in enumerate(legend_items):
        rect = FancyBboxPatch((0.3 + i*3.5, 0.3), 0.35, 0.35,
                              boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="#555")
        ax.add_patch(rect)
        ax.text(0.75 + i*3.5, 0.47, label, fontsize=8, va="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"Saved (matplotlib fallback): {output_path}")


if __name__ == "__main__":
    generate_png()
