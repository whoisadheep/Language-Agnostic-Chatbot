from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./analytics.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_message = Column(String(500))
    detected_language = Column(String, index=True)
    response_time_ms = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    duration_seconds = Column(Integer, default=0)
    transcript = Column(Text, default="")
    detected_language = Column(String, default="en")
    turn_count = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class ProviderTelemetry(Base):
    __tablename__ = "provider_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String, index=True)
    model_name = Column(String)
    latency_ms = Column(Float)
    status = Column(String) # 'success' or 'error'
    error_message = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class LeadRecord(Base):
    __tablename__ = "lead_records"

    id = Column(Integer, primary_key=True, index=True)
    caller_name = Column(String, default="Anonymous")
    contact = Column(String, default="")
    category = Column(String, default="General Inquiry")
    summary = Column(Text, default="")
    source = Column(String, default="Voice Agent") # 'Voice Agent' or 'Chat'
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class MemorySnippet(Base):
    __tablename__ = "memory_snippets"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True) # identity, education, experience, skill, project
    title = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
