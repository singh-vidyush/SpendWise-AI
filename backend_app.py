from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    add_user,
    verify_user,
    get_user_by_email
)

from db.vector_store import (
    upsert_user_profile,
    user_profiles_collection
)

from agents.graph import (
    run_planning_pipeline
)

import json


# =====================================================
# APP
# =====================================================

app = FastAPI(
    title="SpendWise API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# REQUEST MODELS
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
    profile: dict


class ChatRequest(BaseModel):
    user_id: int
    message: str


# =====================================================
# HELPERS
# =====================================================

def profile_exists(user_id):

    col = user_profiles_collection()

    result = col.get(
        ids=[str(user_id)]
    )

    return len(result["ids"]) > 0


def get_profile(user_id):

    col = user_profiles_collection()

    result = col.get(
        ids=[str(user_id)]
    )

    if not result["documents"]:
        return None

    return json.loads(
        result["documents"][0]
    )


# =====================================================
# ROOT
# =====================================================

@app.get("/")
def home():

    return {
        "message": "SpendWise Backend Running"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# =====================================================
# SIGNUP
# =====================================================

@app.post("/signup")
def signup(data: SignupRequest):

    existing = get_user_by_email(
        data.email.lower()
    )

    if existing:

        return {
            "success": False,
            "message": "Email already exists"
        }

    user_id = add_user(
        data.username,
        data.email.lower(),
        data.password
    )

    return {
        "success": True,
        "user_id": user_id
    }


# =====================================================
# LOGIN
# =====================================================

@app.post("/login")
def login(data: LoginRequest):

    user = verify_user(
        data.email.lower(),
        data.password
    )

    if not user:

        return {
            "success": False,
            "message": "Invalid credentials"
        }

    user_id = user[0]
    username = user[1]

    return {
        "success": True,
        "user_id": user_id,
        "username": username,
        "profile_exists": profile_exists(
            user_id
        )
    }


# =====================================================
# SAVE PROFILE
# =====================================================

@app.post("/save-profile")
def save_profile(
    request: SaveProfileRequest
):

    profile_json = json.dumps(
        request.profile,
        indent=2
    )

    upsert_user_profile(
        str(request.user_id),
        profile_json,
        {
            "user_id": request.user_id
        }
    )

    return {
        "success": True
    }


# =====================================================
# PROFILE EXISTS
# =====================================================

@app.get("/profile-exists/{user_id}")
def check_profile(user_id: int):

    return {
        "exists": profile_exists(
            user_id
        )
    }


# =====================================================
# GET PROFILE
# =====================================================

@app.get("/profile/{user_id}")
def fetch_profile(user_id: int):

    profile = get_profile(
        user_id
    )

    return {
        "profile": profile
    }


# =====================================================
# CHAT
# =====================================================

@app.post("/chat")
def chat(request: ChatRequest):

    profile = get_profile(
        request.user_id
    )

    if not profile:

        return {
            "success": False,
            "message":
                "Financial profile not found."
        }

    answers = profile[
        "financial_profile"
    ]

    debt = answers.get(
        "debt_details",
        {}
    )

    state = run_planning_pipeline(

        user_id=str(
            request.user_id
        ),

        user_name=profile.get(
            "user_name",
            "User"
        ),

        person_type=answers.get(
            "persona",
            "Salaried"
        ),

        monthly_income=float(
            answers.get(
                "monthly_income",
                0
            )
        ),

        house_emi=float(
            debt.get(
                "monthly_emi",
                0
            )
        ),

        insurance_premium=0,

        health_expenses=0,

        other_liabilities=[],

        age=30,

        chat_query=request.message,

        chat_history=[]
    )

    return {

        "success": True,

        "recommendations":
            state.get(
                "recommendations",
                []
            ),

        "calculations":
            state.get(
                "calculations",
                {}
            ),

        "market_insights":
            state.get(
                "market_insights",
                ""
            ),

        "pdf_path":
            state.get(
                "pdf_path",
                ""
            )
    }