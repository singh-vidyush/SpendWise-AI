import os
from dotenv import load_dotenv

load_dotenv()

# gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

# ChromaDB
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
CHROMA_COLLECTION_USER_PROFILES = "user_profiles"
CHROMA_COLLECTION_EXPENSE_HISTORY = "expense_history"
CHROMA_COLLECTION_FINANCIAL_KNOWLEDGE = "financial_knowledge"
CHROMA_COLLECTION_MARKET_DATA = "market_data"
CHROMA_COLLECTION_PAST_REPORTS = "past_reports"

# SQLite (structured data)
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "financial.db")

# PDF output
PDF_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
