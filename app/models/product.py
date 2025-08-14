from sqlalchemy import Column, String, Text, Numeric, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Category(BaseModel):
    __tablename__ = "categories"
    
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    image_url = Column(Text)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    # Relationships
    subcategories = relationship("Subcategory", back_populates="category", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="category")


class Subcategory(BaseModel):
    __tablename__ = "subcategories"
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text)
    image_url = Column(Text)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    # Relationships
    category = relationship("Category", back_populates="subcategories")
    products = relationship("Product", back_populates="subcategory")


class Product(BaseModel):
    __tablename__ = "products"
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    short_description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    original_price = Column(Numeric(10, 2))
    cost_price = Column(Numeric(10, 2))
    rating = Column(Numeric(3, 2), default=0)
    review_count = Column(Integer, default=0)
    stock_quantity = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    sku = Column(String(50), unique=True, nullable=False)
    barcode = Column(String(50))
    weight = Column(Numeric(8, 2))
    dimensions = Column(String(100))
    category_id = Column(Integer, ForeignKey("categories.id"))
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"))
    brand = Column(String(100))
    status = Column(String(20), default="active")
    is_featured = Column(Boolean, default=False)
    meta_title = Column(String(255))
    meta_description = Column(Text)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    subcategory = relationship("Subcategory", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    attributes = relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("ProductReview", back_populates="product")
    cart_items = relationship("CartItem", back_populates="product")
    wishlist = relationship("Wishlist", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")


class ProductImage(BaseModel):
    __tablename__ = "product_images"
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    image_url = Column(Text, nullable=False)
    alt_text = Column(String(255))
    sort_order = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False)
    
    # Relationships
    product = relationship("Product", back_populates="images")


class ProductVariant(BaseModel):
    __tablename__ = "product_variants"
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String(100), nullable=False)
    sku = Column(String(50), unique=True, nullable=False)
    price = Column(Numeric(10, 2))
    stock_quantity = Column(Integer, default=0)
    color_name = Column(String(50))
    color_hex = Column(String(7))
    size_name = Column(String(50))
    weight = Column(Numeric(8, 2))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    product = relationship("Product", back_populates="variants")
    cart_items = relationship("CartItem", back_populates="variant")
    order_items = relationship("OrderItem", back_populates="variant")


class ProductAttribute(BaseModel):
    __tablename__ = "product_attributes"
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)
    type = Column(String(50), default="text")
    is_filterable = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    
    # Relationships
    product = relationship("Product", back_populates="attributes")


class ProductReview(BaseModel):
    __tablename__ = "product_reviews"
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, nullable=False)
    title = Column(String(200))
    comment = Column(Text)
    is_verified_purchase = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    helpful_count = Column(Integer, default=0)
    
    # Relationships
    product = relationship("Product", back_populates="reviews")
    user = relationship("User", back_populates="reviews")