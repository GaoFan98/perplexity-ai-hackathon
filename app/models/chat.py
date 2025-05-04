from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.database import Base

class ChatMessage(Base):
    """ChatMessage model for storing chat history."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, nullable=True)  # Telegram message ID
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)  # Message content
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    model_used = Column(String, nullable=True)  # Which Perplexity model was used
    include_thinking = Column(Boolean, default=False)  # Whether thinking was included
    
    # Relationship with User
    user = relationship("User", backref="messages")
    
    def __repr__(self):
        return f"<ChatMessage {self.id}: {self.content[:20]}{'...' if len(self.content) > 20 else ''}>" 