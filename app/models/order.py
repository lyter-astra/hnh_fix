from sqlalchemy import Column, String, Text, Numeric, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class CartItem(BaseModel):
    __tablename__ = "cart_items"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"))
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', 'variant_id', name='uq_cart_item'),
    )
    
    # Relationships
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")
    variant = relationship("ProductVariant", back_populates="cart_items")


class Wishlist(BaseModel):
    __tablename__ = "wishlist"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='uq_wishlist_item'),
    )
    
    # Relationships
    user = relationship("User", back_populates="wishlist")
    product = relationship("Product", back_populates="wishlist")


class Order(BaseModel):
    __tablename__ = "orders"
    
    user_id = Column(Integer, ForeignKey("users.id"))
    order_number = Column(String(50), unique=True, nullable=False)
    status = Column(String(50), default="pending")
    payment_status = Column(String(50), default="pending")
    currency = Column(String(3), default="USD")
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    # Shipping Address (snapshot)
    shipping_first_name = Column(String(100))
    shipping_last_name = Column(String(100))
    shipping_company = Column(String(100))
    shipping_address_line1 = Column(Text)
    shipping_address_line2 = Column(Text)
    shipping_city = Column(String(100))
    shipping_province = Column(String(100))
    shipping_postal_code = Column(String(20))
    shipping_country = Column(String(50))
    shipping_phone = Column(String(20))
    
    # Billing Address (snapshot)
    billing_first_name = Column(String(100))
    billing_last_name = Column(String(100))
    billing_company = Column(String(100))
    billing_address_line1 = Column(Text)
    billing_address_line2 = Column(Text)
    billing_city = Column(String(100))
    billing_province = Column(String(100))
    billing_postal_code = Column(String(20))
    billing_country = Column(String(50))
    billing_phone = Column(String(20))
    
    notes = Column(Text)
    shipped_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")


class OrderItem(BaseModel):
    __tablename__ = "order_items"
    
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))
    variant_id = Column(Integer, ForeignKey("product_variants.id"))
    product_name = Column(String(255), nullable=False)
    variant_name = Column(String(100))
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")
    variant = relationship("ProductVariant", back_populates="order_items")


class Payment(BaseModel):
    __tablename__ = "payments"
    
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    payment_method = Column(String(50), nullable=False)
    payment_provider = Column(String(50))
    transaction_id = Column(String(100))
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(50), default="pending")
    gateway_response = Column(Text)
    processed_at = Column(DateTime(timezone=True))
    
    # Relationships
    order = relationship("Order", back_populates="payments")


class Coupon(BaseModel):
    __tablename__ = "coupons"
    
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    type = Column(String(20), nullable=False)
    value = Column(Numeric(10, 2), nullable=False)
    minimum_amount = Column(Numeric(10, 2))
    maximum_discount = Column(Numeric(10, 2))
    usage_limit = Column(Integer)
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    starts_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))