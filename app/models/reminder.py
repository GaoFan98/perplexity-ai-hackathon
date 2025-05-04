from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.database import Base

class Reminder(Base):
    """Reminder model for storing user reminders."""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)  # The reminder message
    scheduled_at = Column(DateTime(timezone=True), nullable=False)  # When to send the reminder
    is_recurring = Column(Boolean, default=False)  # Whether this is a recurring reminder
    recurrence_pattern = Column(String, nullable=True)  # Cron expression for recurring reminders
    is_active = Column(Boolean, default=True)  # Whether the reminder is active
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship with User
    user = relationship("User", backref="reminders")
    
    def __repr__(self):
        return f"<Reminder {self.id}: {self.text[:20]}{'...' if len(self.text) > 20 else ''}>" 