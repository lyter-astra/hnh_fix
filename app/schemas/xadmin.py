# app/schemas/admin.py

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# ==================== CATEGORY SCHEMAS ====================

class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class CategorySchema(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== SUBCATEGORY SCHEMAS ====================

class SubcategoryBase(BaseModel):
    category_id: int
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

class SubcategoryCreate(SubcategoryBase):
    pass

class SubcategoryUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class SubcategorySchema(SubcategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category: Optional[CategorySchema] = None
    
    class Config:
        from_attributes = True

# ==================== PRODUCT IMAGE SCHEMAS ====================

class ProductImageBase(BaseModel):
    image_url: str
    alt_text: Optional[str] = None
    sort_order: int = 0
    is_primary: bool = False

class ProductImageCreate(ProductImageBase):
    pass

class ProductImageUpdate(BaseModel):
    image_url: Optional[str] = None
    alt_text: Optional[str] = None
    sort_order: Optional[int] = None
    is_primary: Optional[bool] = None

class ProductImageSchema(ProductImageBase):
    id: int
    product_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== PRODUCT VARIANT SCHEMAS ====================

class ProductVariantBase(BaseModel):
    name: str
    sku: str
    price: Optional[float] = None
    stock_quantity: int = 0
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    size_name: Optional[str] = None
    weight: Optional[float] = None
    is_active: bool = True

class ProductVariantCreate(ProductVariantBase):
    pass

class ProductVariantUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    size_name: Optional[str] = None
    weight: Optional[float] = None
    is_active: Optional[bool] = None

class ProductVariantSchema(ProductVariantBase):
    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== PRODUCT ATTRIBUTE SCHEMAS ====================

class ProductAttributeBase(BaseModel):
    name: str
    value: str
    type: str = "text"
    is_filterable: bool = False
    sort_order: int = 0

class ProductAttributeCreate(ProductAttributeBase):
    pass

class ProductAttributeUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    type: Optional[str] = None
    is_filterable: Optional[bool] = None
    sort_order: Optional[int] = None

class ProductAttributeSchema(ProductAttributeBase):
    id: int
    product_id: int
    
    class Config:
        from_attributes = True

# ==================== PRODUCT SCHEMAS ====================

class ProductBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    cost_price: Optional[float] = None
    stock_quantity: int = 0
    low_stock_threshold: int = 10
    sku: str
    barcode: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    brand: Optional[str] = None
    status: str = "active"
    is_featured: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    cost_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    brand: Optional[str] = None
    status: Optional[str] = None
    is_featured: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

class ProductSchema(ProductBase):
    id: int
    rating: float = 0
    review_count: int = 0
    created_at: datetime
    updated_at: datetime
    category: Optional[CategorySchema] = None
    subcategory: Optional[SubcategorySchema] = None
    images: List[ProductImageSchema] = []
    
    class Config:
        from_attributes = True

# ==================== USER SCHEMAS ====================

class UserBase(BaseModel):
    email: str
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    profile_picture: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    is_active: bool = True

class UserCreate(UserBase):
    password_hash: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    profile_picture: Optional[str] = None
    email_verified: Optional[bool] = None
    phone_verified: Optional[bool] = None
    is_active: Optional[bool] = None

class UserSchema(UserBase):
    id: int
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== ORDER SCHEMAS ====================

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None
    notes: Optional[str] = None
    shipping_cost: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_amount: Optional[float] = None

class OrderSchema(BaseModel):
    id: int
    user_id: Optional[int] = None
    order_number: str
    status: str
    payment_status: str
    currency: str
    subtotal: float
    tax_amount: float
    shipping_cost: float
    discount_amount: float
    total_amount: float
    notes: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== PAYMENT SCHEMAS ====================

class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    transaction_id: Optional[str] = None
    gateway_response: Optional[str] = None
    processed_at: Optional[datetime] = None

# ==================== COUPON SCHEMAS ====================

class CouponBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    type: str  # percentage, fixed_amount, free_shipping
    value: float
    minimum_amount: Optional[float] = None
    maximum_discount: Optional[float] = None
    usage_limit: Optional[int] = None
    is_active: bool = True
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class CouponCreate(CouponBase):
    pass

class CouponUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    value: Optional[float] = None
    minimum_amount: Optional[float] = None
    maximum_discount: Optional[float] = None
    usage_limit: Optional[int] = None
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class CouponSchema(CouponBase):
    id: int
    usage_count: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== NOTIFICATION SCHEMAS ====================

class NotificationCreate(BaseModel):
    type: str
    title: str
    message: str

# ==================== REVIEW SCHEMAS ====================

class ProductReviewSchema(BaseModel):
    id: int
    product_id: int
    user_id: Optional[int] = None
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    is_verified_purchase: bool = False
    is_approved: bool = False
    helpful_count: int = 0
    created_at: datetime
    updated_at: datetime
    user: Optional[UserSchema] = None
    product: Optional[ProductSchema] = None
    
    class Config:
        from_attributes = True