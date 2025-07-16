# app/database.py

from sqlmodel import SQLModel, Session, create_engine
from .constants import DATABASE_URL
from pathlib import Path

# Ensure db folder exists
Path("db").mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
