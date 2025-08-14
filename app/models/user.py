from sqlalchemy import Column, String, Boolean, Date, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(20))
    password_hash = Column(Text, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    date_of_birth = Column(Date)
    gender = Column(String(20))
    profile_picture = Column(Text)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    wishlist = relationship("Wishlist", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("ProductReview", back_populates="user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Address(BaseModel):
    __tablename__ = "addresses"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label = Column(String(50), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    company = Column(String(100))
    address_line1 = Column(Text, nullable=False)
    address_line2 = Column(Text)
    city = Column(String(100), nullable=False)
    province = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(50), default="Zimbabwe")
    phone = Column(String(20))
    is_default = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="addresses")


class Notification(BaseModel):
    __tablename__ = "notifications"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    # meta_data = Column(Text)  # JSON string
    # meta_data = Column(Text, nullable=True)  # Add this
    
    # Relationships
    user = relationship("User", back_populates="notifications")