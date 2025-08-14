from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.order import CartItem, Wishlist
from app.models.product import Product, ProductVariant
from app.schemas.order import (
    CartItem as CartItemSchema,
    CartItemCreate,
    CartItemUpdate,
    WishlistItem as WishlistItemSchema,
    WishlistItemCreate
)
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/cart", tags=["Shopping Cart"])


@router.get("", response_model=List[CartItemSchema])
async def get_cart_items(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's cart items."""
    result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product),
            selectinload(CartItem.variant)
        )
        .where(CartItem.user_id == current_user.id)
        .order_by(CartItem.created_at.desc())
    )
    cart_items = result.scalars().all()
    return cart_items


@router.post("", response_model=CartItemSchema, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    item_data: CartItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Add item to cart."""
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == item_data.product_id)
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Verify variant if provided
    variant = None
    if item_data.variant_id:
        variant_result = await db.execute(
            select(ProductVariant).where(ProductVariant.id == item_data.variant_id)
        )
        variant = variant_result.scalar_one_or_none()
        if not variant or variant.product_id != item_data.product_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product variant not found"
            )
    
    # Check if item already exists in cart
    existing_item_result = await db.execute(
        select(CartItem).where(
            CartItem.user_id == current_user.id,
            CartItem.product_id == item_data.product_id,
            CartItem.variant_id == item_data.variant_id
        )
    )
    existing_item = existing_item_result.scalar_one_or_none()
    
    if existing_item:
        # Update quantity
        existing_item.quantity += item_data.quantity
        await db.commit()
        await db.refresh(existing_item)
        return existing_item
    
    # Create new cart item
    price = variant.price if variant and variant.price else product.price
    cart_item = CartItem(
        user_id=current_user.id,
        product_id=item_data.product_id,
        variant_id=item_data.variant_id,
        quantity=item_data.quantity,
        price=price
    )
    
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)
    
    return cart_item


@router.put("/{cart_item_id}", response_model=CartItemSchema)
async def update_cart_item(
    cart_item_id: int,
    item_update: CartItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update cart item quantity."""
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == cart_item_id,
            CartItem.user_id == current_user.id
        )
    )
    cart_item = result.scalar_one_or_none()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )
    
    cart_item.quantity = item_update.quantity
    await db.commit()
    await db.refresh(cart_item)
    
    return cart_item


@router.delete("/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_cart_item(
    cart_item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove item from cart."""
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == cart_item_id,
            CartItem.user_id == current_user.id
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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear all items from cart."""
    await db.execute(
        delete(CartItem).where(CartItem.user_id == current_user.id)
    )
    await db.commit()


# Wishlist endpoints
wishlist_router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


@wishlist_router.get("", response_model=List[WishlistItemSchema])
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


@wishlist_router.post("", response_model=WishlistItemSchema, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    item_data: WishlistItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Add item to wishlist."""
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == item_data.product_id)
    )
    if not product_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if already in wishlist
    existing_result = await db.execute(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.product_id == item_data.product_id
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product already in wishlist"
        )
    
    # Add to wishlist
    wishlist_item = Wishlist(
        user_id=current_user.id,
        product_id=item_data.product_id
    )
    
    db.add(wishlist_item)
    await db.commit()
    await db.refresh(wishlist_item)
    
    return wishlist_item


@wishlist_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove item from wishlist."""
    result = await db.execute(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.product_id == product_id
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


# Include wishlist router in cart router
router.include_router(wishlist_router)