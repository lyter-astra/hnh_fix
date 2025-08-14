from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


# Category schemas
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


class Category(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# Subcategory schemas
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
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class Subcategory(SubcategoryBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# Product schemas
class ProductBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    price: Decimal
    original_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    stock_quantity: int = 0
    low_stock_threshold: int = 10
    sku: str
    barcode: Optional[str] = None
    weight: Optional[Decimal] = None
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
    price: Optional[Decimal] = None
    original_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    brand: Optional[str] = None
    status: Optional[str] = None
    is_featured: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class Product(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    rating: Decimal = Decimal('0.00')
    review_count: int = 0
    created_at: datetime
    updated_at: datetime


# Product Image schemas
class ProductImageBase(BaseModel):
    image_url: str
    alt_text: Optional[str] = None
    sort_order: int = 0
    is_primary: bool = False


class ProductImageCreate(ProductImageBase):
    product_id: int


class ProductImage(ProductImageBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    product_id: int
    created_at: datetime


# Product Variant schemas
class ProductVariantBase(BaseModel):
    name: str
    sku: str
    price: Optional[Decimal] = None
    stock_quantity: int = 0
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    size_name: Optional[str] = None
    weight: Optional[Decimal] = None
    is_active: bool = True


class ProductVariantCreate(ProductVariantBase):
    product_id: int


class ProductVariantUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    size_name: Optional[str] = None
    weight: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductVariant(ProductVariantBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


# Product Attribute schemas
class ProductAttributeBase(BaseModel):
    name: str
    value: str
    type: str = "text"
    is_filterable: bool = False
    sort_order: int = 0


class ProductAttributeCreate(ProductAttributeBase):
    product_id: int


class ProductAttribute(ProductAttributeBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    product_id: int


# Product Review schemas
class ProductReviewBase(BaseModel):
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None


class ProductReviewCreate(ProductReviewBase):
    product_id: int


class ProductReview(ProductReviewBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    product_id: int
    user_id: Optional[int] = None
    is_verified_purchase: bool = False
    is_approved: bool = False
    helpful_count: int = 0
    created_at: datetime
    updated_at: datetime


# Product with relationships
class ProductDetail(Product):
    category: Optional[Category] = None
    subcategory: Optional[Subcategory] = None
    images: List[ProductImage] = []
    variants: List[ProductVariant] = []
    attributes: List[ProductAttribute] = []


# Search and filter schemas
class ProductFilter(BaseModel):
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    brand: Optional[str] = None
    is_featured: Optional[bool] = None
    in_stock: Optional[bool] = None
    search: Optional[str] = None
    sort_by: Optional[str] = "created_at"
    order: Optional[str] = "desc"


class ProductList(BaseModel):
    items: List[Product]
    total: int
    page: int
    per_page: int
    pages: int


    