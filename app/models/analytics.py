from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AnalyticsEvent(BaseModel):
    __tablename__ = "analytics_events"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100))
    event_type = Column(String(50), nullable=False)  # page_view, product_view, add_to_cart, purchase
    event_data = Column(JSON)  # JSONB in PostgreSQL
    ip_address = Column(INET)  # PostgreSQL INET type
    user_agent = Column(Text)
    
    # Relationships
    user = relationship("User", backref="analytics_events")


class SearchLog(BaseModel):
    __tablename__ = "search_logs"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query = Column(String(255), nullable=False)
    results_count = Column(Integer, default=0)
    filters_applied = Column(JSON)  # JSONB in PostgreSQL
    
    # Relationships
    user = relationship("User", backref="search_logs")
