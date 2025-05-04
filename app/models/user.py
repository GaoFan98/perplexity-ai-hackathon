from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from db.database import Base

class User(Base):
    """User model for storing user data."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    preferred_model = Column(String, default="sonar-pro")
    conversation_history = Column(Text, default="[]")  # Storing as JSON string
    thinking_mode = Column(Boolean, default=False)  # Whether to show thinking process
    reminders_count = Column(Integer, default=0)  # Count of active reminders
    
    def __repr__(self):
        return f"<User {self.telegram_id}: {self.username}>" 