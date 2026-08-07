"""
ChromaDB vector store setup.
Five collections:
  1. user_profiles      – embedded user profile text for semantic retrieval
  2. expense_history    – historical expense records as text chunks
  3. financial_knowledge – tax slabs, investment rules, SIP guidelines
  4. market_data        – Tavily-fetched market/inflation/interest rate snippets
  5. past_reports       – summaries of generated PDF reports FOR FUTURE IMPLEMENTATIONS
"""
import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_USER_PROFILES,
    CHROMA_COLLECTION_EXPENSE_HISTORY,
    CHROMA_COLLECTION_FINANCIAL_KNOWLEDGE,
    CHROMA_COLLECTION_MARKET_DATA
    # CHROMA_COLLECTION_PAST_REPORTS,
)

_client = None
_embed_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def get_client() -> chromadb.PersistentClient:

    global _client

    if _client is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR
        )

    return _client


def _get_or_create(name: str):

    return get_client().get_or_create_collection(
        name=name
    )


def user_profiles_collection():
    return _get_or_create(CHROMA_COLLECTION_USER_PROFILES)


def expense_history_collection():
    return _get_or_create(CHROMA_COLLECTION_EXPENSE_HISTORY)


def financial_knowledge_collection():
    return _get_or_create(CHROMA_COLLECTION_FINANCIAL_KNOWLEDGE)


def market_data_collection():
    return _get_or_create(CHROMA_COLLECTION_MARKET_DATA)


# def past_reports_collection():
#     return _get_or_create(CHROMA_COLLECTION_PAST_REPORTS)



# def seed_financial_knowledge():
#     col = financial_knowledge_collection()
#     existing = col.get(ids=[d["id"] for d in KNOWLEDGE_DOCS])
#     existing_ids = set(existing["ids"])
#     new_docs = [d for d in KNOWLEDGE_DOCS if d["id"] not in existing_ids]
#     if new_docs:
#         col.add(
#             ids=[d["id"] for d in new_docs],
#             documents=[d["text"] for d in new_docs],
#             metadatas=[d["metadata"] for d in new_docs],
#         )


# ---------------------------------------------------------------------------
# Helper: upsert user profile embedding
# ---------------------------------------------------------------------------
def upsert_user_profile(user_id: str, profile_text: str, metadata: dict):
    col = user_profiles_collection()
    col.upsert(ids=[user_id], documents=[profile_text], metadatas=[metadata])


# ---------------------------------------------------------------------------
# Helper: add expense history chunk
# ---------------------------------------------------------------------------
def add_expense_history(doc_id: str, text: str, metadata: dict):
    col = expense_history_collection()
    col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])


# ---------------------------------------------------------------------------
# Helper: upsert market data snippet
# ---------------------------------------------------------------------------
def upsert_market_data(doc_id: str, text: str, metadata: dict):
    col = market_data_collection()
    col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])


# ---------------------------------------------------------------------------
# Helper: store past report summary
# ---------------------------------------------------------------------------
# def add_past_report(report_id: str, summary: str, metadata: dict):
#     col = past_reports_collection()
#     col.upsert(ids=[report_id], documents=[summary], metadatas=[metadata])


# ---------------------------------------------------------------------------
# Helper: query any collection
# ---------------------------------------------------------------------------
def query_collection(collection, query_text: str, n_results: int = 5) -> list[str]:

    embedding = _embed_model.embed_query(
        query_text
    )

    results = collection.query(
        query_embeddings=[
            embedding
        ],
        n_results=n_results
    )

    return results["documents"][0] if results["documents"] else []
