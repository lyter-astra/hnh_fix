from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.schemas.product import Product as ProductSchema
from app.schemas.user import Address as AddressSchema


# Cart Item schemas
class CartItemBase(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    price: Decimal


class CartItemCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


class CartItem(CartItemBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductSchema] = None


# Wishlist schemas
class WishlistItemBase(BaseModel):
    product_id: int


class WishlistItemCreate(WishlistItemBase):
    pass


class WishlistItem(WishlistItemBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    product: Optional[ProductSchema] = None


# Order schemas
class OrderItemBase(BaseModel):
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    product_name: str
    variant_name: Optional[str] = None
    sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


class OrderItem(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    order_id: int
    created_at: datetime


class OrderBase(BaseModel):
    order_number: str
    status: str = "pending"
    payment_status: str = "pending"
    currency: str = "USD"
    subtotal: Decimal
    tax_amount: Decimal = Decimal('0.00')
    shipping_cost: Decimal = Decimal('0.00')
    discount_amount: Decimal = Decimal('0.00')
    total_amount: Decimal
    
    # Shipping Address
    shipping_first_name: Optional[str] = None
    shipping_last_name: Optional[str] = None
    shipping_company: Optional[str] = None
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_province: Optional[str] = None
    shipping_postal_code: Optional[str] = None
    shipping_country: Optional[str] = None
    shipping_phone: Optional[str] = None
    
    # Billing Address
    billing_first_name: Optional[str] = None
    billing_last_name: Optional[str] = None
    billing_company: Optional[str] = None
    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_province: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    billing_phone: Optional[str] = None
    
    notes: Optional[str] = None


class OrderCreate(BaseModel):
    shipping_address_id: int
    billing_address_id: Optional[int] = None  # If None, use shipping address
    payment_method: str
    notes: Optional[str] = None
    coupon_code: Optional[str] = None


class Order(OrderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: Optional[int] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    order_items: List[OrderItem] = []


class OrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    order_number: str
    status: str
    payment_status: str
    total_amount: Decimal
    created_at: datetime


# Payment schemas
class PaymentBase(BaseModel):
    payment_method: str
    payment_provider: Optional[str] = None
    amount: Decimal
    currency: str = "USD"


class PaymentCreate(PaymentBase):
    order_id: int


class Payment(PaymentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    order_id: int
    transaction_id: Optional[str] = None
    status: str = "pending"
    gateway_response: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


# Coupon schemas
class CouponBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    type: str  # percentage, fixed_amount, free_shipping
    value: Decimal
    minimum_amount: Optional[Decimal] = None
    maximum_discount: Optional[Decimal] = None
    usage_limit: Optional[int] = None
    is_active: bool = True


class CouponCreate(CouponBase):
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class CouponUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[Decimal] = None
    minimum_amount: Optional[Decimal] = None
    maximum_discount: Optional[Decimal] = None
    usage_limit: Optional[int] = None
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class Coupon(CouponBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    usage_count: int = 0
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CouponValidation(BaseModel):
    valid: bool
    discount_amount: Optional[Decimal] = None
    message: Optional[str] = None