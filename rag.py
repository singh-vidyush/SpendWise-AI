import os
import chromadb

from dotenv import load_dotenv

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader
)

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from langchain_huggingface import HuggingFaceEmbeddings


# =====================================================
# ENV VARIABLES
# =====================================================

load_dotenv()


# =====================================================
# CONFIG
# =====================================================

KNOWLEDGE_DIR = "finance_knowledge_base"
CHROMA_PATH = "chroma_db"


# =====================================================
# EMBEDDING MODEL
# =====================================================

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# =====================================================
# CHROMA CLIENT
# =====================================================

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)


knowledge_collection = client.get_or_create_collection(
    name="financial_knowledge"
)

user_collection = client.get_or_create_collection(
    name="user_profiles"
)


# =====================================================
# LOAD DOCUMENTS
# =====================================================

def load_all_documents():

    documents = []

    pdf_loader = DirectoryLoader(
        KNOWLEDGE_DIR,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader
    )

    docx_loader = DirectoryLoader(
        KNOWLEDGE_DIR,
        glob="**/*.docx",
        loader_cls=Docx2txtLoader
    )

    txt_loader = DirectoryLoader(
        KNOWLEDGE_DIR,
        glob="**/*.txt",
        loader_cls=TextLoader
    )


    try:
        documents.extend(
            pdf_loader.load()
        )
    except Exception:
        pass


    try:
        documents.extend(
            docx_loader.load()
        )
    except Exception:
        pass


    try:
        documents.extend(
            txt_loader.load()
        )
    except Exception:
        pass


    print(
        f"Loaded {len(documents)} documents"
    )

    return documents



# =====================================================
# CHUNK DOCUMENTS
# =====================================================

def split_documents(documents):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )


    chunks = splitter.split_documents(
        documents
    )


    print(
        f"Created {len(chunks)} chunks"
    )

    return chunks



# =====================================================
# INGEST KNOWLEDGE BASE AND USER INFO
# =====================================================

def ingest_knowledge():

    documents = load_all_documents()


    if not documents:
        print(
            "No documents found."
        )
        return


    chunks = split_documents(
        documents
    )


    ids = []
    texts = []
    metadatas = []
    embeddings = []


    for index, chunk in enumerate(chunks):

        text = chunk.page_content


        ids.append(
            f"chunk_{index}"
        )


        texts.append(
            text
        )


        metadatas.append(
            {
                "source":
                chunk.metadata.get(
                    "source",
                    "unknown"
                )
            }
        )


        embeddings.append(
            embedding_model.embed_query(
                text
            )
        )


    knowledge_collection.add(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings
    )


    print(
        f"Stored {len(ids)} chunks in ChromaDB"
    )


import json


def save_user_profile(user_id,profile_data):
    profile_text = json.dumps(
        profile_data,
        indent=2
    )

    embedding = (
        embedding_model.embed_query(
            profile_text
        )
    )

    user_collection.upsert(
        ids=[
            f"user_{user_id}"
        ],

        documents=[
            profile_text
        ],

        embeddings=[
            embedding
        ],

        metadatas=[
            {
                "user_id": user_id
            }
        ]
    )

    print(
        f"Saved profile for user_id={user_id}"
    )


# =====================================================
# GET USER DATA
# =====================================================
def get_user_profile(
    user_id
):

    result = user_collection.get(
        ids=[
            f"user_{user_id}"
        ]
    )

    if len(result["documents"]) == 0:
        return None

    return json.loads(
        result["documents"][0]
    )


def profile_exists(user_id):

    result = user_collection.get(
        ids=[f"user_{user_id}"]
    )

    return len(result["ids"]) > 0

# =====================================================
# MAIN
# =====================================================

def show_all_profiles():

    data = user_collection.get()

    print("\n=== USER PROFILES ===\n")

    print("IDS:")
    print(data["ids"])

    print("\nMETADATA:")
    print(data["metadatas"])

    print("\nDOCUMENTS:")
    print(data["documents"])

if __name__ == "__main__":

    show_all_profiles()