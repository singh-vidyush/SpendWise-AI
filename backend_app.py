import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

from database import add_user, verify_user, get_user_by_email
from db.vector_store import (
    upsert_user_profile,
    get_user_profile,
    profile_exists,
)
from agents.graph import run_planning_pipeline



# # =====================================================
# # APP INITIATION
# # =====================================================
app = FastAPI(title="SpendWise API")

# =====================================================
# REQUEST SCHEMAS
# =====================================================
class SignupRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SaveProfileRequest(BaseModel):
    user_id: int
    profile: Dict[str, Any]


class ChatRequest(BaseModel):
    user_id: int
    message: str


# =====================================================
# ROUTES
# =====================================================
@app.get("/")
def home():
    return {"message": "SpendWise Backend API Running"}



@app.post("/signup")
def signup(data: SignupRequest):
    existing = get_user_by_email(data.email.lower())
    if existing:
        return {"success": False, "message": "Email already exists"}

    user_id = add_user(data.username, data.email.lower(), data.password)
    return {"success": True, "user_id": user_id}


@app.post("/login")
def login(data: LoginRequest):
    user = verify_user(data.email.lower(), data.password)
    if not user:
        return {"success": False, "message": "Invalid email or password"}

    user_id = user[0]
    username = user[1]
    has_profile = profile_exists(str(user_id))

    return {
        "success": True,
        "user_id": user_id,
        "username": username,
        "profile_exists": has_profile,
    }


@app.post("/save-profile")
def save_profile(request: SaveProfileRequest):
    try:
        user_id_str = str(request.user_id)
        saved_json = upsert_user_profile(user_id_str, request.profile)
        return {"success": True, "profile": json.loads(saved_json)}
    except Exception as e:
        return {"success": False, "message": str(e)}



@app.post("/chat")
def chat(request: ChatRequest):
    user_id_str = str(request.user_id)
    profile = get_user_profile(user_id_str)

    fin = profile.get("financial_profile", {})
    debt = fin.get("debt_details", {})

    try:
        state = run_planning_pipeline(
            user_id=user_id_str,
            user_name=profile.get("user_name", "User"),
            person_type=fin.get("persona", "Salaried"),
            monthly_income=float(fin.get("monthly_income", 0.0)),
            house_emi=float(debt.get("monthly_emi", 0.0)),
            chat_query=request.message,
            profile_dict=profile,
        )

        return {
            "success": True,
            "response_text": state.get("response_text", ""),
            "intent": state.get("intent", "financial_analysis"),
            "recommendations": state.get("recommendations", []),
            "tradeoff_analysis": state.get("tradeoff_analysis", []),
            "calculations": state.get("financial_metrics", {}),
            "market_insights": state.get("market_context", ""),
            "pdf_path": state.get("pdf_path", ""),
        }
    except Exception as e:
        return {"success": False, "message": f"Pipeline Error: {str(e)}"}