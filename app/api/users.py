from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import get_db
from app.models.user import User, Address, Notification
from app.models.order import CartItem, Wishlist
from app.models.product import Product
from app.schemas.user import (
    User as UserSchema,
    UserUpdate,
    UserProfile,
    Address as AddressSchema,
    AddressCreate,
    AddressUpdate,
    Notification as NotificationSchema
)
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/user", tags=["User Management"])


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile."""
    return current_user


@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile."""
    update_data = user_update.model_dump(exclude_unset=True)
    
    if update_data:
        await db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(current_user)
    
    return current_user


@router.get("/addresses", response_model=List[AddressSchema])
async def get_user_addresses(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user addresses."""
    result = await db.execute(
        select(Address)
        .where(Address.user_id == current_user.id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    addresses = result.scalars().all()
    return addresses


@router.post("/addresses", response_model=AddressSchema, status_code=status.HTTP_201_CREATED)
async def create_address(
    address_data: AddressCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new address."""
    # If this is the first address or marked as default, make it default
    if address_data.is_default:
        # Remove default from other addresses
        await db.execute(
            update(Address)
            .where(Address.user_id == current_user.id)
            .values(is_default=False)
        )
    
    address = Address(
        user_id=current_user.id,
        **address_data.model_dump()
    )
    
    db.add(address)
    await db.commit()
    await db.refresh(address)
    
    return address


@router.put("/addresses/{address_id}", response_model=AddressSchema)
async def update_address(
    address_id: int,
    address_update: AddressUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update address."""
    # Check if address belongs to user
    result = await db.execute(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    update_data = address_update.model_dump(exclude_unset=True)
    
    if update_data.get("is_default"):
        # Remove default from other addresses
        await db.execute(
            update(Address)
            .where(Address.user_id == current_user.id)
            .values(is_default=False)
        )
    
    if update_data:
        await db.execute(
            update(Address)
            .where(Address.id == address_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(address)
    
    return address


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete address."""
    result = await db.execute(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    await db.delete(address)
    await db.commit()


@router.patch("/addresses/{address_id}/default", response_model=AddressSchema)
async def set_default_address(
    address_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Set address as default."""
    # Check if address belongs to user
    result = await db.execute(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Remove default from all addresses
    await db.execute(
        update(Address)
        .where(Address.user_id == current_user.id)
        .values(is_default=False)
    )
    
    # Set this address as default
    address.is_default = True
    await db.commit()
    await db.refresh(address)
    
    return address


@router.get("/notifications", response_model=List[NotificationSchema])
async def get_user_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user notifications."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()
    return notifications


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.is_read = True
    await db.commit()
    
    return {"message": "Notification marked as read"}


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    await db.delete(notification)
    await db.commit()