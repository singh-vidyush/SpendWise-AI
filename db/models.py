"""
SQLite models for structured user form data.
Vector DB stores embeddings; SQLite stores exact values for calculations.
"""
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid
from config import SQLITE_DB_PATH

engine = create_engine(f"sqlite:///{SQLITE_DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    person_type = Column(String, nullable=False)   # salaried | student | retiree
    monthly_income = Column(Float, default=0.0)
    age = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Liability(Base):
    __tablename__ = "liabilities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    liability_type = Column(String)   # house_emi | insurance | health | other
    amount = Column(Float, default=0.0)
    frequency = Column(String, default="monthly")  # monthly | annual
    description = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ExpenseHistory(Base):
    __tablename__ = "expense_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    month = Column(String)           # YYYY-MM
    category = Column(String)
    amount = Column(Float, default=0.0)
    notes = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
