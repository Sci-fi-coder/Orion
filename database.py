import os
from datetime import datetime
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

load_dotenv()

# Database path configuration
SQLITE_PATH = os.getenv("SQLITE_PATH", "./orion.db")

# Format SQLite connection string
if SQLITE_PATH.startswith("sqlite:///"):
    DATABASE_URL = SQLITE_PATH
else:
    DATABASE_URL = f"sqlite:///{SQLITE_PATH}"

# SQLite engine with check_same_thread=False
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base
Base = declarative_base()


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    query_count = Column(Integer, default=0)

    papers = relationship("Paper", back_populates="workspace", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="workspace", cascade="all, delete-orphan")


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    arxiv_id = Column(String, nullable=False)
    title = Column(String, nullable=True)
    authors = Column(String, nullable=True)
    abstract = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    venue = Column(String, nullable=True)
    citations = Column(Integer, default=0)
    final_score = Column(Float, nullable=True)
    pdf_url = Column(String, nullable=True)
    ingested = Column(Boolean, default=False)
    ingested_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "arxiv_id", name="uq_workspace_arxiv"),
    )

    workspace = relationship("Workspace", back_populates="papers")


class Query(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    faithfulness_score = Column(Float, nullable=True)
    relevance_score = Column(Float, nullable=True)
    precision_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="queries")


def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
