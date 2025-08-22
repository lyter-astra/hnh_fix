from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, desc
from sqlalchemy.orm import selectinload, joinedload
from decimal import Decimal
from datetime import datetime
import uuid

from app.database import get_db
from app.models.order import Order, OrderItem, CartItem, Wishlist, Payment, Coupon
from app.models.product import Product, ProductVariant
from app.models.user import User, Address
from app.schemas.order import (
    Order as OrderSchema,
    OrderCreate,
    OrderSummary,
    CartItem as CartItemSchema,
    CartItemCreate,
    CartItemUpdate,
    WishlistItem as WishlistItemSchema,
    WishlistItemCreate,
    Payment as PaymentSchema,
    PaymentCreate,
    Coupon as CouponSchema,
    CouponCreate,
    CouponUpdate,
    CouponValidation
)
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/orders", tags=["Order Management"])


# Cart Management
@router.get("/cart", response_model=List[CartItemSchema])
async def get_cart_items(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's cart items."""
    result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product),
            selectinload(CartItem.variant)  # Load variant relationship too
        )
        .where(CartItem.user_id == current_user.id)
        .order_by(CartItem.created_at.desc())
    )
    cart_items = result.scalars().all()
    return cart_items


@router.post("/cart", response_model=CartItemSchema, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    cart_item_data: CartItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Add item to cart."""
    # Check if product exists
    product_result = await db.execute(
        select(Product).where(Product.id == cart_item_data.product_id)
    )
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if variant exists (if specified)
    variant_price = None
    if cart_item_data.variant_id:
        variant_result = await db.execute(
            select(ProductVariant).where(
                and_(
                    ProductVariant.id == cart_item_data.variant_id,
                    ProductVariant.product_id == cart_item_data.product_id
                )
            )
        )
        variant = variant_result.scalar_one_or_none()
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product variant not found"
            )
        variant_price = variant.price
    
    # Check if item already exists in cart with proper loading
    existing_item_result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product),
            selectinload(CartItem.variant)
        )
        .where(
            and_(
                CartItem.user_id == current_user.id,
                CartItem.product_id == cart_item_data.product_id,
                CartItem.variant_id == cart_item_data.variant_id
            )
        )
    )
    existing_item = existing_item_result.scalar_one_or_none()
    
    if existing_item:
        # Update quantity
        existing_item.quantity += cart_item_data.quantity
        await db.commit()
        
        # Reload with relationships
        result = await db.execute(
            select(CartItem)
            .options(
                selectinload(CartItem.product),
                selectinload(CartItem.variant)
            )
            .where(CartItem.id == existing_item.id)
        )
        return result.scalar_one()
    
    # Create new cart item
    cart_item = CartItem(
        user_id=current_user.id,
        product_id=cart_item_data.product_id,
        variant_id=cart_item_data.variant_id,
        quantity=cart_item_data.quantity,
        price=variant_price or product.price
    )
    
    db.add(cart_item)
    await db.commit()
    
    # Load with relationships after commit
    result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product),
            selectinload(CartItem.variant)
        )
        .where(CartItem.id == cart_item.id)
    )
    
    return result.scalar_one()


@router.put("/cart/{cart_item_id}", response_model=CartItemSchema)
async def update_cart_item(
    cart_item_id: int,
    cart_item_update: CartItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update cart item quantity."""
    result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product),
            selectinload(CartItem.variant)
        )
        .where(
            and_(
                CartItem.id == cart_item_id,
                CartItem.user_id == current_user.id
            )
        )
    )
    cart_item = result.scalar_one_or_none()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )
    
    if cart_item_update.quantity <= 0:
        await db.delete(cart_item)
        await db.commit()
        return {"message": "Item removed from cart"}
    
    cart_item.quantity = cart_item_update.quantity
    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product),
            selectinload(CartItem.variant)
        )
        .where(CartItem.id == cart_item.id)
    )
    
    return result.scalar_one()


@router.delete("/cart/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_cart(
    cart_item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove item from cart."""
    result = await db.execute(
        select(CartItem).where(
            and_(
                CartItem.id == cart_item_id,
                CartItem.user_id == current_user.id
            )
        )
    )
    cart_item = result.scalar_one_or_none()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )
    
    await db.delete(cart_item)
    await db.commit()


@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear all items from cart."""
    result = await db.execute(
        select(CartItem).where(CartItem.user_id == current_user.id)
    )
    cart_items = result.scalars().all()
    
    for item in cart_items:
        await db.delete(item)
    
    await db.commit()


# Wishlist Management
@router.get("/wishlist", response_model=List[WishlistItemSchema])
async def get_wishlist_items(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's wishlist items."""
    result = await db.execute(
        select(Wishlist)
        .options(selectinload(Wishlist.product))
        .where(Wishlist.user_id == current_user.id)
        .order_by(Wishlist.created_at.desc())
    )
    wishlist_items = result.scalars().all()
    return wishlist_items


@router.post("/wishlist", response_model=WishlistItemSchema, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    wishlist_item_data: WishlistItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Add item to wishlist."""
    # Check if product exists
    product_result = await db.execute(
        select(Product).where(Product.id == wishlist_item_data.product_id)
    )
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if item already exists in wishlist
    existing_item_result = await db.execute(
        select(Wishlist).where(
            and_(
                Wishlist.user_id == current_user.id,
                Wishlist.product_id == wishlist_item_data.product_id
            )
        )
    )
    existing_item = existing_item_result.scalar_one_or_none()
    
    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item already in wishlist"
        )
    
    wishlist_item = Wishlist(
        user_id=current_user.id,
        product_id=wishlist_item_data.product_id
    )
    
    db.add(wishlist_item)
    await db.commit()
    
    # Load with product relationship after commit
    result = await db.execute(
        select(Wishlist)
        .options(selectinload(Wishlist.product))
        .where(Wishlist.id == wishlist_item.id)
    )
    
    return result.scalar_one()


@router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove item from wishlist."""
    result = await db.execute(
        select(Wishlist).where(
            and_(
                Wishlist.product_id == product_id,
                Wishlist.user_id == current_user.id
            )
        )
    )
    wishlist_item = result.scalar_one_or_none()
    
    if not wishlist_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist item not found"
        )
    
    await db.delete(wishlist_item)
    await db.commit()


# Order Management
@router.get("", response_model=List[OrderSummary])  # Changed from "/" to ""
async def get_user_orders(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by order status"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0)
):
    """Get user's orders."""
    query = select(Order).where(Order.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Order.status == status_filter)
    
    query = query.order_by(desc(Order.created_at)).offset(offset).limit(limit)
    
    result = await db.execute(query)
    orders = result.scalars().all()
    return orders


@router.get("/{order_id}", response_model=OrderSchema)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific order details."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.order_items).selectinload(OrderItem.product),
            selectinload(Order.user)
        )
        .where(
            and_(
                Order.id == order_id,
                Order.user_id == current_user.id
            )
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return order


@router.post("", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)  # Changed from "/" to ""
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new order from cart."""
    try:
        # Get cart items with both product and variant relationships loaded
        cart_result = await db.execute(
            select(CartItem)
            .options(
                selectinload(CartItem.product),
                selectinload(CartItem.variant)
            )
            .where(CartItem.user_id == current_user.id)
        )
        cart_items = cart_result.scalars().all()
        
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty"
            )
        
        # Get shipping address
        shipping_address_result = await db.execute(
            select(Address).where(
                and_(
                    Address.id == order_data.shipping_address_id,
                    Address.user_id == current_user.id
                )
            )
        )
        shipping_address = shipping_address_result.scalar_one_or_none()
        
        if not shipping_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipping address not found"
            )
        
        # Get billing address (use shipping if not specified)
        billing_address = shipping_address
        if order_data.billing_address_id:
            billing_address_result = await db.execute(
                select(Address).where(
                    and_(
                        Address.id == order_data.billing_address_id,
                        Address.user_id == current_user.id
                    )
                )
            )
            billing_address = billing_address_result.scalar_one_or_none()
            
            if not billing_address:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Billing address not found"
                )
        
        # Calculate totals
        subtotal = sum(item.price * item.quantity for item in cart_items)
        tax_amount = Decimal('0.00')  # Calculate based on your tax logic
        shipping_cost = Decimal('0.00')  # Calculate based on your shipping logic
        discount_amount = Decimal('0.00')
        
        # Apply coupon if provided
        if order_data.coupon_code:
            coupon_validation = await validate_coupon(
                order_data.coupon_code, subtotal, current_user.id, db
            )
            if not coupon_validation.valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=coupon_validation.message
                )
            discount_amount = coupon_validation.discount_amount
        
        total_amount = subtotal + tax_amount + shipping_cost - discount_amount
        
        # Generate order number
        order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Create order
        order = Order(
            user_id=current_user.id,
            order_number=order_number,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_cost=shipping_cost,
            discount_amount=discount_amount,
            total_amount=total_amount,
            
            # Shipping address snapshot
            shipping_first_name=shipping_address.first_name,
            shipping_last_name=shipping_address.last_name,
            shipping_company=shipping_address.company,
            shipping_address_line1=shipping_address.address_line1,
            shipping_address_line2=shipping_address.address_line2,
            shipping_city=shipping_address.city,
            shipping_province=shipping_address.province,
            shipping_postal_code=shipping_address.postal_code,
            shipping_country=shipping_address.country,
            shipping_phone=shipping_address.phone,
            
            # Billing address snapshot
            billing_first_name=billing_address.first_name,
            billing_last_name=billing_address.last_name,
            billing_company=billing_address.company,
            billing_address_line1=billing_address.address_line1,
            billing_address_line2=billing_address.address_line2,
            billing_city=billing_address.city,
            billing_province=billing_address.province,
            billing_postal_code=billing_address.postal_code,
            billing_country=billing_address.country,
            billing_phone=billing_address.phone,
            
            notes=order_data.notes
        )
        
        db.add(order)
        await db.flush()  # Get order ID
        
        # Create order items with proper null checks
        for cart_item in cart_items:
            # Safely get variant attributes
            variant_name = None
            variant_sku = None
            
            if cart_item.variant_id and cart_item.variant:
                variant_name = cart_item.variant.name
                variant_sku = cart_item.variant.sku
            
            # Determine SKU (use variant SKU if available, otherwise product SKU)
            sku = variant_sku if variant_sku else cart_item.product.sku
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                variant_id=cart_item.variant_id,
                product_name=cart_item.product.name,
                variant_name=variant_name,
                sku=sku,
                quantity=cart_item.quantity,
                unit_price=cart_item.price,
                total_price=cart_item.price * cart_item.quantity
            )
            db.add(order_item)
        
        # Update coupon usage if applied
        if order_data.coupon_code:
            await db.execute(
                update(Coupon)
                .where(Coupon.code == order_data.coupon_code)
                .values(usage_count=Coupon.usage_count + 1)
            )
        
        # Clear cart after successful order
        for cart_item in cart_items:
            await db.delete(cart_item)
        
        await db.commit()
        
        # Properly load the order with all relationships
        result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.order_items).selectinload(OrderItem.product),
                selectinload(Order.user)
            )
            .where(Order.id == order.id)
        )
        order = result.scalar_one()
        
        return order
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the actual error for debugging
        import traceback
        print(f"Error creating order: {str(e)}")
        print(traceback.format_exc())
        
        # Rollback the transaction
        await db.rollback()
        
        # Return a generic error to the client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


# Payment Management
@router.post("/{order_id}/payments", response_model=PaymentSchema, status_code=status.HTTP_201_CREATED)
async def create_payment(
    order_id: int,
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create payment for order."""
    # Verify order belongs to user
    order_result = await db.execute(
        select(Order).where(
            and_(
                Order.id == order_id,
                Order.user_id == current_user.id
            )
        )
    )
    order = order_result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    payment = Payment(
        order_id=order_id,
        **payment_data.model_dump()
    )
    
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    
    return payment


@router.get("/{order_id}/payments", response_model=List[PaymentSchema])
async def get_order_payments(
    order_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payments for order."""
    # Verify order belongs to user
    order_result = await db.execute(
        select(Order).where(
            and_(
                Order.id == order_id,
                Order.user_id == current_user.id
            )
        )
    )
    order = order_result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    result = await db.execute(
        select(Payment)
        .where(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    
    return payments


# Coupon Management
@router.post("/coupons/validate", response_model=CouponValidation)
async def validate_coupon_endpoint(
    coupon_code: str,
    cart_total: Decimal,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate coupon code."""
    return await validate_coupon(coupon_code, cart_total, current_user.id, db)


# Helper function for coupon validation
async def validate_coupon(
    coupon_code: str,
    cart_total: Decimal,
    user_id: int,
    db: AsyncSession
) -> CouponValidation:
    """Validate coupon and calculate discount."""
    result = await db.execute(
        select(Coupon).where(Coupon.code == coupon_code)
    )
    coupon = result.scalar_one_or_none()
    
    if not coupon:
        return CouponValidation(valid=False, message="Coupon not found")
    
    if not coupon.is_active:
        return CouponValidation(valid=False, message="Coupon is not active")
    
    now = datetime.utcnow()
    if coupon.starts_at and now < coupon.starts_at:
        return CouponValidation(valid=False, message="Coupon is not yet active")
    
    if coupon.expires_at and now > coupon.expires_at:
        return CouponValidation(valid=False, message="Coupon has expired")
    
    if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
        return CouponValidation(valid=False, message="Coupon usage limit reached")
    
    if coupon.minimum_amount and cart_total < coupon.minimum_amount:
        return CouponValidation(
            valid=False,
            message=f"Minimum order amount of ${coupon.minimum_amount} required"
        )
    
    # Calculate discount
    if coupon.type == "percentage":
        discount = (cart_total * coupon.value) / 100
        if coupon.maximum_discount:
            discount = min(discount, coupon.maximum_discount)
    elif coupon.type == "fixed_amount":
        discount = min(coupon.value, cart_total)
    elif coupon.type == "free_shipping":
        # This would need shipping cost calculation
        discount = Decimal('0.00')  # Placeholder
    else:
        return CouponValidation(valid=False, message="Invalid coupon type")
    
    return CouponValidation(
        valid=True,
        discount_amount=discount,
        message="Coupon is valid"
    )


__all__ = ["router"]



# from typing import List, Optional
# from fastapi import APIRouter, Depends, HTTPException, status, Query
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, update, and_, or_, desc
# from sqlalchemy.orm import selectinload
# from decimal import Decimal
# from datetime import datetime
# import uuid

# from app.database import get_db
# from app.models.order import Order, OrderItem, CartItem, Wishlist, Payment, Coupon
# from app.models.product import Product, ProductVariant
# from app.models.user import User, Address
# from app.schemas.order import (
#     Order as OrderSchema,
#     OrderCreate,
#     OrderSummary,
#     CartItem as CartItemSchema,
#     CartItemCreate,
#     CartItemUpdate,
#     WishlistItem as WishlistItemSchema,
#     WishlistItemCreate,
#     Payment as PaymentSchema,
#     PaymentCreate,
#     Coupon as CouponSchema,
#     CouponCreate,
#     CouponUpdate,
#     CouponValidation
# )
# from app.api.deps import get_current_active_user

# router = APIRouter(prefix="/orders", tags=["Order Management"])


# # Cart Management
# @router.get("/cart", response_model=List[CartItemSchema])
# async def get_cart_items(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get user's cart items."""
#     result = await db.execute(
#         select(CartItem)
#         .options(selectinload(CartItem.product))
#         .where(CartItem.user_id == current_user.id)
#         .order_by(CartItem.created_at.desc())
#     )
#     cart_items = result.scalars().all()
#     return cart_items


# @router.post("/cart", response_model=CartItemSchema, status_code=status.HTTP_201_CREATED)
# async def add_to_cart(
#     cart_item_data: CartItemCreate,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Add item to cart."""
#     # Check if product exists
#     product_result = await db.execute(
#         select(Product).where(Product.id == cart_item_data.product_id)
#     )
#     product = product_result.scalar_one_or_none()
    
#     if not product:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Product not found"
#         )
    
#     # Check if variant exists (if specified)
#     variant_price = None
#     if cart_item_data.variant_id:
#         variant_result = await db.execute(
#             select(ProductVariant).where(
#                 and_(
#                     ProductVariant.id == cart_item_data.variant_id,
#                     ProductVariant.product_id == cart_item_data.product_id
#                 )
#             )
#         )
#         variant = variant_result.scalar_one_or_none()
#         if not variant:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Product variant not found"
#             )
#         variant_price = variant.price
    
#     # Check if item already exists in cart
#     existing_item_result = await db.execute(
#         select(CartItem).where(
#             and_(
#                 CartItem.user_id == current_user.id,
#                 CartItem.product_id == cart_item_data.product_id,
#                 CartItem.variant_id == cart_item_data.variant_id
#             )
#         )
#     )
#     existing_item = existing_item_result.scalar_one_or_none()
    
#     if existing_item:
#         # Update quantity
#         existing_item.quantity += cart_item_data.quantity
#         await db.commit()
#         await db.refresh(existing_item)
#         return existing_item
    
#     # Create new cart item
#     cart_item = CartItem(
#         user_id=current_user.id,
#         product_id=cart_item_data.product_id,
#         variant_id=cart_item_data.variant_id,
#         quantity=cart_item_data.quantity,
#         price=variant_price or product.price
#     )
    
#     db.add(cart_item)
#     await db.commit()
#     await db.refresh(cart_item)
    
#     # Load product relationship
#     await db.execute(
#         select(CartItem)
#         .options(selectinload(CartItem.product))
#         .where(CartItem.id == cart_item.id)
#     )
#     await db.refresh(cart_item)
    
#     return cart_item


# @router.put("/cart/{cart_item_id}", response_model=CartItemSchema)
# async def update_cart_item(
#     cart_item_id: int,
#     cart_item_update: CartItemUpdate,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update cart item quantity."""
#     result = await db.execute(
#         select(CartItem).where(
#             and_(
#                 CartItem.id == cart_item_id,
#                 CartItem.user_id == current_user.id
#             )
#         )
#     )
#     cart_item = result.scalar_one_or_none()
    
#     if not cart_item:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Cart item not found"
#         )
    
#     if cart_item_update.quantity <= 0:
#         await db.delete(cart_item)
#         await db.commit()
#         return {"message": "Item removed from cart"}
    
#     cart_item.quantity = cart_item_update.quantity
#     await db.commit()
#     await db.refresh(cart_item)
    
#     return cart_item


# @router.delete("/cart/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def remove_from_cart(
#     cart_item_id: int,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Remove item from cart."""
#     result = await db.execute(
#         select(CartItem).where(
#             and_(
#                 CartItem.id == cart_item_id,
#                 CartItem.user_id == current_user.id
#             )
#         )
#     )
#     cart_item = result.scalar_one_or_none()
    
#     if not cart_item:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Cart item not found"
#         )
    
#     await db.delete(cart_item)
#     await db.commit()


# @router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
# async def clear_cart(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Clear all items from cart."""
#     await db.execute(
#         select(CartItem).where(CartItem.user_id == current_user.id)
#     )
    
#     result = await db.execute(
#         select(CartItem).where(CartItem.user_id == current_user.id)
#     )
#     cart_items = result.scalars().all()
    
#     for item in cart_items:
#         await db.delete(item)
    
#     await db.commit()


# # Wishlist Management
# @router.get("/wishlist", response_model=List[WishlistItemSchema])
# async def get_wishlist_items(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get user's wishlist items."""
#     result = await db.execute(
#         select(Wishlist)
#         .options(selectinload(Wishlist.product))
#         .where(Wishlist.user_id == current_user.id)
#         .order_by(Wishlist.created_at.desc())
#     )
#     wishlist_items = result.scalars().all()
#     return wishlist_items


# @router.post("/wishlist", response_model=WishlistItemSchema, status_code=status.HTTP_201_CREATED)
# async def add_to_wishlist(
#     wishlist_item_data: WishlistItemCreate,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Add item to wishlist."""
#     # Check if product exists
#     product_result = await db.execute(
#         select(Product).where(Product.id == wishlist_item_data.product_id)
#     )
#     product = product_result.scalar_one_or_none()
    
#     if not product:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Product not found"
#         )
    
#     # Check if item already exists in wishlist
#     existing_item_result = await db.execute(
#         select(Wishlist).where(
#             and_(
#                 Wishlist.user_id == current_user.id,
#                 Wishlist.product_id == wishlist_item_data.product_id
#             )
#         )
#     )
#     existing_item = existing_item_result.scalar_one_or_none()
    
#     if existing_item:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Item already in wishlist"
#         )
    
#     wishlist_item = Wishlist(
#         user_id=current_user.id,
#         product_id=wishlist_item_data.product_id
#     )
    
#     db.add(wishlist_item)
#     await db.commit()
#     await db.refresh(wishlist_item)
    
#     # Load product relationship
#     await db.execute(
#         select(Wishlist)
#         .options(selectinload(Wishlist.product))
#         .where(Wishlist.id == wishlist_item.id)
#     )
#     await db.refresh(wishlist_item)
    
#     return wishlist_item


# @router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def remove_from_wishlist(
#     product_id: int,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Remove item from wishlist."""
#     result = await db.execute(
#         select(Wishlist).where(
#             and_(
#                 Wishlist.product_id == product_id,
#                 Wishlist.user_id == current_user.id
#             )
#         )
#     )
#     wishlist_item = result.scalar_one_or_none()
    
#     if not wishlist_item:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Wishlist item not found"
#         )
    
#     await db.delete(wishlist_item)
#     await db.commit()


# # Order Management
# @router.get("/", response_model=List[OrderSummary])
# async def get_user_orders(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db),
#     status_filter: Optional[str] = Query(None, description="Filter by order status"),
#     limit: int = Query(20, le=100),
#     offset: int = Query(0, ge=0)
# ):
#     """Get user's orders."""
#     query = select(Order).where(Order.user_id == current_user.id)
    
#     if status_filter:
#         query = query.where(Order.status == status_filter)
    
#     query = query.order_by(desc(Order.created_at)).offset(offset).limit(limit)
    
#     result = await db.execute(query)
#     orders = result.scalars().all()
#     return orders


# @router.get("/{order_id}", response_model=OrderSchema)
# async def get_order(
#     order_id: int,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get specific order details."""
#     result = await db.execute(
#         select(Order)
#         .options(selectinload(Order.order_items))
#         .where(
#             and_(
#                 Order.id == order_id,
#                 Order.user_id == current_user.id
#             )
#         )
#     )
#     order = result.scalar_one_or_none()
    
#     if not order:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Order not found"
#         )
    
#     return order


# @router.post("/", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
# async def create_order(
#     order_data: OrderCreate,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new order from cart."""
#     try:
#         # Get cart items with both product and variant relationships loaded
#         cart_result = await db.execute(
#             select(CartItem)
#             .options(
#                 selectinload(CartItem.product),
#                 selectinload(CartItem.variant)  # Add this line to load variants
#             )
#             .where(CartItem.user_id == current_user.id)
#         )
#         cart_items = cart_result.scalars().all()
        
#         if not cart_items:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Cart is empty"
#             )
        
#         # Get shipping address
#         shipping_address_result = await db.execute(
#             select(Address).where(
#                 and_(
#                     Address.id == order_data.shipping_address_id,
#                     Address.user_id == current_user.id
#                 )
#             )
#         )
#         shipping_address = shipping_address_result.scalar_one_or_none()
        
#         if not shipping_address:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Shipping address not found"
#             )
        
#         # Get billing address (use shipping if not specified)
#         billing_address = shipping_address
#         if order_data.billing_address_id:
#             billing_address_result = await db.execute(
#                 select(Address).where(
#                     and_(
#                         Address.id == order_data.billing_address_id,
#                         Address.user_id == current_user.id
#                     )
#                 )
#             )
#             billing_address = billing_address_result.scalar_one_or_none()
            
#             if not billing_address:
#                 raise HTTPException(
#                     status_code=status.HTTP_404_NOT_FOUND,
#                     detail="Billing address not found"
#                 )
        
#         # Calculate totals
#         subtotal = sum(item.price * item.quantity for item in cart_items)
#         tax_amount = Decimal('0.00')  # Calculate based on your tax logic
#         shipping_cost = Decimal('0.00')  # Calculate based on your shipping logic
#         discount_amount = Decimal('0.00')
        
#         # Apply coupon if provided
#         if order_data.coupon_code:
#             coupon_validation = await validate_coupon(
#                 order_data.coupon_code, subtotal, current_user.id, db
#             )
#             if not coupon_validation.valid:
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail=coupon_validation.message
#                 )
#             discount_amount = coupon_validation.discount_amount
        
#         total_amount = subtotal + tax_amount + shipping_cost - discount_amount
        
#         # Generate order number
#         order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
#         # Create order
#         order = Order(
#             user_id=current_user.id,
#             order_number=order_number,
#             subtotal=subtotal,
#             tax_amount=tax_amount,
#             shipping_cost=shipping_cost,
#             discount_amount=discount_amount,
#             total_amount=total_amount,
            
#             # Shipping address snapshot
#             shipping_first_name=shipping_address.first_name,
#             shipping_last_name=shipping_address.last_name,
#             shipping_company=shipping_address.company,
#             shipping_address_line1=shipping_address.address_line1,
#             shipping_address_line2=shipping_address.address_line2,
#             shipping_city=shipping_address.city,
#             shipping_province=shipping_address.province,
#             shipping_postal_code=shipping_address.postal_code,
#             shipping_country=shipping_address.country,
#             shipping_phone=shipping_address.phone,
            
#             # Billing address snapshot
#             billing_first_name=billing_address.first_name,
#             billing_last_name=billing_address.last_name,
#             billing_company=billing_address.company,
#             billing_address_line1=billing_address.address_line1,
#             billing_address_line2=billing_address.address_line2,
#             billing_city=billing_address.city,
#             billing_province=billing_address.province,
#             billing_postal_code=billing_address.postal_code,
#             billing_country=billing_address.country,
#             billing_phone=billing_address.phone,
            
#             notes=order_data.notes
#         )
        
#         db.add(order)
#         await db.flush()  # Get order ID
        
#         # Create order items with proper null checks
#         for cart_item in cart_items:
#             # Safely get variant attributes
#             variant_name = None
#             variant_sku = None
            
#             if cart_item.variant_id and cart_item.variant:
#                 variant_name = cart_item.variant.name
#                 variant_sku = cart_item.variant.sku
            
#             # Determine SKU (use variant SKU if available, otherwise product SKU)
#             sku = variant_sku if variant_sku else cart_item.product.sku
            
#             order_item = OrderItem(
#                 order_id=order.id,
#                 product_id=cart_item.product_id,
#                 variant_id=cart_item.variant_id,
#                 product_name=cart_item.product.name,
#                 variant_name=variant_name,  # Now safely accessed
#                 sku=sku,  # Now safely determined
#                 quantity=cart_item.quantity,
#                 unit_price=cart_item.price,
#                 total_price=cart_item.price * cart_item.quantity
#             )
#             db.add(order_item)
        
#         # Update coupon usage if applied
#         if order_data.coupon_code:
#             await db.execute(
#                 update(Coupon)
#                 .where(Coupon.code == order_data.coupon_code)
#                 .values(usage_count=Coupon.usage_count + 1)
#             )
        
#         # Clear cart
#         # for cart_item in cart_items:
#         #     await db.delete(cart_item)
        
#         await db.commit()
        
#         # Properly load the order with all relationships
#         result = await db.execute(
#             select(Order)
#             .options(
#                 selectinload(Order.order_items),
#                 selectinload(Order.user)  # If needed by the schema
#             )
#             .where(Order.id == order.id)
#         )
#         order = result.scalar_one()
        
#         return order
        
#     except HTTPException:
#         # Re-raise HTTP exceptions as-is
#         raise
#     except Exception as e:
#         # Log the actual error for debugging
#         import traceback
#         print(f"Error creating order: {str(e)}")
#         print(traceback.format_exc())
        
#         # Rollback the transaction
#         await db.rollback()
        
#         # Return a generic error to the client
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to create order: {str(e)}"
#         )


# # Payment Management
# @router.post("/{order_id}/payments", response_model=PaymentSchema, status_code=status.HTTP_201_CREATED)
# async def create_payment(
#     order_id: int,
#     payment_data: PaymentCreate,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create payment for order."""
#     # Verify order belongs to user
#     order_result = await db.execute(
#         select(Order).where(
#             and_(
#                 Order.id == order_id,
#                 Order.user_id == current_user.id
#             )
#         )
#     )
#     order = order_result.scalar_one_or_none()
    
#     if not order:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Order not found"
#         )
    
#     payment = Payment(
#         order_id=order_id,
#         **payment_data.model_dump()
#     )
    
#     db.add(payment)
#     await db.commit()
#     await db.refresh(payment)
    
#     return payment


# @router.get("/{order_id}/payments", response_model=List[PaymentSchema])
# async def get_order_payments(
#     order_id: int,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get payments for order."""
#     # Verify order belongs to user
#     order_result = await db.execute(
#         select(Order).where(
#             and_(
#                 Order.id == order_id,
#                 Order.user_id == current_user.id
#             )
#         )
#     )
#     order = order_result.scalar_one_or_none()
    
#     if not order:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Order not found"
#         )
    
#     result = await db.execute(
#         select(Payment)
#         .where(Payment.order_id == order_id)
#         .order_by(Payment.created_at.desc())
#     )
#     payments = result.scalars().all()
    
#     return payments


# # Coupon Management
# @router.post("/coupons/validate", response_model=CouponValidation)
# async def validate_coupon_endpoint(
#     coupon_code: str,
#     cart_total: Decimal,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Validate coupon code."""
#     return await validate_coupon(coupon_code, cart_total, current_user.id, db)


# # Helper function for coupon validation
# async def validate_coupon(
#     coupon_code: str,
#     cart_total: Decimal,
#     user_id: int,
#     db: AsyncSession
# ) -> CouponValidation:
#     """Validate coupon and calculate discount."""
#     result = await db.execute(
#         select(Coupon).where(Coupon.code == coupon_code)
#     )
#     coupon = result.scalar_one_or_none()
    
#     if not coupon:
#         return CouponValidation(valid=False, message="Coupon not found")
    
#     if not coupon.is_active:
#         return CouponValidation(valid=False, message="Coupon is not active")
    
#     now = datetime.utcnow()
#     if coupon.starts_at and now < coupon.starts_at:
#         return CouponValidation(valid=False, message="Coupon is not yet active")
    
#     if coupon.expires_at and now > coupon.expires_at:
#         return CouponValidation(valid=False, message="Coupon has expired")
    
#     if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
#         return CouponValidation(valid=False, message="Coupon usage limit reached")
    
#     if coupon.minimum_amount and cart_total < coupon.minimum_amount:
#         return CouponValidation(
#             valid=False,
#             message=f"Minimum order amount of ${coupon.minimum_amount} required"
#         )
    
#     # Calculate discount
#     if coupon.type == "percentage":
#         discount = (cart_total * coupon.value) / 100
#         if coupon.maximum_discount:
#             discount = min(discount, coupon.maximum_discount)
#     elif coupon.type == "fixed_amount":
#         discount = min(coupon.value, cart_total)
#     elif coupon.type == "free_shipping":
#         # This would need shipping cost calculation
#         discount = Decimal('0.00')  # Placeholder
#     else:
#         return CouponValidation(valid=False, message="Invalid coupon type")
    
#     return CouponValidation(
#         valid=True,
#         discount_amount=discount,
#         message="Coupon is valid"
#     )


# __all__ = ["router"]



# # from typing import List, Optional
# # from fastapi import APIRouter, Depends, HTTPException, status, Query
# # from sqlalchemy.ext.asyncio import AsyncSession
# # from sqlalchemy import select, update, and_, or_, desc
# # from sqlalchemy.orm import selectinload
# # from decimal import Decimal
# # from datetime import datetime
# # import uuid

# # from app.database import get_db
# # from app.models.order import Order, OrderItem, CartItem, Wishlist, Payment, Coupon
# # from app.models.product import Product, ProductVariant
# # from app.models.user import User, Address
# # from app.schemas.order import (
# #     Order as OrderSchema,
# #     OrderCreate,
# #     OrderSummary,
# #     CartItem as CartItemSchema,
# #     CartItemCreate,
# #     CartItemUpdate,
# #     WishlistItem as WishlistItemSchema,
# #     WishlistItemCreate,
# #     Payment as PaymentSchema,
# #     PaymentCreate,
# #     Coupon as CouponSchema,
# #     CouponCreate,
# #     CouponUpdate,
# #     CouponValidation
# # )
# # from app.api.deps import get_current_active_user

# # router = APIRouter(prefix="/orders", tags=["Order Management"])


# # # Cart Management
# # @router.get("/cart", response_model=List[CartItemSchema])
# # async def get_cart_items(
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Get user's cart items."""
# #     result = await db.execute(
# #         select(CartItem)
# #         .options(selectinload(CartItem.product))
# #         .where(CartItem.user_id == current_user.id)
# #         .order_by(CartItem.created_at.desc())
# #     )
# #     cart_items = result.scalars().all()
# #     return cart_items


# # @router.post("/cart", response_model=CartItemSchema, status_code=status.HTTP_201_CREATED)
# # async def add_to_cart(
# #     cart_item_data: CartItemCreate,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Add item to cart."""
# #     # Check if product exists
# #     product_result = await db.execute(
# #         select(Product).where(Product.id == cart_item_data.product_id)
# #     )
# #     product = product_result.scalar_one_or_none()
    
# #     if not product:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Product not found"
# #         )
    
# #     # Check if variant exists (if specified)
# #     variant_price = None
# #     if cart_item_data.variant_id:
# #         variant_result = await db.execute(
# #             select(ProductVariant).where(
# #                 and_(
# #                     ProductVariant.id == cart_item_data.variant_id,
# #                     ProductVariant.product_id == cart_item_data.product_id
# #                 )
# #             )
# #         )
# #         variant = variant_result.scalar_one_or_none()
# #         if not variant:
# #             raise HTTPException(
# #                 status_code=status.HTTP_404_NOT_FOUND,
# #                 detail="Product variant not found"
# #             )
# #         variant_price = variant.price
    
# #     # Check if item already exists in cart
# #     existing_item_result = await db.execute(
# #         select(CartItem).where(
# #             and_(
# #                 CartItem.user_id == current_user.id,
# #                 CartItem.product_id == cart_item_data.product_id,
# #                 CartItem.variant_id == cart_item_data.variant_id
# #             )
# #         )
# #     )
# #     existing_item = existing_item_result.scalar_one_or_none()
    
# #     if existing_item:
# #         # Update quantity
# #         existing_item.quantity += cart_item_data.quantity
# #         await db.commit()
# #         await db.refresh(existing_item)
# #         return existing_item
    
# #     # Create new cart item
# #     cart_item = CartItem(
# #         user_id=current_user.id,
# #         product_id=cart_item_data.product_id,
# #         variant_id=cart_item_data.variant_id,
# #         quantity=cart_item_data.quantity,
# #         price=variant_price or product.price
# #     )
    
# #     db.add(cart_item)
# #     await db.commit()
# #     await db.refresh(cart_item)
    
# #     # Load product relationship
# #     await db.execute(
# #         select(CartItem)
# #         .options(selectinload(CartItem.product))
# #         .where(CartItem.id == cart_item.id)
# #     )
# #     await db.refresh(cart_item)
    
# #     return cart_item


# # @router.put("/cart/{cart_item_id}", response_model=CartItemSchema)
# # async def update_cart_item(
# #     cart_item_id: int,
# #     cart_item_update: CartItemUpdate,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Update cart item quantity."""
# #     result = await db.execute(
# #         select(CartItem).where(
# #             and_(
# #                 CartItem.id == cart_item_id,
# #                 CartItem.user_id == current_user.id
# #             )
# #         )
# #     )
# #     cart_item = result.scalar_one_or_none()
    
# #     if not cart_item:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Cart item not found"
# #         )
    
# #     if cart_item_update.quantity <= 0:
# #         await db.delete(cart_item)
# #         await db.commit()
# #         return {"message": "Item removed from cart"}
    
# #     cart_item.quantity = cart_item_update.quantity
# #     await db.commit()
# #     await db.refresh(cart_item)
    
# #     return cart_item


# # @router.delete("/cart/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
# # async def remove_from_cart(
# #     cart_item_id: int,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Remove item from cart."""
# #     result = await db.execute(
# #         select(CartItem).where(
# #             and_(
# #                 CartItem.id == cart_item_id,
# #                 CartItem.user_id == current_user.id
# #             )
# #         )
# #     )
# #     cart_item = result.scalar_one_or_none()
    
# #     if not cart_item:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Cart item not found"
# #         )
    
# #     await db.delete(cart_item)
# #     await db.commit()


# # @router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
# # async def clear_cart(
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Clear all items from cart."""
# #     await db.execute(
# #         select(CartItem).where(CartItem.user_id == current_user.id)
# #     )
    
# #     result = await db.execute(
# #         select(CartItem).where(CartItem.user_id == current_user.id)
# #     )
# #     cart_items = result.scalars().all()
    
# #     for item in cart_items:
# #         await db.delete(item)
    
# #     await db.commit()


# # # Wishlist Management
# # @router.get("/wishlist", response_model=List[WishlistItemSchema])
# # async def get_wishlist_items(
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Get user's wishlist items."""
# #     result = await db.execute(
# #         select(Wishlist)
# #         .options(selectinload(Wishlist.product))
# #         .where(Wishlist.user_id == current_user.id)
# #         .order_by(Wishlist.created_at.desc())
# #     )
# #     wishlist_items = result.scalars().all()
# #     return wishlist_items


# # @router.post("/wishlist", response_model=WishlistItemSchema, status_code=status.HTTP_201_CREATED)
# # async def add_to_wishlist(
# #     wishlist_item_data: WishlistItemCreate,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Add item to wishlist."""
# #     # Check if product exists
# #     product_result = await db.execute(
# #         select(Product).where(Product.id == wishlist_item_data.product_id)
# #     )
# #     product = product_result.scalar_one_or_none()
    
# #     if not product:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Product not found"
# #         )
    
# #     # Check if item already exists in wishlist
# #     existing_item_result = await db.execute(
# #         select(Wishlist).where(
# #             and_(
# #                 Wishlist.user_id == current_user.id,
# #                 Wishlist.product_id == wishlist_item_data.product_id
# #             )
# #         )
# #     )
# #     existing_item = existing_item_result.scalar_one_or_none()
    
# #     if existing_item:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Item already in wishlist"
# #         )
    
# #     wishlist_item = Wishlist(
# #         user_id=current_user.id,
# #         product_id=wishlist_item_data.product_id
# #     )
    
# #     db.add(wishlist_item)
# #     await db.commit()
# #     await db.refresh(wishlist_item)
    
# #     # Load product relationship
# #     await db.execute(
# #         select(Wishlist)
# #         .options(selectinload(Wishlist.product))
# #         .where(Wishlist.id == wishlist_item.id)
# #     )
# #     await db.refresh(wishlist_item)
    
# #     return wishlist_item


# # @router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
# # async def remove_from_wishlist(
# #     product_id: int,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Remove item from wishlist."""
# #     result = await db.execute(
# #         select(Wishlist).where(
# #             and_(
# #                 Wishlist.product_id == product_id,
# #                 Wishlist.user_id == current_user.id
# #             )
# #         )
# #     )
# #     wishlist_item = result.scalar_one_or_none()
    
# #     if not wishlist_item:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Wishlist item not found"
# #         )
    
# #     await db.delete(wishlist_item)
# #     await db.commit()


# # # Order Management
# # @router.get("/", response_model=List[OrderSummary])
# # async def get_user_orders(
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db),
# #     status_filter: Optional[str] = Query(None, description="Filter by order status"),
# #     limit: int = Query(20, le=100),
# #     offset: int = Query(0, ge=0)
# # ):
# #     """Get user's orders."""
# #     query = select(Order).where(Order.user_id == current_user.id)
    
# #     if status_filter:
# #         query = query.where(Order.status == status_filter)
    
# #     query = query.order_by(desc(Order.created_at)).offset(offset).limit(limit)
    
# #     result = await db.execute(query)
# #     orders = result.scalars().all()
# #     return orders


# # @router.get("/{order_id}", response_model=OrderSchema)
# # async def get_order(
# #     order_id: int,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Get specific order details."""
# #     result = await db.execute(
# #         select(Order)
# #         .options(selectinload(Order.order_items))
# #         .where(
# #             and_(
# #                 Order.id == order_id,
# #                 Order.user_id == current_user.id
# #             )
# #         )
# #     )
# #     order = result.scalar_one_or_none()
    
# #     if not order:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Order not found"
# #         )
    
# #     return order


# # @router.post("/", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
# # async def create_order(
# #     order_data: OrderCreate,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Create new order from cart."""
# #     # Get cart items
# #     cart_result = await db.execute(
# #         select(CartItem)
# #         .options(selectinload(CartItem.product))
# #         .where(CartItem.user_id == current_user.id)
# #     )
# #     cart_items = cart_result.scalars().all()
    
# #     if not cart_items:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Cart is empty"
# #         )
    
# #     # Get shipping address
# #     shipping_address_result = await db.execute(
# #         select(Address).where(
# #             and_(
# #                 Address.id == order_data.shipping_address_id,
# #                 Address.user_id == current_user.id
# #             )
# #         )
# #     )
# #     shipping_address = shipping_address_result.scalar_one_or_none()
    
# #     if not shipping_address:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Shipping address not found"
# #         )
    
# #     # Get billing address (use shipping if not specified)
# #     billing_address = shipping_address
# #     if order_data.billing_address_id:
# #         billing_address_result = await db.execute(
# #             select(Address).where(
# #                 and_(
# #                     Address.id == order_data.billing_address_id,
# #                     Address.user_id == current_user.id
# #                 )
# #             )
# #         )
# #         billing_address = billing_address_result.scalar_one_or_none()
        
# #         if not billing_address:
# #             raise HTTPException(
# #                 status_code=status.HTTP_404_NOT_FOUND,
# #                 detail="Billing address not found"
# #             )
    
# #     # Calculate totals
# #     subtotal = sum(item.price * item.quantity for item in cart_items)
# #     tax_amount = Decimal('0.00')  # Calculate based on your tax logic
# #     shipping_cost = Decimal('0.00')  # Calculate based on your shipping logic
# #     discount_amount = Decimal('0.00')
    
# #     # Apply coupon if provided
# #     if order_data.coupon_code:
# #         coupon_validation = await validate_coupon(
# #             order_data.coupon_code, subtotal, current_user.id, db
# #         )
# #         if not coupon_validation.valid:
# #             raise HTTPException(
# #                 status_code=status.HTTP_400_BAD_REQUEST,
# #                 detail=coupon_validation.message
# #             )
# #         discount_amount = coupon_validation.discount_amount
    
# #     total_amount = subtotal + tax_amount + shipping_cost - discount_amount
    
# #     # Generate order number
# #     order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
# #     # Create order
# #     order = Order(
# #         user_id=current_user.id,
# #         order_number=order_number,
# #         subtotal=subtotal,
# #         tax_amount=tax_amount,
# #         shipping_cost=shipping_cost,
# #         discount_amount=discount_amount,
# #         total_amount=total_amount,
        
# #         # Shipping address snapshot
# #         shipping_first_name=shipping_address.first_name,
# #         shipping_last_name=shipping_address.last_name,
# #         shipping_company=shipping_address.company,
# #         shipping_address_line1=shipping_address.address_line1,
# #         shipping_address_line2=shipping_address.address_line2,
# #         shipping_city=shipping_address.city,
# #         shipping_province=shipping_address.province,
# #         shipping_postal_code=shipping_address.postal_code,
# #         shipping_country=shipping_address.country,
# #         shipping_phone=shipping_address.phone,
        
# #         # Billing address snapshot
# #         billing_first_name=billing_address.first_name,
# #         billing_last_name=billing_address.last_name,
# #         billing_company=billing_address.company,
# #         billing_address_line1=billing_address.address_line1,
# #         billing_address_line2=billing_address.address_line2,
# #         billing_city=billing_address.city,
# #         billing_province=billing_address.province,
# #         billing_postal_code=billing_address.postal_code,
# #         billing_country=billing_address.country,
# #         billing_phone=billing_address.phone,
        
# #         notes=order_data.notes
# #     )
    
# #     db.add(order)
# #     await db.flush()  # Get order ID
    
# #     # Create order items
# #     for cart_item in cart_items:
# #         order_item = OrderItem(
# #             order_id=order.id,
# #             product_id=cart_item.product_id,
# #             variant_id=cart_item.variant_id,
# #             product_name=cart_item.product.name,
# #             variant_name=cart_item.variant.name if cart_item.variant else None,
# #             sku=cart_item.variant.sku if cart_item.variant else cart_item.product.sku,
# #             quantity=cart_item.quantity,
# #             unit_price=cart_item.price,
# #             total_price=cart_item.price * cart_item.quantity
# #         )
# #         db.add(order_item)
    
# #     # Update coupon usage if applied
# #     if order_data.coupon_code:
# #         await db.execute(
# #             update(Coupon)
# #             .where(Coupon.code == order_data.coupon_code)
# #             .values(usage_count=Coupon.usage_count + 1)
# #         )
    
# #     # Clear cart
# #     for cart_item in cart_items:
# #         await db.delete(cart_item)
    
# #     await db.commit()
# #     await db.refresh(order)
    
# #     # Load order items
# #     await db.execute(
# #         select(Order)
# #         .options(selectinload(Order.order_items))
# #         .where(Order.id == order.id)
# #     )
# #     await db.refresh(order)
    
# #     return order


# # # Payment Management
# # @router.post("/{order_id}/payments", response_model=PaymentSchema, status_code=status.HTTP_201_CREATED)
# # async def create_payment(
# #     order_id: int,
# #     payment_data: PaymentCreate,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Create payment for order."""
# #     # Verify order belongs to user
# #     order_result = await db.execute(
# #         select(Order).where(
# #             and_(
# #                 Order.id == order_id,
# #                 Order.user_id == current_user.id
# #             )
# #         )
# #     )
# #     order = order_result.scalar_one_or_none()
    
# #     if not order:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Order not found"
# #         )
    
# #     payment = Payment(
# #         order_id=order_id,
# #         **payment_data.model_dump()
# #     )
    
# #     db.add(payment)
# #     await db.commit()
# #     await db.refresh(payment)
    
# #     return payment


# # @router.get("/{order_id}/payments", response_model=List[PaymentSchema])
# # async def get_order_payments(
# #     order_id: int,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Get payments for order."""
# #     # Verify order belongs to user
# #     order_result = await db.execute(
# #         select(Order).where(
# #             and_(
# #                 Order.id == order_id,
# #                 Order.user_id == current_user.id
# #             )
# #         )
# #     )
# #     order = order_result.scalar_one_or_none()
    
# #     if not order:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail="Order not found"
# #         )
    
# #     result = await db.execute(
# #         select(Payment)
# #         .where(Payment.order_id == order_id)
# #         .order_by(Payment.created_at.desc())
# #     )
# #     payments = result.scalars().all()
    
# #     return payments


# # # Coupon Management
# # @router.post("/coupons/validate", response_model=CouponValidation)
# # async def validate_coupon_endpoint(
# #     coupon_code: str,
# #     cart_total: Decimal,
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """Validate coupon code."""
# #     return await validate_coupon(coupon_code, cart_total, current_user.id, db)


# # # Helper function for coupon validation
# # async def validate_coupon(
# #     coupon_code: str,
# #     cart_total: Decimal,
# #     user_id: int,
# #     db: AsyncSession
# # ) -> CouponValidation:
# #     """Validate coupon and calculate discount."""
# #     result = await db.execute(
# #         select(Coupon).where(Coupon.code == coupon_code)
# #     )
# #     coupon = result.scalar_one_or_none()
    
# #     if not coupon:
# #         return CouponValidation(valid=False, message="Coupon not found")
    
# #     if not coupon.is_active:
# #         return CouponValidation(valid=False, message="Coupon is not active")
    
# #     now = datetime.utcnow()
# #     if coupon.starts_at and now < coupon.starts_at:
# #         return CouponValidation(valid=False, message="Coupon is not yet active")
    
# #     if coupon.expires_at and now > coupon.expires_at:
# #         return CouponValidation(valid=False, message="Coupon has expired")
    
# #     if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
# #         return CouponValidation(valid=False, message="Coupon usage limit reached")
    
# #     if coupon.minimum_amount and cart_total < coupon.minimum_amount:
# #         return CouponValidation(
# #             valid=False,
# #             message=f"Minimum order amount of ${coupon.minimum_amount} required"
# #         )
    
# #     # Calculate discount
# #     if coupon.type == "percentage":
# #         discount = (cart_total * coupon.value) / 100
# #         if coupon.maximum_discount:
# #             discount = min(discount, coupon.maximum_discount)
# #     elif coupon.type == "fixed_amount":
# #         discount = min(coupon.value, cart_total)
# #     elif coupon.type == "free_shipping":
# #         # This would need shipping cost calculation
# #         discount = Decimal('0.00')  # Placeholder
# #     else:
# #         return CouponValidation(valid=False, message="Invalid coupon type")
    
# #     return CouponValidation(
# #         valid=True,
# #         discount_amount=discount,
# #         message="Coupon is valid"
# #     )


# # __all__ = ["router"]
