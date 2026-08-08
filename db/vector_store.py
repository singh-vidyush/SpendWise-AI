"""
ChromaDB vector store setup for SpendWise-AI.

Five Collections:
  1. user_profiles       – user profile JSON and metadata (versioned)
  2. expense_history     – historical expense records as text chunks
  3. financial_knowledge – tax slabs, investment rules, SIP guidelines
  4. market_data         – Tavily-fetched market/inflation/interest rate snippets
  5. past_reports        – summaries and metadata of generated PDF reports
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import chromadb
from langchain_huggingface import HuggingFaceEmbeddings

from config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_USER_PROFILES,
    CHROMA_COLLECTION_EXPENSE_HISTORY,
    CHROMA_COLLECTION_FINANCIAL_KNOWLEDGE,
    CHROMA_COLLECTION_MARKET_DATA,
    CHROMA_COLLECTION_PAST_REPORTS,
)

logger = logging.getLogger(__name__)

_client = None
_embed_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embed_model


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def _get_or_create(name: str):
    return get_client().get_or_create_collection(name=name)


def user_profiles_collection():
    return _get_or_create(CHROMA_COLLECTION_USER_PROFILES)


def expense_history_collection():
    return _get_or_create(CHROMA_COLLECTION_EXPENSE_HISTORY)


def financial_knowledge_collection():
    return _get_or_create(CHROMA_COLLECTION_FINANCIAL_KNOWLEDGE)


def market_data_collection():
    return _get_or_create(CHROMA_COLLECTION_MARKET_DATA)


def past_reports_collection():
    return _get_or_create(CHROMA_COLLECTION_PAST_REPORTS)


# ---------------------------------------------------------------------------
# Schema Validation and Normalization
# ---------------------------------------------------------------------------
# user normalization can be removed as its in frontend
# def normalize_user_profile(raw_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and normalizes frontend user profile JSON.
    Handles missing or ill-formatted fields safely.
    """
    if not isinstance(raw_profile, dict):
        raw_profile = {}
        #can be changes based on frontend input variable 
    user_name = raw_profile.get("user_name") or raw_profile.get("name") or "User"
    user_email = raw_profile.get("user_email") or raw_profile.get("email") or ""

    fin = raw_profile.get("financial_profile")
    if not isinstance(fin, dict):
        fin = raw_profile

    persona = fin.get("persona") or fin.get("person_type") or "Salaried"
    monthly_income = float(fin.get("monthly_income") or 0.0)
    essential_expenses = float(fin.get("essential_expenses") or 0.0)
    non_essential_expenses = float(fin.get("non_essential_expenses") or 0.0)
    current_savings = float(fin.get("current_savings") or 0.0)
    monthly_saving_investment = float(fin.get("monthly_saving_investment") or 0.0)

    debt_details = fin.get("debt_details")
    if not isinstance(debt_details, dict):
        debt_details = {
            "has_debt": False,
            "debt_type": "None",
            "total_outstanding_debt": 0.0,
            "monthly_emi": 0.0,
        }
    else:
        debt_details = {
            "has_debt": bool(debt_details.get("has_debt", False)),
            "debt_type": str(debt_details.get("debt_type", "None")),
            "total_outstanding_debt": float(debt_details.get("total_outstanding_debt", 0.0)),
            "monthly_emi": float(debt_details.get("monthly_emi", 0.0)),
        }

    investments = fin.get("investments")
    if not isinstance(investments, list):
        investments = []

    normalized = {
        "user_name": str(user_name),
        "user_email": str(user_email),
        "financial_profile": {
            "persona": str(persona),
            "monthly_income": monthly_income,
            "essential_expenses": essential_expenses,
            "non_essential_expenses": non_essential_expenses,
            "current_savings": current_savings,
            "debt_details": debt_details,
            "investments": investments,
            "monthly_saving_investment": monthly_saving_investment,
        },
        "updated_at": datetime.utcnow().isoformat(),
    }
    return normalized


# ---------------------------------------------------------------------------
# Helper: User Profile Ops
# ---------------------------------------------------------------------------
def upsert_user_profile(user_id, profile_data, session_id="default"):
    """
        Normalizes profile, creates embeddings and metadata, stores in ChromaDB.
        Supports update and versioning.
    """
    # profile = normalize_user_profile(profile_data)
    profile_json = json.dumps(profile_data)

    try:
        user_profiles_collection().upsert(
            ids=[f"user_{user_id}"],
            documents=[profile_json],
            embeddings=[get_embed_model().embed_query(profile_json)],
            metadatas=[{
                "user_id": str(user_id),
                "session_id": str(session_id)
            }]
        )
        
    except Exception as e:
        logger.error(e)

    return profile_json


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    col = user_profiles_collection()
    try:
        res = col.get(ids=[f"user_{user_id}"])
        if not res or not res.get("documents"):
            res = col.get(ids=[str(user_id)])

        if res and res.get("documents") and len(res["documents"]) > 0:
            return json.loads(res["documents"][0])
    except Exception as e:
        logger.error(f"Error fetching profile for user_id={user_id}: {e}")
    return None


def profile_exists(user_id: str) -> bool:
    try:
        col = user_profiles_collection()
        return bool(col.get(ids=[f"user_{user_id}"]).get("ids"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helper: Market Data Ops
# ---------------------------------------------------------------------------
def upsert_market_data(doc_id: str, text: str, metadata: Dict[str, Any]):
    col = market_data_collection()
    try:
        embed = get_embed_model().embed_query(text)
        col.upsert(ids=[doc_id], documents=[text], embeddings=[embed], metadatas=[metadata])
    except Exception as e:
        logger.error(f"Error upserting market data: {e}")


# ---------------------------------------------------------------------------
# Helper: Past Reports Ops
# ---------------------------------------------------------------------------
def add_past_report(user_id: str, report_id: str, summary: str, filepath: str, metadata: Optional[Dict[str, Any]] = None):
    col = past_reports_collection()
    doc_id = f"report_{user_id}_{report_id}"
    meta = metadata or {}
    meta.update({
        "user_id": str(user_id),
        "report_id": str(report_id),
        "filepath": filepath,
        "created_at": datetime.utcnow().isoformat(),
    })
    try:
        embed = get_embed_model().embed_query(summary)
        col.upsert(ids=[doc_id], documents=[summary], embeddings=[embed], metadatas=[meta])
    except Exception as e:
        logger.error(f"Error storing past report: {e}")



# ---------------------------------------------------------------------------
# Helper: Generic Query across collections
# ---------------------------------------------------------------------------
def query_collection(collection, query_text: str, n_results: int = 5) -> List[str]:
    try:
        embedding = get_embed_model().embed_query(query_text)
        results = collection.query(query_embeddings=[embedding], n_results=n_results)
        if results and results.get("documents") and len(results["documents"]) > 0:
            return results["documents"][0]
    except Exception as e:
        logger.error(f"Error querying collection: {e}")
    return []
