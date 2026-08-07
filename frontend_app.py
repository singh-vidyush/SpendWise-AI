import streamlit as st
import time
import re
import json
import html
import requests

# ============================================================
# SPENDWISE - COMPLETE STREAMLIT FRONTEND
# Landing -> Signup/Login -> Chat-style onboarding -> AI Advisor
# ============================================================

st.set_page_config(
    page_title="SpendWise",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "page": "home",
    "users": {},
    "current_user": None,
    "current_email": None,
    "financial_question": 0,
    "financial_answers": {},
    "chat_phase": "onboarding",   # onboarding | review | advisor
    "advisor_messages": [],
    "financial_profile_json": "",
    "investment_selection": [],
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


def go_to(page):
    st.session_state.page = page
    st.rerun()


def reset_chat():
    st.session_state.financial_question = 0
    st.session_state.financial_answers = {}
    st.session_state.chat_phase = "onboarding"
    st.session_state.advisor_messages = []
    st.session_state.financial_profile_json = ""
    st.session_state.investment_selection = []


def logout():
    st.session_state.current_user = None
    st.session_state.current_email = None
    reset_chat()
    go_to("home")


API_BASE_URL = "http://localhost:8000"

# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif; }

.stApp {
    background:
        radial-gradient(circle at 92% 8%, #FFE9D8 0%, transparent 27%),
        radial-gradient(circle at 8% 92%, #FFF1E6 0%, transparent 27%),
        #FFFBF8;
}

header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }

.block-container {
    padding-top: 1.1rem;
    padding-bottom: 3rem;
    max-width: 1250px;
}

/* ---------- Buttons ---------- */
.stButton > button {
    border-radius: 12px;
    min-height: 45px;
    font-weight: 650;
    border: 1px solid #F0D7C5;
    background: white;
    transition: all .18s ease;
}

.stButton > button:hover {
    border-color: #FF7A00;
    color: #E85D00;
    background: #FFF9F5;
    transform: translateY(-1px);
}

.stButton > button[kind="primary"] {
    border: none;
    color: white;
    background: linear-gradient(135deg,#FF7A00,#FF5C00);
    box-shadow: 0 7px 20px rgba(255,107,0,.20);
}

.stButton > button[kind="primary"]:hover {
    color: white;
    background: linear-gradient(135deg,#FF6900,#EB5200);
    box-shadow: 0 9px 25px rgba(255,107,0,.28);
}

/* Make option buttons feel like chat suggestion chips */
div[data-testid="stHorizontalBlock"] .stButton > button {
    white-space: normal;
}

/* ---------- Inputs ---------- */
.stTextInput input,
.stNumberInput input {
    border-radius: 12px !important;
    border: 1px solid #E5E7EB !important;
    background: #FFFFFF !important;
    min-height: 48px;
}

.stTextInput input:focus,
.stNumberInput input:focus {
    border-color: #FF7A00 !important;
    box-shadow: 0 0 0 2px rgba(255,122,0,.10) !important;
}

/* ---------- Chat shell ---------- */
.chat-shell {
    max-width: 860px;
    margin: 0 auto;
}

.chat-heading {
    text-align: center;
    margin: 16px 0 24px;
}

.chat-badge {
    display: inline-block;
    background: #FFF0E5;
    color: #FF6B00;
    padding: 7px 14px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .6px;
    margin-bottom: 10px;
}

.bot-row {
    display: flex;
    align-items: flex-start;
    gap: 11px;
    margin: 16px 0;
}

.bot-avatar {
    width: 42px;
    height: 42px;
    min-width: 42px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg,#FF7A00,#FF5C00);
    box-shadow: 0 7px 18px rgba(255,107,0,.20);
    font-size: 20px;
}

.bot-bubble {
    max-width: 690px;
    background: #FFFFFF;
    border: 1px solid #F0E4DA;
    border-radius: 5px 18px 18px 18px;
    padding: 15px 18px;
    box-shadow: 0 6px 22px rgba(80,45,20,.055);
    color: #374151;
    line-height: 1.62;
    font-size: 14px;
}

.bot-title {
    color: #111827;
    font-weight: 750;
    font-size: 15px;
    margin-bottom: 4px;
}

.bot-subtitle {
    color: #7B8190;
    font-size: 12.5px;
}

.user-row {
    display: flex;
    justify-content: flex-end;
    align-items: flex-start;
    gap: 9px;
    margin: 11px 0 18px;
}

.user-bubble {
    max-width: 560px;
    padding: 12px 17px;
    color: white;
    background: linear-gradient(135deg,#FF7A00,#FF5C00);
    border-radius: 18px 5px 18px 18px;
    box-shadow: 0 7px 18px rgba(255,107,0,.18);
    font-size: 14px;
    line-height: 1.5;
}

.user-avatar {
    width: 34px;
    height: 34px;
    min-width: 34px;
    border-radius: 50%;
    background: #FFF0E5;
    color: #FF6B00;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
}

.option-label {
    color: #9CA3AF;
    font-size: 10.5px;
    font-weight: 800;
    letter-spacing: .55px;
    margin: 7px 0 8px;
}

.helper-text {
    color: #9CA3AF;
    font-size: 11px;
    margin: 4px 0 10px;
}

.online-pill {
    margin-top: 6px;
    padding: 7px 12px;
    border-radius: 999px;
    background: #ECFDF3;
    color: #15803D;
    text-align: center;
    font-size: 11px;
    font-weight: 750;
}

.summary-card {
    background: white;
    border: 1px solid #F0E4DA;
    border-radius: 19px;
    padding: 19px 22px;
    margin: 9px 0 18px 53px;
    box-shadow: 0 8px 28px rgba(80,45,20,.06);
}

.summary-row {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    padding: 10px 0;
    border-bottom: 1px solid #F6EEE8;
}

.summary-row:last-child { border-bottom: none; }

.summary-label {
    color: #7B8190;
    font-size: 12.5px;
}

.summary-value {
    color: #111827;
    font-size: 12.5px;
    font-weight: 750;
    text-align: right;
}

.feature-card {
    background: white;
    border: 1px solid #F3E8DF;
    border-radius: 18px;
    padding: 25px;
    min-height: 180px;
    box-shadow: 0 8px 30px rgba(80,45,20,.05);
}

.soft-card {
    background: rgba(255,255,255,.72);
    border: 1px solid #F1E5DB;
    border-radius: 18px;
    padding: 17px;
    margin: 8px 0 16px 53px;
}

/* Streamlit progress */
.stProgress > div > div > div > div {
    background-color: #FF6B00;
}

@media (max-width: 768px) {
    .bot-bubble, .user-bubble { max-width: 82%; }
    .summary-card, .soft-card { margin-left: 0; }
    .summary-row { flex-direction: column; gap: 3px; }
    .summary-value { text-align: left; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# UI HELPERS
# ============================================================

def esc(value):
    return html.escape(str(value))


def format_money(value):
    try:
        return f"₹{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def logo():
    st.markdown("""
    <div style="font-size:27px;font-weight:800;color:#1F2937;padding-top:7px;">
        <span style="color:#FF6B00;">◉</span>
        Spend<span style="color:#FF6B00;">Wise</span>
    </div>
    """, unsafe_allow_html=True)


def bot_message(title, description=""):
    description_html = (
        f'<div class="bot-subtitle">{description}</div>'
        if description else ""
    )
    st.markdown(f"""
    <div class="bot-row">
        <div class="bot-avatar">🤖</div>
        <div class="bot-bubble">
            <div class="bot-title">{title}</div>
            {description_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def user_message(text):
    st.markdown(f"""
    <div class="user-row">
        <div class="user-bubble">{text}</div>
        <div class="user-avatar">👤</div>
    </div>
    """, unsafe_allow_html=True)


def navbar(status_text=None):
    c1, c2, c3, c4 = st.columns([3, 4, 2, 1.2])
    with c1:
        logo()
    with c3:
        if status_text:
            st.markdown(
                f'<div class="online-pill">● {esc(status_text)}</div>',
                unsafe_allow_html=True
            )
    with c4:
        if st.button("Logout", use_container_width=True, key=f"logout_{st.session_state.chat_phase}"):
            logout()

    st.markdown(
        '<hr style="border:none;border-top:1px solid #F1E7DF;margin-top:8px;">',
        unsafe_allow_html=True
    )


# ============================================================
# LANDING PAGE
# ============================================================

def home_page():
    nav_logo, empty, login_col, signup_col = st.columns([3, 6, 1.2, 1.3])

    with nav_logo:
        logo()

    with login_col:
        if st.button("Login", use_container_width=True, key="nav_login"):
            go_to("login")

    with signup_col:
        if st.button("Sign Up", type="primary", use_container_width=True, key="nav_signup"):
            go_to("signup")

    st.markdown("<br><br>", unsafe_allow_html=True)

    left, space, right = st.columns([5.2, .5, 4.3])

    with left:
        st.markdown("""
        <div style="display:inline-block;background:#FFF0E5;color:#FF6B00;padding:7px 14px;
                    border-radius:50px;font-size:12px;font-weight:750;margin-bottom:20px;">
            ✨ YOUR AI FINANCIAL COMPANION
        </div>

        <h1 style="font-size:58px;line-height:1.08;color:#111827;margin-bottom:20px;letter-spacing:-2px;">
            Make your money
            <span style="color:#FF6B00;">work smarter.</span>
        </h1>

        <p style="font-size:18px;line-height:1.7;color:#6B7280;max-width:570px;margin-bottom:25px;">
            SpendWise is an AI-powered financial advisor that learns your basic financial situation
            and helps you make smarter decisions about budgeting, expenses, savings, debt and investments.
        </p>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1.6, 1.7, 2])
        with c1:
            if st.button("Get Started →", type="primary", use_container_width=True, key="hero_start"):
                go_to("signup")
        with c2:
            if st.button("I have an account", use_container_width=True, key="hero_login"):
                go_to("login")

        st.markdown("""
        <div style="margin-top:28px;color:#ffffff;font-size:12px;">
            ✓ Personalized guidance &nbsp;&nbsp;
            ✓ Smarter budgeting &nbsp;&nbsp;
            ✓ AI-powered insights
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown("""
        
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown("""
        <div class="feature-card">
            <div style="font-size:29px;">💳</div>
            <h3 style="color:#111827;">Smart Budgeting</h3>
            <p style="color:#6B7280;line-height:1.6;">
                Understand your income and spending and get guidance for managing your monthly budget.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
        <div class="feature-card">
            <div style="font-size:29px;">📊</div>
            <h3 style="color:#111827;">Financial Context</h3>
            <p style="color:#6B7280;line-height:1.6;">
                SpendWise considers your savings, debt, expenses and investments before responding.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with f3:
        st.markdown("""
        <div class="feature-card">
            <div style="font-size:29px;">🤖</div>
            <h3 style="color:#111827;">AI Advisor</h3>
            <p style="color:#6B7280;line-height:1.6;">
                Ask natural-language questions and receive financial guidance through one continuous chat.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;color:#9CA3AF;font-size:11px;margin-top:55px;">
        © 2026 SpendWise • Your smarter financial companion
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# SIGNUP / LOGIN
# ============================================================

def signup_page():
    left, center, right = st.columns([2.8, 4.4, 2.8])

    with center:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:25px;">
            <div style="font-size:30px;font-weight:800;color:#1F2937;">
                <span style="color:#FF6B00;">◉</span>
                Spend<span style="color:#FF6B00;">Wise</span>
            </div>
            <h1 style="color:#111827;font-size:31px;margin-bottom:6px;">Create your account</h1>
            <p style="color:#6B7280;">Start making smarter financial decisions.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            name = st.text_input("Full Name", placeholder="Enter your full name", key="signup_name")
            email = st.text_input("Email Address", placeholder="you@example.com", key="signup_email")
            password = st.text_input("Password", type="password", placeholder="Create a password", key="signup_password")
            confirm = st.text_input("Confirm Password", type="password", placeholder="Enter your password again", key="signup_confirm")

            st.caption("Use at least 8 characters for your password.")

            if st.button("Create Account →", type="primary", use_container_width=True, key="signup_submit"):
                clean_email = email.strip().lower()

                if not name.strip():
                    st.error("Please enter your name.")
                elif not clean_email:
                    st.error("Please enter your email.")
                elif not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", clean_email):
                    st.error("Please enter a valid email address.")
                elif len(password) < 8:
                    st.error("Password must contain at least 8 characters.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif clean_email in st.session_state.users:
                    st.error("An account with this email already exists.")
                else:
                    response = requests.post(
                        f"{API_BASE_URL}/signup",
                        json={
                            "username": name.strip(),
                            "email": clean_email,
                            "password": password
                        }
                    )

                    data = response.json()
                    if data["success"]:

                        st.session_state.user_id = data["user_id"]

                        st.session_state.current_user = (
                            name.strip()
                        )

                        st.session_state.current_email = (
                            clean_email
                        )

                        reset_chat()

                        st.success(
                            "Account created successfully!"
                        )

                        time.sleep(0.5)

                        go_to("chatbot")

                    else:

                        st.error(data["message"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;color:#6B7280;font-size:13px;">Already have an account?</div>',
            unsafe_allow_html=True
        )

        if st.button("Login to SpendWise", use_container_width=True, key="signup_to_login"):
            go_to("login")
        if st.button("← Back to home", use_container_width=True, key="signup_home"):
            go_to("home")


def login_page():
    left, center, right = st.columns([2.8, 4.4, 2.8])

    with center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:25px;">
            <div style="font-size:30px;font-weight:800;color:#1F2937;">
                <span style="color:#FF6B00;">◉</span>
                Spend<span style="color:#FF6B00;">Wise</span>
            </div>
            <h1 style="color:#111827;font-size:31px;margin-bottom:6px;">Welcome back</h1>
            <p style="color:#6B7280;">Login to continue to SpendWise.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            email = st.text_input("Email Address", placeholder="you@example.com", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")

            if st.button("Login →", type="primary", use_container_width=True, key="login_submit"):
                clean_email = email.strip().lower()
                response = requests.post(
                    f"{API_BASE_URL}/login",
                    json={
                        "email": clean_email,
                        "password": password
                    }
                )

                data = response.json()

                if not data["success"]:

                    st.error(
                        data["message"]
                    )

                else:

                    st.session_state.user_id = (
                        data["user_id"]
                    )

                    st.session_state.current_user = (
                        data["username"]
                    )

                    st.session_state.current_email = (
                        clean_email
                    )

                    reset_chat()

                    st.success(
                        "Login successful!"
                    )

                    time.sleep(0.5)

                    if data["profile_exists"]:

                        st.session_state.chat_phase = "advisor"

                    else:

                        st.session_state.chat_phase = "onboarding"

                    go_to("chatbot")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;color:#6B7280;font-size:13px;">Don\'t have a SpendWise account?</div>',
            unsafe_allow_html=True
        )

        if st.button("Create an Account", use_container_width=True, key="login_to_signup"):
            go_to("signup")
        if st.button("← Back to home", use_container_width=True, key="login_home"):
            go_to("home")


# ============================================================
# CHAT ONBOARDING QUESTIONS
# Exactly 9 top-level questions. Q7 becomes conditional.
# ============================================================

QUESTIONS = [
    {
        "key": "persona",
        "title": "What best describes how you earn your income?",
        "description": "Choose the option that best matches your main source of income.",
        "type": "single_choice",
        "options": [
            ("💼 Salaried", "Salaried"),
            ("🏢 Business Owner", "Business Owner"),
            ("💻 Freelancer", "Freelancer"),
            ("💼 Salaried + Business", "Salaried + Business"),
        ],
    },
    {
        "key": "monthly_income",
        "title": "What is your average monthly income?",
        "description": "Pick a quick amount or enter your own approximate monthly income.",
        "type": "money",
        "quick": [25000, 50000, 75000, 100000],
        "quick_labels": ["₹25,000", "₹50,000", "₹75,000", "₹1,00,000"],
        "placeholder": "Enter another amount",
    },
    {
        "key": "essential_expenses",
        "title": "How much do you spend on essential expenses every month?",
        "description": "Include rent, groceries, utilities, transport, bills and other necessary expenses.",
        "type": "money",
        "quick": [10000, 20000, 30000, 40000],
        "quick_labels": ["₹10,000", "₹20,000", "₹30,000", "₹40,000"],
        "placeholder": "Enter another amount",
    },
    {
        "key": "non_essential_expenses",
        "title": "How much do you spend on non-essential things each month?",
        "description": "Think shopping, entertainment, eating out, subscriptions and similar spending.",
        "type": "money",
        "quick": [2000, 5000, 10000, 15000],
        "quick_labels": ["₹2,000", "₹5,000", "₹10,000", "₹15,000"],
        "placeholder": "Enter another amount",
    },
    {
        "key": "current_savings",
        "title": "How much money do you currently have in savings?",
        "description": "Pick a quick amount or enter an approximate savings balance.",
        "type": "money",
        "quick": [25000, 50000, 100000, 500000],
        "quick_labels": ["₹25,000", "₹50,000", "₹1,00,000", "₹5,00,000"],
        "placeholder": "Enter your savings amount",
    },
    {
        "key": "has_debt",
        "title": "Do you currently have any loans or debt?",
        "description": "This can include EMIs, credit-card balances, education loans, vehicle loans or other debt.",
        "type": "single_choice",
        "options": [
            ("✓ No debt", "No"),
            ("💳 Yes, I have debt", "Yes"),
        ],
    },
    {
        "key": "debt_details",
        "title": "Tell me a little about your current debt.",
        "description": "If you have debt, select its type and enter the outstanding amount and monthly EMI.",
        "type": "debt",
    },
    {
        "key": "investments",
        "title": "Where do you currently invest your money?",
        "description": "Select all that apply. You can also add another investment type.",
        "type": "investments",
        "options": [
            "Mutual Funds",
            "Stocks",
            "Fixed Deposits",
            "PPF",
            "NPS",
            "Gold",
            "Crypto",
            "Real Estate",
            "None",
        ],
    },
    {
        "key": "monthly_saving_investment",
        "title": "How much do you usually save or invest every month?",
        "description": "Last question 🎉 Pick a quick amount or enter what you normally set aside.",
        "type": "money",
        "quick": [2500, 5000, 10000, 20000],
        "quick_labels": ["₹2,500", "₹5,000", "₹10,000", "₹20,000"],
        "placeholder": "Enter another amount",
    },
]


DEBT_TYPES = [
    "Home Loan",
    "Vehicle Loan",
    "Credit Card",
    "Education Loan",
    "Personal Loan",
    "Other",
]


# ============================================================
# CHAT DATA HELPERS
# ============================================================

def answer_for_chat(question, answer):
    qtype = question["type"]

    if qtype == "money":
        return format_money(answer)

    if qtype == "single_choice":
        return esc(answer)

    if qtype == "debt":
        if not answer or answer.get("has_debt") is False:
            return "✓ No debt"

        debt_type = esc(answer.get("debt_type", "Debt"))
        total = format_money(answer.get("total_outstanding_debt", 0))
        emi = format_money(answer.get("monthly_emi", 0))
        return f"{debt_type}<br>Total debt: <b>{total}</b><br>Monthly EMI: <b>{emi}</b>"

    if qtype == "investments":
        return esc(", ".join(answer)) if answer else "None"

    return esc(answer)


def save_answer(key, value):
    st.session_state.financial_answers[key] = value

    if st.session_state.financial_question < len(QUESTIONS) - 1:
        st.session_state.financial_question += 1
        st.session_state.chat_phase = "onboarding"
    else:
        st.session_state.chat_phase = "review"

    print(st.session_state.financial_answers)
    st.rerun()


def back_one_question():
    if st.session_state.financial_question > 0:
        st.session_state.financial_question -= 1
        st.session_state.chat_phase = "onboarding"
        st.rerun()


def jump_to_question(index):
    st.session_state.financial_question = max(0, min(index, len(QUESTIONS) - 1))
    st.session_state.chat_phase = "onboarding"
    st.rerun()


def display_previous_qa():
    answers = st.session_state.financial_answers
    current = st.session_state.financial_question

    for i in range(current):
        q = QUESTIONS[i]
        if q["key"] in answers:
            bot_message(q["title"], q["description"])
            user_message(answer_for_chat(q, answers[q["key"]]))


# ============================================================
# PRE-POPULATED OPTION BUTTONS
# ============================================================

def render_single_choice(question, index):
    st.markdown('<div class="option-label">CHOOSE A QUICK REPLY</div>', unsafe_allow_html=True)

    options = question["options"]
    cols = st.columns(2)

    for i, (label, value) in enumerate(options):
        with cols[i % 2]:
            if st.button(
                label,
                use_container_width=True,
                key=f"choice_{question['key']}_{i}"
            ):
                save_answer(question["key"], value)

    if index > 0:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        b1, b2 = st.columns([1, 3])
        with b1:
            if st.button("← Back", use_container_width=True, key=f"back_choice_{index}"):
                back_one_question()


def render_money_question(question, index):
    st.markdown('<div class="option-label">QUICK AMOUNTS</div>', unsafe_allow_html=True)

    quick = question["quick"]
    labels = question["quick_labels"]
    cols = st.columns(len(quick))

    for i, amount in enumerate(quick):
        with cols[i]:
            if st.button(
                labels[i],
                use_container_width=True,
                key=f"quick_{question['key']}_{amount}"
            ):
                save_answer(question["key"], amount)

    st.markdown(
        '<div class="helper-text">Or enter your own amount below.</div>',
        unsafe_allow_html=True
    )

    previous = st.session_state.financial_answers.get(question["key"])
    default_value = int(previous) if isinstance(previous, (int, float)) else None

    custom_amount = st.number_input(
        "Custom amount",
        min_value=0,
        value=default_value,
        step=500,
        placeholder=question["placeholder"],
        label_visibility="collapsed",
        key=f"custom_{question['key']}_{index}"
    )

    b1, b2 = st.columns([1, 2])

    with b1:
        if index > 0:
            if st.button("← Back", use_container_width=True, key=f"back_money_{index}"):
                back_one_question()

    with b2:
        if st.button("Send ➤", type="primary", use_container_width=True, key=f"send_money_{index}"):
            if custom_amount is None:
                st.warning("Choose a quick amount or enter your own amount.")
            else:
                save_answer(question["key"], int(custom_amount))


def render_debt_question(question, index):
    has_debt = st.session_state.financial_answers.get("has_debt", "No")

    if has_debt == "No":
        bot_message(
            "You told me you don't currently have debt 👍",
            "I'll record your outstanding debt and monthly EMI as ₹0 and move on."
        )

        b1, b2 = st.columns([1, 2])
        with b1:
            if st.button("← Back", use_container_width=True, key="back_no_debt"):
                back_one_question()
        with b2:
            if st.button("Continue ➤", type="primary", use_container_width=True, key="skip_debt"):
                save_answer(
                    "debt_details",
                    {
                        "has_debt": False,
                        "debt_type": "None",
                        "total_outstanding_debt": 0,
                        "monthly_emi": 0,
                    }
                )
        return

    old = st.session_state.financial_answers.get("debt_details", {})
    old_type = old.get("debt_type") if isinstance(old, dict) else None

    st.markdown('<div class="option-label">DEBT TYPE</div>', unsafe_allow_html=True)

    selected_type = st.selectbox(
        "Debt type",
        ["Select debt type"] + DEBT_TYPES,
        index=(DEBT_TYPES.index(old_type) + 1) if old_type in DEBT_TYPES else 0,
        label_visibility="collapsed",
        key="debt_type_select"
    )

    c1, c2 = st.columns(2)

    with c1:
        total_debt = st.number_input(
            "Total outstanding debt",
            min_value=0,
            value=int(old.get("total_outstanding_debt", 0)) if isinstance(old, dict) else 0,
            step=1000,
            key="debt_total"
        )

    with c2:
        monthly_emi = st.number_input(
            "Monthly EMI / debt payment",
            min_value=0,
            value=int(old.get("monthly_emi", 0)) if isinstance(old, dict) else 0,
            step=500,
            key="debt_emi"
        )

    b1, b2 = st.columns([1, 2])

    with b1:
        if st.button("← Back", use_container_width=True, key="back_debt"):
            back_one_question()

    with b2:
        if st.button("Send ➤", type="primary", use_container_width=True, key="send_debt"):
            if selected_type == "Select debt type":
                st.warning("Please select your debt type.")
            elif total_debt <= 0:
                st.warning("Please enter your outstanding debt amount.")
            else:
                save_answer(
                    "debt_details",
                    {
                        "has_debt": True,
                        "debt_type": selected_type,
                        "total_outstanding_debt": int(total_debt),
                        "monthly_emi": int(monthly_emi),
                    }
                )


def render_investments(question, index):
    old = st.session_state.financial_answers.get("investments", [])

    st.markdown('<div class="option-label">SELECT ALL THAT APPLY</div>', unsafe_allow_html=True)

    selected = st.multiselect(
        "Investments",
        question["options"],
        default=[x for x in old if x in question["options"]],
        placeholder="Choose your investments...",
        label_visibility="collapsed",
        key="investment_picker"
    )

    st.markdown(
        '<div class="helper-text">You can choose more than one. If you do not invest, choose “None”.</div>',
        unsafe_allow_html=True
    )

    other = st.text_input(
        "Other investment",
        placeholder="Optional: e.g. Bonds, ETFs...",
        label_visibility="collapsed",
        key="other_investment"
    )

    b1, b2 = st.columns([1, 2])

    with b1:
        if st.button("← Back", use_container_width=True, key="back_investments"):
            back_one_question()

    with b2:
        if st.button("Continue ➤", type="primary", use_container_width=True, key="send_investments"):
            final = selected.copy()
            if other.strip():
                final.append(other.strip())

            if not final:
                st.warning("Please select at least one option or choose None.")
            elif "None" in final and len(final) > 1:
                st.warning("Choose either None or your investments, not both.")
            else:
                save_answer("investments", final)


# ============================================================
# ONBOARDING CHAT
# ============================================================

def onboarding_chat():
    name = esc(st.session_state.get("current_user", "there"))
    index = st.session_state.financial_question
    question = QUESTIONS[index]

    bot_message(
        f"Hi {name} 👋",
        "Before we start, I'll ask you 9 quick questions so I can understand your financial situation. "
        "Use Back anytime if you want to change an earlier answer."
    )

    display_previous_qa()

    p1, p2 = st.columns([8, 2])
    with p1:
        st.progress((index + 1) / len(QUESTIONS))
    with p2:
        st.markdown(
            f'<div style="text-align:right;color:#FF6B00;font-size:12px;font-weight:800;padding-top:5px;">'
            f'{index + 1} of {len(QUESTIONS)}</div>',
            unsafe_allow_html=True
        )

    bot_message(question["title"], question["description"])

    if question["type"] == "single_choice":
        render_single_choice(question, index)

    elif question["type"] == "money":
        render_money_question(question, index)

    elif question["type"] == "debt":
        render_debt_question(question, index)

    elif question["type"] == "investments":
        render_investments(question, index)


# ============================================================
# IN-CHAT REVIEW
# ============================================================

def summary_html():
    a = st.session_state.financial_answers
    debt = a.get("debt_details", {}) or {}
    investments = a.get("investments", [])
    investment_text = ", ".join(investments) if investments else "None"

    debt_value = (
        "No debt"
        if not debt.get("has_debt", False)
        else f"{esc(debt.get('debt_type', 'Debt'))} • {format_money(debt.get('total_outstanding_debt', 0))}"
    )

    rows = [
        ("Financial persona", esc(a.get("persona", "-"))),
        ("Monthly income", format_money(a.get("monthly_income", 0))),
        ("Essential expenses", format_money(a.get("essential_expenses", 0))),
        ("Non-essential expenses", format_money(a.get("non_essential_expenses", 0))),
        ("Current savings", format_money(a.get("current_savings", 0))),
        ("Debt", debt_value),
        ("Monthly EMI", format_money(debt.get("monthly_emi", 0))),
        ("Investments", esc(investment_text)),
        ("Monthly saving / investment", format_money(a.get("monthly_saving_investment", 0))),
    ]

    body = "".join(
        f"""
        <div class="summary-row">
            <div class="summary-label">{label}</div>
            <div class="summary-value">{value}</div>
        </div>
        """
        for label, value in rows
    )

    return f'<div class="summary-card">{body}</div>'


def review_chat():
    # Keep the full conversation visible.
    for q in QUESTIONS:
        if q["key"] in st.session_state.financial_answers:
            bot_message(q["title"], q["description"])
            user_message(answer_for_chat(q, st.session_state.financial_answers[q["key"]]))

    bot_message(
        "Perfect! 🎉 I've got a good understanding of your finances.",
        "Please check the summary below. You can edit your details before starting the AI advisor."
    )

    st.markdown(summary_html(), unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])

    with c1:
        if st.button("✏️ Edit Details", use_container_width=True, key="edit_profile"):
            jump_to_question(len(QUESTIONS) - 1)

    with c2:
        if st.button("✓ Everything Looks Good", type="primary", use_container_width=True, key="confirm_profile"):
            profile = {
                "user_name": st.session_state.current_user,
                "user_email": st.session_state.current_email,
                "financial_profile": st.session_state.financial_answers,
            }

            requests.post(
                f"{API_BASE_URL}/save-profile",
                json={
                    "user_id":
                    st.session_state.user_id,

                    "profile":
                    profile
                }
            )

            st.session_state.financial_profile_json = json.dumps(
                profile,
                indent=2,
                ensure_ascii=False
            )

            st.session_state.chat_phase = "advisor"
            st.rerun()


# ============================================================
# ADVISOR CHAT
# ============================================================
def advisor_response(question):

    print("Sending question:", question)

    response = requests.post(
        f"{API_BASE_URL}/chat",
        json={
            "user_id": st.session_state.user_id,
            "message": question
        }
    )

    print("Status Code:", response.status_code)
    print("Response:", response.text)

    # If backend crashed
    if response.status_code != 200:
        return f"Backend Error: {response.text}"

    data = response.json()

    print("Parsed Data:")
    print(data)

    # If API returned failure
    if not data.get("success", False):
        return data.get(
            "message",
            "Something went wrong."
        )

    answer = ""

    calculations = data.get(
        "calculations",
        {}
    )

    recommendations = data.get(
        "recommendations",
        []
    )

    market_insights = data.get(
        "market_insights",
        ""
    )

    if calculations:

        answer += "📊 Financial Analysis\n\n"

        for key, value in calculations.items():
            answer += f"• {key}: {value}\n"

        answer += "\n"

    if recommendations:

        answer += "✅ Recommendations\n\n"

        for i, rec in enumerate(recommendations,start=1):

            # Gemini returned structured content
            if isinstance(rec, dict):

                rec_text = rec.get(
                    "text",
                    str(rec)
                )

            else:

                rec_text = str(rec)

            answer += f". {rec_text}\n"

        answer += "\n"

    if market_insights:

        answer += (
            "🌍 Market Insights\n\n"
        )

        answer += market_insights[:1000]

    return answer



def submit_advisor_question(question):
    if not question or not question.strip():
        return

    clean = question.strip()

    st.session_state.advisor_messages.append({
        "role": "user",
        "content": clean
    })

    response = advisor_response(clean)

    st.session_state.advisor_messages.append({
        "role": "assistant",
        "content": response
    })

    st.rerun()


def advisor_chat():
    name = esc(st.session_state.get("current_user", "there"))

    # The confirmation is shown as part of the same conversation.
    user_message("✓ Everything looks good")

    bot_message(
        f"Awesome, {name}! Your financial profile is ready. 💰",
        "I'm now your SpendWise AI financial advisor. Ask me about budgeting, spending, savings, debt, "
        "investments or general financial decisions."
    )

    st.markdown('<div class="option-label">TRY ASKING</div>', unsafe_allow_html=True)

    q1, q2 = st.columns(2)
    q3, q4 = st.columns(2)

    with q1:
        if st.button("💰 Analyze my budget", use_container_width=True, key="advisor_budget"):
            submit_advisor_question("Analyze my current budget.")

    with q2:
        if st.button("📉 Where am I overspending?", use_container_width=True, key="advisor_spending"):
            submit_advisor_question("Based on my financial profile, where might I be overspending?")

    with q3:
        if st.button("🏦 How much should I save?", use_container_width=True, key="advisor_saving"):
            submit_advisor_question("How much should I try to save every month?")

    with q4:
        if st.button("💳 Should I clear debt first?", use_container_width=True, key="advisor_debt"):
            submit_advisor_question("Should I prioritize clearing my debt before investing more?")

    st.markdown("<br>", unsafe_allow_html=True)

    for message in st.session_state.advisor_messages:
        if message["role"] == "user":
            user_message(esc(message["content"]))
        else:
            bot_message(esc(message["content"]))

    prompt = st.chat_input("Ask SpendWise anything about your finances...")

    if prompt:
        submit_advisor_question(prompt)


# ============================================================
# MAIN CHATBOT PAGE
# ============================================================

def chatbot_page():
    status = "AI Advisor Online" if st.session_state.chat_phase == "advisor" else "Secure Financial Setup"
    navbar(status)

    left, center, right = st.columns([1.1, 7.8, 1.1])

    with center:
        st.markdown("""
        <div class="chat-heading">
            <div class="chat-badge">SPENDWISE AI ADVISOR</div>
            <h2 style="color:#111827;margin-bottom:6px;">Your financial conversation</h2>
            <p style="color:#6B7280;font-size:13px;">
                One simple conversation — from understanding your finances to personalized AI guidance.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.chat_phase == "onboarding":
            onboarding_chat()

        elif st.session_state.chat_phase == "review":
            review_chat()

        elif st.session_state.chat_phase == "advisor":
            advisor_chat()


# ============================================================
# ROUTER
# ============================================================

if st.session_state.page == "home":
    home_page()

elif st.session_state.page == "signup":
    signup_page()

elif st.session_state.page == "login":
    login_page()

elif st.session_state.page == "chatbot":
    chatbot_page()

else:
    st.session_state.page = "home"
    st.rerun()
