from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, and_, or_

from sqlalchemy.orm import selectinload

from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.api.deps import require_admin

# Import all site models including hero section
from app.models.site import (
    HeroImage, HeroConfig, HeroButton, HeroPriceTag,
    Feature, Stat, SocialLink, QuickLinkCategory, QuickLink,
    PaymentMethod, ContactInfo, PromoMessage, Supplier, Store,
    StoreService, SearchQuery, TrafficSource, RecentActivity,
    NewsletterSubscriber, EventType, Event, ConversionFunnel
)

router = APIRouter(prefix="/admin/site", tags=["Admin - Site Management"])

# ==================== HERO SECTION SCHEMAS ====================

# Hero Images Schemas
class HeroImageBase(BaseModel):
    image_url: str
    alt_text: Optional[str] = None
    display_order: int = 0
    is_active: bool = True

class HeroImageCreate(HeroImageBase):
    pass

class HeroImageUpdate(BaseModel):
    image_url: Optional[str] = None
    alt_text: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class HeroImageSchema(HeroImageBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Hero Config Schemas
class HeroConfigBase(BaseModel):
    config_name: str
    title_primary: str
    title_secondary: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True

class HeroConfigCreate(HeroConfigBase):
    pass

class HeroConfigUpdate(BaseModel):
    config_name: Optional[str] = None
    title_primary: Optional[str] = None
    title_secondary: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class HeroConfigSchema(HeroConfigBase):
    id: int
    created_at: datetime
    buttons: List['HeroButtonSchema'] = []
    price_tags: List['HeroPriceTagSchema'] = []
    
    class Config:
        from_attributes = True

# Hero Button Schemas
class HeroButtonBase(BaseModel):
    hero_config_id: int
    button_type: str  # 'primary' or 'secondary'
    button_text: str
    button_icon: Optional[str] = None
    button_url: Optional[str] = None
    button_action: Optional[str] = None
    display_order: int = 0
    is_active: bool = True

class HeroButtonCreate(HeroButtonBase):
    pass

class HeroButtonUpdate(BaseModel):
    hero_config_id: Optional[int] = None
    button_type: Optional[str] = None
    button_text: Optional[str] = None
    button_icon: Optional[str] = None
    button_url: Optional[str] = None
    button_action: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class HeroButtonSchema(HeroButtonBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Hero Price Tag Schemas
class HeroPriceTagBase(BaseModel):
    hero_config_id: int
    label: str
    price: str
    currency_code: str = 'USD'
    is_active: bool = True

class HeroPriceTagCreate(HeroPriceTagBase):
    pass

class HeroPriceTagUpdate(BaseModel):
    hero_config_id: Optional[int] = None
    label: Optional[str] = None
    price: Optional[str] = None
    currency_code: Optional[str] = None
    is_active: Optional[bool] = None

class HeroPriceTagSchema(HeroPriceTagBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Features Schemas
class FeatureBase(BaseModel):
    icon: str
    text: str
    subtext: Optional[str] = None
    bg_color: Optional[str] = None
    icon_color: Optional[str] = None

class FeatureCreate(FeatureBase):
    pass

class FeatureUpdate(BaseModel):
    icon: Optional[str] = None
    text: Optional[str] = None
    subtext: Optional[str] = None
    bg_color: Optional[str] = None
    icon_color: Optional[str] = None

class FeatureSchema(FeatureBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Stats Schemas
class StatBase(BaseModel):
    icon: str
    number: str
    label: str
    color: Optional[str] = None

class StatCreate(StatBase):
    pass

class StatUpdate(BaseModel):
    icon: Optional[str] = None
    number: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None

class StatSchema(StatBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Social Links Schemas
class SocialLinkBase(BaseModel):
    icon: str
    href: str
    label: str
    color: Optional[str] = None

class SocialLinkCreate(SocialLinkBase):
    pass

class SocialLinkUpdate(BaseModel):
    icon: Optional[str] = None
    href: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None

class SocialLinkSchema(SocialLinkBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Quick Links Schemas
class QuickLinkCategoryBase(BaseModel):
    category: str
    icon: Optional[str] = None

class QuickLinkCategoryCreate(QuickLinkCategoryBase):
    pass

class QuickLinkCategoryUpdate(BaseModel):
    category: Optional[str] = None
    icon: Optional[str] = None

class QuickLinkCategorySchema(QuickLinkCategoryBase):
    id: int
    created_at: datetime
    quick_links: List['QuickLinkSchema'] = []
    
    class Config:
        from_attributes = True

class QuickLinkBase(BaseModel):
    category_id: int
    name: str
    icon: Optional[str] = None

class QuickLinkCreate(QuickLinkBase):
    pass

class QuickLinkUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    icon: Optional[str] = None

class QuickLinkSchema(QuickLinkBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Payment Methods Schemas
class PaymentMethodBase(BaseModel):
    name: str
    is_active: bool = True

class PaymentMethodCreate(PaymentMethodBase):
    pass

class PaymentMethodUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class PaymentMethodSchema(PaymentMethodBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Contact Info Schemas
class ContactInfoBase(BaseModel):
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    weekday_hours: Optional[str] = None
    weekend_hours: Optional[str] = None
    phone: Optional[str] = None
    phone_href: Optional[str] = None
    email: Optional[str] = None

class ContactInfoCreate(ContactInfoBase):
    pass

class ContactInfoUpdate(ContactInfoBase):
    pass

class ContactInfoSchema(ContactInfoBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Promo Messages Schemas
class PromoMessageBase(BaseModel):
    icon: Optional[str] = None
    text: str
    cta: Optional[str] = None
    is_active: bool = True

class PromoMessageCreate(PromoMessageBase):
    pass

class PromoMessageUpdate(BaseModel):
    icon: Optional[str] = None
    text: Optional[str] = None
    cta: Optional[str] = None
    is_active: Optional[bool] = None

class PromoMessageSchema(PromoMessageBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Suppliers Schemas
class SupplierBase(BaseModel):
    name: str
    logo: Optional[str] = None
    category: Optional[str] = None
    featured: bool = False
    partner_since: Optional[str] = None
    rating: Optional[float] = None
    growth: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    logo: Optional[str] = None
    category: Optional[str] = None
    featured: Optional[bool] = None
    partner_since: Optional[str] = None
    rating: Optional[float] = None
    growth: Optional[str] = None

class SupplierSchema(SupplierBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Store Schemas
class StoreServiceSchema(BaseModel):
    id: int
    store_id: int
    service_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class StoreBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    hours_weekday: Optional[str] = None
    hours_weekend: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    distance: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_open: bool = True
    featured: bool = False

class StoreCreate(StoreBase):
    services: List[str] = []

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    weekday_hours: Optional[str] = None
    weekend_hours: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    distance: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_open: Optional[bool] = None
    featured: Optional[bool] = None
    services: Optional[List[str]] = None

class StoreSchema(StoreBase):
    id: int
    created_at: datetime
    services: List[StoreServiceSchema] = []
    
    class Config:
        from_attributes = True

# Newsletter Subscriber Schemas
class NewsletterSubscriberBase(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True

class NewsletterSubscriberCreate(NewsletterSubscriberBase):
    pass

class NewsletterSubscriberUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None

# class NewsletterSubscriberSchema(NewsletterSubscriberBase):
#     id: int
#     subscribed_at: datetime
#     unsubscribed_at: Optional[datetime] = None
    
#     class Config:
#         from_attributes = True


class NewsletterSubscriberSchema(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    subscribed_at: datetime
    unsubscribed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NewsletterSubscribersResponse(BaseModel):
    items: List[NewsletterSubscriberSchema]
    total: int
    page: int
    per_page: int
    pages: int

# Generic response models
class DeleteResponse(BaseModel):
    message: str
    deleted_count: int = 1

class BulkDeleteResponse(BaseModel):
    message: str
    deleted_count: int


# ==================== HERO IMAGES MANAGEMENT ====================

@router.get("/hero-images", response_model=List[HeroImageSchema])
async def get_all_hero_images(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all hero images."""
    result = await db.execute(
        select(HeroImage).order_by(HeroImage.display_order)
    )
    return result.scalars().all()

@router.post("/hero-images", response_model=HeroImageSchema)
async def create_hero_image(
    image_data: HeroImageCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new hero image."""
    image = HeroImage(**image_data.model_dump())
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image

@router.put("/hero-images/{image_id}", response_model=HeroImageSchema)
async def update_hero_image(
    image_id: int,
    image_update: HeroImageUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update hero image."""
    result = await db.execute(select(HeroImage).where(HeroImage.id == image_id))
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Hero image not found")
    
    update_data = image_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(image, field, value)
    
    await db.commit()
    await db.refresh(image)
    return image

@router.delete("/hero-images/{image_id}", response_model=DeleteResponse)
async def delete_hero_image(
    image_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete hero image."""
    result = await db.execute(select(HeroImage).where(HeroImage.id == image_id))
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Hero image not found")
    
    await db.delete(image)
    await db.commit()
    return DeleteResponse(message="Hero image deleted successfully")

# ==================== HERO CONFIG MANAGEMENT ====================

@router.get("/hero-configs", response_model=List[HeroConfigSchema])
async def get_all_hero_configs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all hero configurations."""
    result = await db.execute(
        select(HeroConfig)
        .options(
            selectinload(HeroConfig.buttons),
            selectinload(HeroConfig.price_tags)
        )
        .order_by(HeroConfig.id)
    )
    return result.scalars().all()

@router.post("/hero-configs", response_model=HeroConfigSchema)
async def create_hero_config(
    config_data: HeroConfigCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new hero configuration."""
    # Check if config name already exists
    existing = await db.execute(
        select(HeroConfig).where(HeroConfig.config_name == config_data.config_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Config name already exists")
    
    config = HeroConfig(**config_data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config

@router.put("/hero-configs/{config_id}", response_model=HeroConfigSchema)
async def update_hero_config(
    config_id: int,
    config_update: HeroConfigUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update hero configuration."""
    result = await db.execute(
        select(HeroConfig)
        .options(
            selectinload(HeroConfig.buttons),
            selectinload(HeroConfig.price_tags)
        )
        .where(HeroConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Hero config not found")
    
    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    return config

@router.delete("/hero-configs/{config_id}", response_model=DeleteResponse)
async def delete_hero_config(
    config_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete hero configuration and all related buttons/price tags."""
    result = await db.execute(select(HeroConfig).where(HeroConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Hero config not found")
    
    await db.delete(config)
    await db.commit()
    return DeleteResponse(message="Hero config deleted successfully")

# ==================== HERO BUTTONS MANAGEMENT ====================

@router.get("/hero-buttons", response_model=List[HeroButtonSchema])
async def get_all_hero_buttons(
    config_id: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all hero buttons, optionally filtered by config."""
    query = select(HeroButton)
    
    if config_id:
        query = query.where(HeroButton.hero_config_id == config_id)
    
    query = query.order_by(HeroButton.hero_config_id, HeroButton.display_order)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/hero-buttons", response_model=HeroButtonSchema)
async def create_hero_button(
    button_data: HeroButtonCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new hero button."""
    # Verify hero config exists
    config = await db.get(HeroConfig, button_data.hero_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Hero config not found")
    
    button = HeroButton(**button_data.model_dump())
    db.add(button)
    await db.commit()
    await db.refresh(button)
    return button

@router.put("/hero-buttons/{button_id}", response_model=HeroButtonSchema)
async def update_hero_button(
    button_id: int,
    button_update: HeroButtonUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update hero button."""
    result = await db.execute(select(HeroButton).where(HeroButton.id == button_id))
    button = result.scalar_one_or_none()
    
    if not button:
        raise HTTPException(status_code=404, detail="Hero button not found")
    
    update_data = button_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(button, field, value)
    
    await db.commit()
    await db.refresh(button)
    return button

@router.delete("/hero-buttons/{button_id}", response_model=DeleteResponse)
async def delete_hero_button(
    button_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete hero button."""
    result = await db.execute(select(HeroButton).where(HeroButton.id == button_id))
    button = result.scalar_one_or_none()
    
    if not button:
        raise HTTPException(status_code=404, detail="Hero button not found")
    
    await db.delete(button)
    await db.commit()
    return DeleteResponse(message="Hero button deleted successfully")

# ==================== HERO PRICE TAGS MANAGEMENT ====================

@router.get("/hero-price-tags", response_model=List[HeroPriceTagSchema])
async def get_all_hero_price_tags(
    config_id: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all hero price tags, optionally filtered by config."""
    query = select(HeroPriceTag)
    
    if config_id:
        query = query.where(HeroPriceTag.hero_config_id == config_id)
    
    query = query.order_by(HeroPriceTag.hero_config_id, HeroPriceTag.id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/hero-price-tags", response_model=HeroPriceTagSchema)
async def create_hero_price_tag(
    price_tag_data: HeroPriceTagCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new hero price tag."""
    # Verify hero config exists
    config = await db.get(HeroConfig, price_tag_data.hero_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Hero config not found")
    
    price_tag = HeroPriceTag(**price_tag_data.model_dump())
    db.add(price_tag)
    await db.commit()
    await db.refresh(price_tag)
    return price_tag

@router.put("/hero-price-tags/{price_tag_id}", response_model=HeroPriceTagSchema)
async def update_hero_price_tag(
    price_tag_id: int,
    price_tag_update: HeroPriceTagUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update hero price tag."""
    result = await db.execute(select(HeroPriceTag).where(HeroPriceTag.id == price_tag_id))
    price_tag = result.scalar_one_or_none()
    
    if not price_tag:
        raise HTTPException(status_code=404, detail="Hero price tag not found")
    
    update_data = price_tag_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(price_tag, field, value)
    
    await db.commit()
    await db.refresh(price_tag)
    return price_tag

@router.delete("/hero-price-tags/{price_tag_id}", response_model=DeleteResponse)
async def delete_hero_price_tag(
    price_tag_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete hero price tag."""
    result = await db.execute(select(HeroPriceTag).where(HeroPriceTag.id == price_tag_id))
    price_tag = result.scalar_one_or_none()
    
    if not price_tag:
        raise HTTPException(status_code=404, detail="Hero price tag not found")
    
    await db.delete(price_tag)
    await db.commit()
    return DeleteResponse(message="Hero price tag deleted successfully")

# ==================== HERO SECTION BULK OPERATIONS ====================

@router.post("/hero-configs/{config_id}/setup-default")
async def setup_default_hero_config(
    config_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Setup default buttons and price tag for a hero config."""
    # Verify config exists
    config = await db.get(HeroConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Hero config not found")
    
    # Create default buttons
    primary_button = HeroButton(
        hero_config_id=config_id,
        button_type="primary",
        button_text="Shop Now",
        button_icon="ArrowRight",
        button_action="shop_now",
        display_order=1
    )
    
    secondary_button = HeroButton(
        hero_config_id=config_id,
        button_type="secondary",
        button_text="View Showcase",
        button_icon="PlayCircle",
        button_action="view_showcase",
        display_order=2
    )
    
    # Create default price tag
    price_tag = HeroPriceTag(
        hero_config_id=config_id,
        label="FROM",
        price="$499",
        currency_code="USD"
    )
    
    db.add_all([primary_button, secondary_button, price_tag])
    await db.commit()
    
    return {
        "message": "Default hero config setup completed",
        "buttons_created": 2,
        "price_tags_created": 1
    }

@router.post("/hero-configs/{config_id}/duplicate")
async def duplicate_hero_config(
    config_id: int,
    new_config_name: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Duplicate a hero config with all its buttons and price tags."""
    # Get original config
    result = await db.execute(
        select(HeroConfig)
        .options(
            selectinload(HeroConfig.buttons),
            selectinload(HeroConfig.price_tags)
        )
        .where(HeroConfig.id == config_id)
    )
    original_config = result.scalar_one_or_none()
    
    if not original_config:
        raise HTTPException(status_code=404, detail="Hero config not found")
    
    # Check if new name already exists
    existing = await db.execute(
        select(HeroConfig).where(HeroConfig.config_name == new_config_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Config name already exists")
    
    # Create new config
    new_config = HeroConfig(
        config_name=new_config_name,
        title_primary=original_config.title_primary,
        title_secondary=original_config.title_secondary,
        subtitle=original_config.subtitle,
        description=original_config.description,
        is_active=False  # Start as inactive
    )
    db.add(new_config)
    await db.flush()  # Get the new config ID
    
    # Duplicate buttons
    for button in original_config.buttons:
        new_button = HeroButton(
            hero_config_id=new_config.id,
            button_type=button.button_type,
            button_text=button.button_text,
            button_icon=button.button_icon,
            button_url=button.button_url,
            button_action=button.button_action,
            display_order=button.display_order,
            is_active=button.is_active
        )
        db.add(new_button)
    
    # Duplicate price tags
    for price_tag in original_config.price_tags:
        new_price_tag = HeroPriceTag(
            hero_config_id=new_config.id,
            label=price_tag.label,
            price=price_tag.price,
            currency_code=price_tag.currency_code,
            is_active=price_tag.is_active
        )
        db.add(new_price_tag)
    
    await db.commit()
    await db.refresh(new_config)
    
    return {
        "message": "Hero config duplicated successfully",
        "new_config_id": new_config.id,
        "new_config_name": new_config_name
    }


# ==================== FEATURES MANAGEMENT ====================

@router.get("/features", response_model=List[FeatureSchema])
async def get_all_features(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all features."""
    result = await db.execute(select(Feature).order_by(Feature.id))
    return result.scalars().all()

@router.post("/features", response_model=FeatureSchema)
async def create_feature(
    feature_data: FeatureCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new feature."""
    feature = Feature(**feature_data.model_dump())
    db.add(feature)
    await db.commit()
    await db.refresh(feature)
    return feature

@router.put("/features/{feature_id}", response_model=FeatureSchema)
async def update_feature(
    feature_id: int,
    feature_update: FeatureUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update feature."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    update_data = feature_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(feature, field, value)
    
    await db.commit()
    await db.refresh(feature)
    return feature

@router.delete("/features/{feature_id}", response_model=DeleteResponse)
async def delete_feature(
    feature_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete feature."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    await db.delete(feature)
    await db.commit()
    return DeleteResponse(message="Feature deleted successfully")

# ==================== STATS MANAGEMENT ====================

@router.get("/stats", response_model=List[StatSchema])
async def get_all_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all stats."""
    result = await db.execute(select(Stat).order_by(Stat.id))
    return result.scalars().all()

@router.post("/stats", response_model=StatSchema)
async def create_stat(
    stat_data: StatCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new stat."""
    stat = Stat(**stat_data.model_dump())
    db.add(stat)
    await db.commit()
    await db.refresh(stat)
    return stat

@router.put("/stats/{stat_id}", response_model=StatSchema)
async def update_stat(
    stat_id: int,
    stat_update: StatUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update stat."""
    result = await db.execute(select(Stat).where(Stat.id == stat_id))
    stat = result.scalar_one_or_none()
    
    if not stat:
        raise HTTPException(status_code=404, detail="Stat not found")
    
    update_data = stat_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(stat, field, value)
    
    await db.commit()
    await db.refresh(stat)
    return stat

@router.delete("/stats/{stat_id}", response_model=DeleteResponse)
async def delete_stat(
    stat_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete stat."""
    result = await db.execute(select(Stat).where(Stat.id == stat_id))
    stat = result.scalar_one_or_none()
    
    if not stat:
        raise HTTPException(status_code=404, detail="Stat not found")
    
    await db.delete(stat)
    await db.commit()
    return DeleteResponse(message="Stat deleted successfully")

# ==================== SOCIAL LINKS MANAGEMENT ====================

@router.get("/social-links", response_model=List[SocialLinkSchema])
async def get_all_social_links(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all social links."""
    result = await db.execute(select(SocialLink).order_by(SocialLink.id))
    return result.scalars().all()

@router.post("/social-links", response_model=SocialLinkSchema)
async def create_social_link(
    link_data: SocialLinkCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new social link."""
    link = SocialLink(**link_data.model_dump())
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link

@router.put("/social-links/{link_id}", response_model=SocialLinkSchema)
async def update_social_link(
    link_id: int,
    link_update: SocialLinkUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update social link."""
    result = await db.execute(select(SocialLink).where(SocialLink.id == link_id))
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Social link not found")
    
    update_data = link_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)
    
    await db.commit()
    await db.refresh(link)
    return link

@router.delete("/social-links/{link_id}", response_model=DeleteResponse)
async def delete_social_link(
    link_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete social link."""
    result = await db.execute(select(SocialLink).where(SocialLink.id == link_id))
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Social link not found")
    
    await db.delete(link)
    await db.commit()
    return DeleteResponse(message="Social link deleted successfully")

# ==================== QUICK LINKS MANAGEMENT ====================

@router.get("/quick-link-categories", response_model=List[QuickLinkCategorySchema])
async def get_all_quick_link_categories(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all quick link categories with their links."""
    result = await db.execute(
        select(QuickLinkCategory)
        .options(selectinload(QuickLinkCategory.quick_links))
        .order_by(QuickLinkCategory.id)
    )
    return result.scalars().all()

@router.post("/quick-link-categories", response_model=QuickLinkCategorySchema)
async def create_quick_link_category(
    category_data: QuickLinkCategoryCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new quick link category."""
    category = QuickLinkCategory(**category_data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category

@router.put("/quick-link-categories/{category_id}", response_model=QuickLinkCategorySchema)
async def update_quick_link_category(
    category_id: int,
    category_update: QuickLinkCategoryUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update quick link category."""
    result = await db.execute(select(QuickLinkCategory).where(QuickLinkCategory.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Quick link category not found")
    
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    await db.commit()
    await db.refresh(category)
    return category

@router.delete("/quick-link-categories/{category_id}", response_model=DeleteResponse)
async def delete_quick_link_category(
    category_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete quick link category and all its links."""
    result = await db.execute(select(QuickLinkCategory).where(QuickLinkCategory.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Quick link category not found")
    
    await db.delete(category)
    await db.commit()
    return DeleteResponse(message="Quick link category deleted successfully")

@router.post("/quick-links", response_model=QuickLinkSchema)
async def create_quick_link(
    link_data: QuickLinkCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new quick link."""
    # Verify category exists
    category = await db.get(QuickLinkCategory, link_data.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Quick link category not found")
    
    link = QuickLink(**link_data.model_dump())
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link

@router.put("/quick-links/{link_id}", response_model=QuickLinkSchema)
async def update_quick_link(
    link_id: int,
    link_update: QuickLinkUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update quick link."""
    result = await db.execute(select(QuickLink).where(QuickLink.id == link_id))
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Quick link not found")
    
    update_data = link_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)
    
    await db.commit()
    await db.refresh(link)
    return link

@router.delete("/quick-links/{link_id}", response_model=DeleteResponse)
async def delete_quick_link(
    link_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete quick link."""
    result = await db.execute(select(QuickLink).where(QuickLink.id == link_id))
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Quick link not found")
    
    await db.delete(link)
    await db.commit()
    return DeleteResponse(message="Quick link deleted successfully")

# ==================== PAYMENT METHODS MANAGEMENT ====================

@router.get("/payment-methods", response_model=List[PaymentMethodSchema])
async def get_all_payment_methods(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all payment methods."""
    result = await db.execute(select(PaymentMethod).order_by(PaymentMethod.id))
    return result.scalars().all()

@router.post("/payment-methods", response_model=PaymentMethodSchema)
async def create_payment_method(
    method_data: PaymentMethodCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new payment method."""
    method = PaymentMethod(**method_data.model_dump())
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method

@router.put("/payment-methods/{method_id}", response_model=PaymentMethodSchema)
async def update_payment_method(
    method_id: int,
    method_update: PaymentMethodUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update payment method."""
    result = await db.execute(select(PaymentMethod).where(PaymentMethod.id == method_id))
    method = result.scalar_one_or_none()
    
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    update_data = method_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(method, field, value)
    
    await db.commit()
    await db.refresh(method)
    return method

@router.delete("/payment-methods/{method_id}", response_model=DeleteResponse)
async def delete_payment_method(
    method_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete payment method."""
    result = await db.execute(select(PaymentMethod).where(PaymentMethod.id == method_id))
    method = result.scalar_one_or_none()
    
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    await db.delete(method)
    await db.commit()
    return DeleteResponse(message="Payment method deleted successfully")

# ==================== CONTACT INFO MANAGEMENT ====================

@router.get("/contact-info", response_model=ContactInfoSchema)
async def get_contact_info(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get contact info (should have only one record)."""
    result = await db.execute(select(ContactInfo).limit(1))
    contact_info = result.scalar_one_or_none()
    
    if not contact_info:
        raise HTTPException(status_code=404, detail="Contact info not found")
    
    return contact_info

# @router.post("/contact-info", response_model=ContactInfoSchema)
# async def create_or_update_contact_info(
#     contact_data: ContactInfoCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create or update contact info (only one record allowed)."""
#     result = await db.execute(select(ContactInfo).limit(1))
#     contact_info = result.scalar_one_or_none()
    
#     if contact_info:
#         # Update existing
#         update_data = contact_data.model_dump(exclude_unset=True)
#         for field, value in update_data.items():
#             setattr(contact_info, field, value)
#     else:
#         # Create new
#         contact_info = ContactInfo(**contact_data.model_dump())
#         db.add(contact_info)
    
#     await db.commit()
#     await db.refresh(contact_info)
#     return contact_info

@router.post("/contact-info", response_model=ContactInfoSchema)
async def create_or_update_contact_info(
    contact_data: ContactInfoCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create or update contact info (only one record allowed)."""
    result = await db.execute(select(ContactInfo).limit(1))
    contact_info = result.scalar_one_or_none()
    
    if contact_info:
        # Update existing
        update_data = contact_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contact_info, field, value)
    else:
        # Create new
        contact_info = ContactInfo(**contact_data.model_dump())
        db.add(contact_info)
    
    await db.commit()
    await db.refresh(contact_info)
    return contact_info


@router.put("/contact-info/{contact_id}", response_model=ContactInfoSchema)
async def update_contact_info_by_id(
    contact_id: int,
    contact_data: ContactInfoCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update contact info by ID."""
    result = await db.execute(select(ContactInfo).where(ContactInfo.id == contact_id))
    contact_info = result.scalar_one_or_none()
    
    if not contact_info:
        raise HTTPException(status_code=404, detail="Contact info not found")
    
    # Update existing
    update_data = contact_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact_info, field, value)
    
    await db.commit()
    await db.refresh(contact_info)
    return contact_info

# ==================== PROMO MESSAGES MANAGEMENT ====================

@router.get("/promo-messages", response_model=List[PromoMessageSchema])
async def get_all_promo_messages(
    is_active: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all promo messages."""
    query = select(PromoMessage)
    
    if is_active is not None:
        query = query.where(PromoMessage.is_active == is_active)
    
    query = query.order_by(PromoMessage.id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/promo-messages", response_model=PromoMessageSchema)
async def create_promo_message(
    promo_data: PromoMessageCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new promo message."""
    promo = PromoMessage(**promo_data.model_dump())
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo

@router.put("/promo-messages/{promo_id}", response_model=PromoMessageSchema)
async def update_promo_message(
    promo_id: int,
    promo_update: PromoMessageUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update promo message."""
    result = await db.execute(select(PromoMessage).where(PromoMessage.id == promo_id))
    promo = result.scalar_one_or_none()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Promo message not found")
    
    update_data = promo_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(promo, field, value)
    
    await db.commit()
    await db.refresh(promo)
    return promo

@router.delete("/promo-messages/{promo_id}", response_model=DeleteResponse)
async def delete_promo_message(
    promo_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete promo message."""
    result = await db.execute(select(PromoMessage).where(PromoMessage.id == promo_id))
    promo = result.scalar_one_or_none()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Promo message not found")
    
    await db.delete(promo)
    await db.commit()
    return DeleteResponse(message="Promo message deleted successfully")

# ==================== SUPPLIERS MANAGEMENT ====================

@router.get("/suppliers", response_model=List[SupplierSchema])
async def get_all_suppliers(
    featured: Optional[bool] = None,
    category: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all suppliers."""
    query = select(Supplier)
    
    if featured is not None:
        query = query.where(Supplier.featured == featured)
    
    if category:
        query = query.where(Supplier.category == category)
    
    query = query.order_by(Supplier.name)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/suppliers", response_model=SupplierSchema)
async def create_supplier(
    supplier_data: SupplierCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new supplier."""
    supplier = Supplier(**supplier_data.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier

@router.put("/suppliers/{supplier_id}", response_model=SupplierSchema)
async def update_supplier(
    supplier_id: int,
    supplier_update: SupplierUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update supplier."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    update_data = supplier_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(supplier, field, value)
    
    await db.commit()
    await db.refresh(supplier)
    return supplier

@router.delete("/suppliers/{supplier_id}", response_model=DeleteResponse)
async def delete_supplier(
    supplier_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete supplier."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    await db.delete(supplier)
    await db.commit()
    return DeleteResponse(message="Supplier deleted successfully")

# ==================== STORES MANAGEMENT ====================

@router.get("/stores", response_model=List[StoreSchema])
async def get_all_stores(
    featured: Optional[bool] = None,
    is_open: Optional[bool] = None,
    city: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all stores with their services."""
    query = select(Store).options(selectinload(Store.services))
    
    if featured is not None:
        query = query.where(Store.featured == featured)
    
    if is_open is not None:
        query = query.where(Store.is_open == is_open)
    
    if city:
        query = query.where(Store.city.ilike(f"%{city}%"))
    
    query = query.order_by(Store.name)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/stores", response_model=StoreSchema)
async def create_store(
    store_data: StoreCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new store with services."""
    store_dict = store_data.model_dump()
    services = store_dict.pop('services', [])
    
    store = Store(**store_dict)
    db.add(store)
    await db.flush()  # Get the store ID
    
    # Add services
    for service_name in services:
        service = StoreService(store_id=store.id, service_name=service_name)
        db.add(service)
    
    await db.commit()
    await db.refresh(store)
    
    # Load with services
    result = await db.execute(
        select(Store).options(selectinload(Store.services)).where(Store.id == store.id)
    )
    return result.scalar_one()

@router.put("/stores/{store_id}", response_model=StoreSchema)
async def update_store(
    store_id: int,
    store_update: StoreUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update store and its services."""
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    update_data = store_update.model_dump(exclude_unset=True)
    services = update_data.pop('services', None)
    
    # Update store fields
    for field, value in update_data.items():
        setattr(store, field, value)
    
    # Update services if provided
    if services is not None:
        # Delete existing services
        await db.execute(delete(StoreService).where(StoreService.store_id == store_id))
        
        # Add new services
        for service_name in services:
            service = StoreService(store_id=store_id, service_name=service_name)
            db.add(service)
    
    await db.commit()
    
    # Load with services
    result = await db.execute(
        select(Store).options(selectinload(Store.services)).where(Store.id == store_id)
    )
    return result.scalar_one()

@router.delete("/stores/{store_id}", response_model=DeleteResponse)
async def delete_store(
    store_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete store and its services."""
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    await db.delete(store)
    await db.commit()
    return DeleteResponse(message="Store deleted successfully")

# ==================== NEWSLETTER SUBSCRIBERS MANAGEMENT ====================

# @router.get("/newsletter-subscribers", response_model=Dict[str, Any])
# async def get_newsletter_subscribers(
#     page: int = Query(1, ge=1),
#     per_page: int = Query(50, ge=1, le=200),
#     is_active: Optional[bool] = None,
#     search: Optional[str] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get newsletter subscribers with pagination."""
#     query = select(NewsletterSubscriber)
    
#     if is_active is not None:
#         query = query.where(NewsletterSubscriber.is_active == is_active)
    
#     if search:
#         query = query.where(
#             or_(
#                 NewsletterSubscriber.email.ilike(f"%{search}%"),
#                 NewsletterSubscriber.first_name.ilike(f"%{search}%"),
#                 NewsletterSubscriber.last_name.ilike(f"%{search}%")
#             )
#         )
    
#     # Count total
#     count_query = select(func.count()).select_from(query.subquery())
#     total_result = await db.execute(count_query)
#     total = total_result.scalar()
    
#     # Apply pagination
#     offset = (page - 1) * per_page
#     query = query.order_by(NewsletterSubscriber.subscribed_at.desc()).offset(offset).limit(per_page)
    
#     result = await db.execute(query)
#     subscribers = result.scalars().all()
    
#     return {
#         "items": subscribers,
#         "total": total,
#         "page": page,
#         "per_page": per_page,
#         "pages": (total + per_page - 1) // per_page
#     }


# Then, update your API endpoint
@router.get("/newsletter-subscribers", response_model=NewsletterSubscribersResponse)
async def get_newsletter_subscribers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get newsletter subscribers with pagination."""
    query = select(NewsletterSubscriber)
    
    if is_active is not None:
        query = query.where(NewsletterSubscriber.is_active == is_active)
    
    if search:
        query = query.where(
            or_(
                NewsletterSubscriber.email.ilike(f"%{search}%"),
                NewsletterSubscriber.first_name.ilike(f"%{search}%"),
                NewsletterSubscriber.last_name.ilike(f"%{search}%")
            )
        )
    
    # Count total
    count_query = select(func.count(NewsletterSubscriber.id))
    if is_active is not None:
        count_query = count_query.where(NewsletterSubscriber.is_active == is_active)
    if search:
        count_query = count_query.where(
            or_(
                NewsletterSubscriber.email.ilike(f"%{search}%"),
                NewsletterSubscriber.first_name.ilike(f"%{search}%"),
                NewsletterSubscriber.last_name.ilike(f"%{search}%")
            )
        )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(NewsletterSubscriber.subscribed_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    subscribers = result.scalars().all()
    
    return NewsletterSubscribersResponse(
        items=subscribers,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page
    )


@router.post("/newsletter-subscribers", response_model=NewsletterSubscriberSchema)
async def add_newsletter_subscriber(
    subscriber_data: NewsletterSubscriberCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add newsletter subscriber."""
    # Check if email exists
    existing = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == subscriber_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already subscribed")
    
    subscriber = NewsletterSubscriber(**subscriber_data.model_dump())
    db.add(subscriber)
    await db.commit()
    await db.refresh(subscriber)
    return subscriber

@router.put("/newsletter-subscribers/{subscriber_id}", response_model=NewsletterSubscriberSchema)
async def update_newsletter_subscriber(
    subscriber_id: int,
    subscriber_update: NewsletterSubscriberUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update newsletter subscriber."""
    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.id == subscriber_id)
    )
    subscriber = result.scalar_one_or_none()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    update_data = subscriber_update.model_dump(exclude_unset=True)
    
    # Handle unsubscribe
    if 'is_active' in update_data and not update_data['is_active'] and subscriber.is_active:
        subscriber.unsubscribed_at = datetime.utcnow()
    elif 'is_active' in update_data and update_data['is_active'] and not subscriber.is_active:
        subscriber.unsubscribed_at = None
    
    for field, value in update_data.items():
        setattr(subscriber, field, value)
    
    await db.commit()
    await db.refresh(subscriber)
    return subscriber

@router.delete("/newsletter-subscribers/{subscriber_id}", response_model=DeleteResponse)
async def delete_newsletter_subscriber(
    subscriber_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete newsletter subscriber."""
    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.id == subscriber_id)
    )
    subscriber = result.scalar_one_or_none()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    await db.delete(subscriber)
    await db.commit()
    return DeleteResponse(message="Subscriber deleted successfully")

@router.post("/newsletter-subscribers/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_newsletter_subscribers(
    subscriber_ids: List[int],
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk delete newsletter subscribers."""
    result = await db.execute(
        delete(NewsletterSubscriber).where(NewsletterSubscriber.id.in_(subscriber_ids))
    )
    await db.commit()
    return BulkDeleteResponse(
        message=f"Deleted {result.rowcount} subscribers",
        deleted_count=result.rowcount
    )


# ==================== ANALYTICS DASHBOARD ====================

@router.get("/analytics/search-queries")
async def get_search_queries(
    limit: int = Query(100, le=1000),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get search queries analytics."""
    query = select(
        SearchQuery.query_text,
        func.count(SearchQuery.id).label('count'),
        func.avg(SearchQuery.results_count).label('avg_results')
    ).group_by(SearchQuery.query_text)
    
    if start_date:
        query = query.where(SearchQuery.created_at >= start_date)
    
    if end_date:
        query = query.where(SearchQuery.created_at <= end_date)
    
    query = query.order_by(func.count(SearchQuery.id).desc()).limit(limit)
    
    result = await db.execute(query)
    return [
        {
            "query": row.query_text,
            "count": row.count,
            "avg_results": float(row.avg_results) if row.avg_results else 0
        }
        for row in result
    ]

# ==================== EVENTS ANALYTICS ====================

@router.get("/analytics/events/summary")
async def get_events_summary(
    limit: int = Query(100, le=1000),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get events summary analytics by event type."""
    query = select(
        EventType.event_name,
        EventType.category,
        func.count(Event.id).label('count'),
        func.count(func.distinct(Event.user_id)).label('unique_users'),
        func.count(func.distinct(Event.session_id)).label('unique_sessions')
    ).join(Event, EventType.id == Event.event_type_id).group_by(
        EventType.id, EventType.event_name, EventType.category
    )
    
    if start_date:
        query = query.where(Event.created_at >= start_date)
    
    if end_date:
        query = query.where(Event.created_at <= end_date)
    
    query = query.order_by(func.count(Event.id).desc()).limit(limit)
    
    result = await db.execute(query)
    return [
        {
            "event_name": row.event_name,
            "category": row.category,
            "count": row.count,
            "unique_users": row.unique_users,
            "unique_sessions": row.unique_sessions
        }
        for row in result
    ]


@router.get("/analytics/traffic-sources")
async def get_traffic_sources(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get traffic sources analytics."""
    query = select(TrafficSource)
    
    if start_date:
        query = query.where(TrafficSource.created_at >= start_date)
    
    if end_date:
        query = query.where(TrafficSource.created_at <= end_date)
    
    query = query.order_by(TrafficSource.sessions.desc())
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/analytics/conversion-funnel")
async def get_conversion_funnel(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get conversion funnel data."""
    query = select(ConversionFunnel)
    
    if start_date:
        query = query.where(ConversionFunnel.date >= start_date.date())
    
    if end_date:
        query = query.where(ConversionFunnel.date <= end_date.date())
    
    query = query.order_by(ConversionFunnel.date.desc())
    
    result = await db.execute(query)
    data = result.scalars().all()
    
    # Calculate conversion rates
    funnel_data = []
    for record in data:
        funnel_data.append({
            "date": record.date,
            "visitors": record.visitors,
            "product_views": record.product_views,
            "add_to_cart": record.add_to_cart,
            "add_to_wishlist": record.add_to_wishlist,
            "checkout": record.checkout,
            "purchase": record.purchase,
            "conversion_rates": {
                "visitor_to_view": (record.product_views / record.visitors * 100) if record.visitors > 0 else 0,
                "view_to_cart": (record.add_to_cart / record.product_views * 100) if record.product_views > 0 else 0,
                "cart_to_checkout": (record.checkout / record.add_to_cart * 100) if record.add_to_cart > 0 else 0,
                "checkout_to_purchase": (record.purchase / record.checkout * 100) if record.checkout > 0 else 0,
                "overall": (record.purchase / record.visitors * 100) if record.visitors > 0 else 0
            }
        })
    
    return funnel_data

# Export router
__all__ = ["router"]



# from typing import List, Optional, Dict, Any
# from datetime import datetime
# from fastapi import APIRouter, Depends, HTTPException, status, Query
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, delete, update, func, and_, or_

# from sqlalchemy.orm import selectinload

# from pydantic import BaseModel, Field
# from app.database import get_db
# from app.models.user import User
# from app.api.deps import require_admin

# # Import your site static models (you'll need to create these)
# from app.models.site import (
#     Feature, Stat, SocialLink, QuickLinkCategory, QuickLink,
#     PaymentMethod, ContactInfo, PromoMessage, Supplier, Store,
#     StoreService, SearchQuery, TrafficSource, RecentActivity,
#     NewsletterSubscriber, EventType, Event, ConversionFunnel
# )

# router = APIRouter(prefix="/admin/site", tags=["Admin - Site Management"])

# # ==================== SCHEMAS ====================

# # Features Schemas
# class FeatureBase(BaseModel):
#     icon: str
#     text: str
#     subtext: Optional[str] = None
#     bg_color: Optional[str] = None
#     icon_color: Optional[str] = None

# class FeatureCreate(FeatureBase):
#     pass

# class FeatureUpdate(BaseModel):
#     icon: Optional[str] = None
#     text: Optional[str] = None
#     subtext: Optional[str] = None
#     bg_color: Optional[str] = None
#     icon_color: Optional[str] = None

# class FeatureSchema(FeatureBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Stats Schemas
# class StatBase(BaseModel):
#     icon: str
#     number: str
#     label: str
#     color: Optional[str] = None

# class StatCreate(StatBase):
#     pass

# class StatUpdate(BaseModel):
#     icon: Optional[str] = None
#     number: Optional[str] = None
#     label: Optional[str] = None
#     color: Optional[str] = None

# class StatSchema(StatBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Social Links Schemas
# class SocialLinkBase(BaseModel):
#     icon: str
#     href: str
#     label: str
#     color: Optional[str] = None

# class SocialLinkCreate(SocialLinkBase):
#     pass

# class SocialLinkUpdate(BaseModel):
#     icon: Optional[str] = None
#     href: Optional[str] = None
#     label: Optional[str] = None
#     color: Optional[str] = None

# class SocialLinkSchema(SocialLinkBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Quick Links Schemas
# class QuickLinkCategoryBase(BaseModel):
#     category: str
#     icon: Optional[str] = None

# class QuickLinkCategoryCreate(QuickLinkCategoryBase):
#     pass

# class QuickLinkCategoryUpdate(BaseModel):
#     category: Optional[str] = None
#     icon: Optional[str] = None

# class QuickLinkCategorySchema(QuickLinkCategoryBase):
#     id: int
#     created_at: datetime
#     quick_links: List['QuickLinkSchema'] = []
    
#     class Config:
#         from_attributes = True

# class QuickLinkBase(BaseModel):
#     category_id: int
#     name: str
#     icon: Optional[str] = None

# class QuickLinkCreate(QuickLinkBase):
#     pass

# class QuickLinkUpdate(BaseModel):
#     category_id: Optional[int] = None
#     name: Optional[str] = None
#     icon: Optional[str] = None

# class QuickLinkSchema(QuickLinkBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Payment Methods Schemas
# class PaymentMethodBase(BaseModel):
#     name: str
#     is_active: bool = True

# class PaymentMethodCreate(PaymentMethodBase):
#     pass

# class PaymentMethodUpdate(BaseModel):
#     name: Optional[str] = None
#     is_active: Optional[bool] = None

# class PaymentMethodSchema(PaymentMethodBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Contact Info Schemas
# class ContactInfoBase(BaseModel):
#     address_line1: Optional[str] = None
#     address_line2: Optional[str] = None
#     weekday_hours: Optional[str] = None
#     weekend_hours: Optional[str] = None
#     phone: Optional[str] = None
#     phone_href: Optional[str] = None
#     email: Optional[str] = None

# class ContactInfoCreate(ContactInfoBase):
#     pass

# class ContactInfoUpdate(ContactInfoBase):
#     pass

# class ContactInfoSchema(ContactInfoBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Promo Messages Schemas
# class PromoMessageBase(BaseModel):
#     icon: Optional[str] = None
#     text: str
#     cta: Optional[str] = None
#     is_active: bool = True

# class PromoMessageCreate(PromoMessageBase):
#     pass

# class PromoMessageUpdate(BaseModel):
#     icon: Optional[str] = None
#     text: Optional[str] = None
#     cta: Optional[str] = None
#     is_active: Optional[bool] = None

# class PromoMessageSchema(PromoMessageBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Suppliers Schemas
# class SupplierBase(BaseModel):
#     name: str
#     logo: Optional[str] = None
#     category: Optional[str] = None
#     featured: bool = False
#     partner_since: Optional[str] = None
#     rating: Optional[float] = None
#     growth: Optional[str] = None

# class SupplierCreate(SupplierBase):
#     pass

# class SupplierUpdate(BaseModel):
#     name: Optional[str] = None
#     logo: Optional[str] = None
#     category: Optional[str] = None
#     featured: Optional[bool] = None
#     partner_since: Optional[str] = None
#     rating: Optional[float] = None
#     growth: Optional[str] = None

# class SupplierSchema(SupplierBase):
#     id: int
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# # Store Schemas
# class StoreServiceSchema(BaseModel):
#     id: int
#     store_id: int
#     service_name: str
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# class StoreBase(BaseModel):
#     name: str
#     address: Optional[str] = None
#     city: Optional[str] = None
#     state: Optional[str] = None
#     zip: Optional[str] = None
#     phone: Optional[str] = None
#     weekday_hours: Optional[str] = None
#     weekend_hours: Optional[str] = None
#     rating: Optional[float] = None
#     reviews: Optional[int] = None
#     distance: Optional[str] = None
#     latitude: Optional[float] = None
#     longitude: Optional[float] = None
#     is_open: bool = True
#     featured: bool = False

# class StoreCreate(StoreBase):
#     services: List[str] = []

# class StoreUpdate(BaseModel):
#     name: Optional[str] = None
#     address: Optional[str] = None
#     city: Optional[str] = None
#     state: Optional[str] = None
#     zip: Optional[str] = None
#     phone: Optional[str] = None
#     weekday_hours: Optional[str] = None
#     weekend_hours: Optional[str] = None
#     rating: Optional[float] = None
#     reviews: Optional[int] = None
#     distance: Optional[str] = None
#     latitude: Optional[float] = None
#     longitude: Optional[float] = None
#     is_open: Optional[bool] = None
#     featured: Optional[bool] = None
#     services: Optional[List[str]] = None

# class StoreSchema(StoreBase):
#     id: int
#     created_at: datetime
#     services: List[StoreServiceSchema] = []
    
#     class Config:
#         from_attributes = True

# # Newsletter Subscriber Schemas
# class NewsletterSubscriberBase(BaseModel):
#     email: str
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     is_active: bool = True

# class NewsletterSubscriberCreate(NewsletterSubscriberBase):
#     pass

# class NewsletterSubscriberUpdate(BaseModel):
#     email: Optional[str] = None
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     is_active: Optional[bool] = None

# class NewsletterSubscriberSchema(NewsletterSubscriberBase):
#     id: int
#     subscribed_at: datetime
#     unsubscribed_at: Optional[datetime] = None
    
#     class Config:
#         from_attributes = True

# # Generic response models
# class DeleteResponse(BaseModel):
#     message: str
#     deleted_count: int = 1

# class BulkDeleteResponse(BaseModel):
#     message: str
#     deleted_count: int

# # ==================== FEATURES MANAGEMENT ====================

# @router.get("/features", response_model=List[FeatureSchema])
# async def get_all_features(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all features."""
#     result = await db.execute(select(Feature).order_by(Feature.id))
#     return result.scalars().all()

# @router.post("/features", response_model=FeatureSchema)
# async def create_feature(
#     feature_data: FeatureCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new feature."""
#     feature = Feature(**feature_data.model_dump())
#     db.add(feature)
#     await db.commit()
#     await db.refresh(feature)
#     return feature

# @router.put("/features/{feature_id}", response_model=FeatureSchema)
# async def update_feature(
#     feature_id: int,
#     feature_update: FeatureUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update feature."""
#     result = await db.execute(select(Feature).where(Feature.id == feature_id))
#     feature = result.scalar_one_or_none()
    
#     if not feature:
#         raise HTTPException(status_code=404, detail="Feature not found")
    
#     update_data = feature_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(feature, field, value)
    
#     await db.commit()
#     await db.refresh(feature)
#     return feature

# @router.delete("/features/{feature_id}", response_model=DeleteResponse)
# async def delete_feature(
#     feature_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete feature."""
#     result = await db.execute(select(Feature).where(Feature.id == feature_id))
#     feature = result.scalar_one_or_none()
    
#     if not feature:
#         raise HTTPException(status_code=404, detail="Feature not found")
    
#     await db.delete(feature)
#     await db.commit()
#     return DeleteResponse(message="Feature deleted successfully")

# # ==================== STATS MANAGEMENT ====================

# @router.get("/stats", response_model=List[StatSchema])
# async def get_all_stats(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all stats."""
#     result = await db.execute(select(Stat).order_by(Stat.id))
#     return result.scalars().all()

# @router.post("/stats", response_model=StatSchema)
# async def create_stat(
#     stat_data: StatCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new stat."""
#     stat = Stat(**stat_data.model_dump())
#     db.add(stat)
#     await db.commit()
#     await db.refresh(stat)
#     return stat

# @router.put("/stats/{stat_id}", response_model=StatSchema)
# async def update_stat(
#     stat_id: int,
#     stat_update: StatUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update stat."""
#     result = await db.execute(select(Stat).where(Stat.id == stat_id))
#     stat = result.scalar_one_or_none()
    
#     if not stat:
#         raise HTTPException(status_code=404, detail="Stat not found")
    
#     update_data = stat_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(stat, field, value)
    
#     await db.commit()
#     await db.refresh(stat)
#     return stat

# @router.delete("/stats/{stat_id}", response_model=DeleteResponse)
# async def delete_stat(
#     stat_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete stat."""
#     result = await db.execute(select(Stat).where(Stat.id == stat_id))
#     stat = result.scalar_one_or_none()
    
#     if not stat:
#         raise HTTPException(status_code=404, detail="Stat not found")
    
#     await db.delete(stat)
#     await db.commit()
#     return DeleteResponse(message="Stat deleted successfully")

# # ==================== SOCIAL LINKS MANAGEMENT ====================

# @router.get("/social-links", response_model=List[SocialLinkSchema])
# async def get_all_social_links(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all social links."""
#     result = await db.execute(select(SocialLink).order_by(SocialLink.id))
#     return result.scalars().all()

# @router.post("/social-links", response_model=SocialLinkSchema)
# async def create_social_link(
#     link_data: SocialLinkCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new social link."""
#     link = SocialLink(**link_data.model_dump())
#     db.add(link)
#     await db.commit()
#     await db.refresh(link)
#     return link

# @router.put("/social-links/{link_id}", response_model=SocialLinkSchema)
# async def update_social_link(
#     link_id: int,
#     link_update: SocialLinkUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update social link."""
#     result = await db.execute(select(SocialLink).where(SocialLink.id == link_id))
#     link = result.scalar_one_or_none()
    
#     if not link:
#         raise HTTPException(status_code=404, detail="Social link not found")
    
#     update_data = link_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(link, field, value)
    
#     await db.commit()
#     await db.refresh(link)
#     return link

# @router.delete("/social-links/{link_id}", response_model=DeleteResponse)
# async def delete_social_link(
#     link_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete social link."""
#     result = await db.execute(select(SocialLink).where(SocialLink.id == link_id))
#     link = result.scalar_one_or_none()
    
#     if not link:
#         raise HTTPException(status_code=404, detail="Social link not found")
    
#     await db.delete(link)
#     await db.commit()
#     return DeleteResponse(message="Social link deleted successfully")

# # ==================== QUICK LINKS MANAGEMENT ====================

# @router.get("/quick-link-categories", response_model=List[QuickLinkCategorySchema])
# async def get_all_quick_link_categories(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all quick link categories with their links."""
#     result = await db.execute(
#         select(QuickLinkCategory)
#         .options(selectinload(QuickLinkCategory.quick_links))
#         .order_by(QuickLinkCategory.id)
#     )
#     return result.scalars().all()

# @router.post("/quick-link-categories", response_model=QuickLinkCategorySchema)
# async def create_quick_link_category(
#     category_data: QuickLinkCategoryCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new quick link category."""
#     category = QuickLinkCategory(**category_data.model_dump())
#     db.add(category)
#     await db.commit()
#     await db.refresh(category)
#     return category

# @router.put("/quick-link-categories/{category_id}", response_model=QuickLinkCategorySchema)
# async def update_quick_link_category(
#     category_id: int,
#     category_update: QuickLinkCategoryUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update quick link category."""
#     result = await db.execute(select(QuickLinkCategory).where(QuickLinkCategory.id == category_id))
#     category = result.scalar_one_or_none()
    
#     if not category:
#         raise HTTPException(status_code=404, detail="Quick link category not found")
    
#     update_data = category_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(category, field, value)
    
#     await db.commit()
#     await db.refresh(category)
#     return category

# @router.delete("/quick-link-categories/{category_id}", response_model=DeleteResponse)
# async def delete_quick_link_category(
#     category_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete quick link category and all its links."""
#     result = await db.execute(select(QuickLinkCategory).where(QuickLinkCategory.id == category_id))
#     category = result.scalar_one_or_none()
    
#     if not category:
#         raise HTTPException(status_code=404, detail="Quick link category not found")
    
#     await db.delete(category)
#     await db.commit()
#     return DeleteResponse(message="Quick link category deleted successfully")

# @router.post("/quick-links", response_model=QuickLinkSchema)
# async def create_quick_link(
#     link_data: QuickLinkCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new quick link."""
#     # Verify category exists
#     category = await db.get(QuickLinkCategory, link_data.category_id)
#     if not category:
#         raise HTTPException(status_code=404, detail="Quick link category not found")
    
#     link = QuickLink(**link_data.model_dump())
#     db.add(link)
#     await db.commit()
#     await db.refresh(link)
#     return link

# @router.put("/quick-links/{link_id}", response_model=QuickLinkSchema)
# async def update_quick_link(
#     link_id: int,
#     link_update: QuickLinkUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update quick link."""
#     result = await db.execute(select(QuickLink).where(QuickLink.id == link_id))
#     link = result.scalar_one_or_none()
    
#     if not link:
#         raise HTTPException(status_code=404, detail="Quick link not found")
    
#     update_data = link_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(link, field, value)
    
#     await db.commit()
#     await db.refresh(link)
#     return link

# @router.delete("/quick-links/{link_id}", response_model=DeleteResponse)
# async def delete_quick_link(
#     link_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete quick link."""
#     result = await db.execute(select(QuickLink).where(QuickLink.id == link_id))
#     link = result.scalar_one_or_none()
    
#     if not link:
#         raise HTTPException(status_code=404, detail="Quick link not found")
    
#     await db.delete(link)
#     await db.commit()
#     return DeleteResponse(message="Quick link deleted successfully")

# # ==================== PAYMENT METHODS MANAGEMENT ====================

# @router.get("/payment-methods", response_model=List[PaymentMethodSchema])
# async def get_all_payment_methods(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all payment methods."""
#     result = await db.execute(select(PaymentMethod).order_by(PaymentMethod.id))
#     return result.scalars().all()

# @router.post("/payment-methods", response_model=PaymentMethodSchema)
# async def create_payment_method(
#     method_data: PaymentMethodCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new payment method."""
#     method = PaymentMethod(**method_data.model_dump())
#     db.add(method)
#     await db.commit()
#     await db.refresh(method)
#     return method

# @router.put("/payment-methods/{method_id}", response_model=PaymentMethodSchema)
# async def update_payment_method(
#     method_id: int,
#     method_update: PaymentMethodUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update payment method."""
#     result = await db.execute(select(PaymentMethod).where(PaymentMethod.id == method_id))
#     method = result.scalar_one_or_none()
    
#     if not method:
#         raise HTTPException(status_code=404, detail="Payment method not found")
    
#     update_data = method_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(method, field, value)
    
#     await db.commit()
#     await db.refresh(method)
#     return method

# @router.delete("/payment-methods/{method_id}", response_model=DeleteResponse)
# async def delete_payment_method(
#     method_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete payment method."""
#     result = await db.execute(select(PaymentMethod).where(PaymentMethod.id == method_id))
#     method = result.scalar_one_or_none()
    
#     if not method:
#         raise HTTPException(status_code=404, detail="Payment method not found")
    
#     await db.delete(method)
#     await db.commit()
#     return DeleteResponse(message="Payment method deleted successfully")

# # ==================== CONTACT INFO MANAGEMENT ====================

# @router.get("/contact-info", response_model=ContactInfoSchema)
# async def get_contact_info(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get contact info (should have only one record)."""
#     result = await db.execute(select(ContactInfo).limit(1))
#     contact_info = result.scalar_one_or_none()
    
#     if not contact_info:
#         raise HTTPException(status_code=404, detail="Contact info not found")
    
#     return contact_info

# @router.post("/contact-info", response_model=ContactInfoSchema)
# async def create_or_update_contact_info(
#     contact_data: ContactInfoCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create or update contact info (only one record allowed)."""
#     result = await db.execute(select(ContactInfo).limit(1))
#     contact_info = result.scalar_one_or_none()
    
#     if contact_info:
#         # Update existing
#         update_data = contact_data.model_dump(exclude_unset=True)
#         for field, value in update_data.items():
#             setattr(contact_info, field, value)
#     else:
#         # Create new
#         contact_info = ContactInfo(**contact_data.model_dump())
#         db.add(contact_info)
    
#     await db.commit()
#     await db.refresh(contact_info)
#     return contact_info

# # ==================== PROMO MESSAGES MANAGEMENT ====================

# @router.get("/promo-messages", response_model=List[PromoMessageSchema])
# async def get_all_promo_messages(
#     is_active: Optional[bool] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all promo messages."""
#     query = select(PromoMessage)
    
#     if is_active is not None:
#         query = query.where(PromoMessage.is_active == is_active)
    
#     query = query.order_by(PromoMessage.id)
#     result = await db.execute(query)
#     return result.scalars().all()

# @router.post("/promo-messages", response_model=PromoMessageSchema)
# async def create_promo_message(
#     promo_data: PromoMessageCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new promo message."""
#     promo = PromoMessage(**promo_data.model_dump())
#     db.add(promo)
#     await db.commit()
#     await db.refresh(promo)
#     return promo

# @router.put("/promo-messages/{promo_id}", response_model=PromoMessageSchema)
# async def update_promo_message(
#     promo_id: int,
#     promo_update: PromoMessageUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update promo message."""
#     result = await db.execute(select(PromoMessage).where(PromoMessage.id == promo_id))
#     promo = result.scalar_one_or_none()
    
#     if not promo:
#         raise HTTPException(status_code=404, detail="Promo message not found")
    
#     update_data = promo_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(promo, field, value)
    
#     await db.commit()
#     await db.refresh(promo)
#     return promo

# @router.delete("/promo-messages/{promo_id}", response_model=DeleteResponse)
# async def delete_promo_message(
#     promo_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete promo message."""
#     result = await db.execute(select(PromoMessage).where(PromoMessage.id == promo_id))
#     promo = result.scalar_one_or_none()
    
#     if not promo:
#         raise HTTPException(status_code=404, detail="Promo message not found")
    
#     await db.delete(promo)
#     await db.commit()
#     return DeleteResponse(message="Promo message deleted successfully")

# # ==================== SUPPLIERS MANAGEMENT ====================

# @router.get("/suppliers", response_model=List[SupplierSchema])
# async def get_all_suppliers(
#     featured: Optional[bool] = None,
#     category: Optional[str] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all suppliers."""
#     query = select(Supplier)
    
#     if featured is not None:
#         query = query.where(Supplier.featured == featured)
    
#     if category:
#         query = query.where(Supplier.category == category)
    
#     query = query.order_by(Supplier.name)
#     result = await db.execute(query)
#     return result.scalars().all()

# @router.post("/suppliers", response_model=SupplierSchema)
# async def create_supplier(
#     supplier_data: SupplierCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new supplier."""
#     supplier = Supplier(**supplier_data.model_dump())
#     db.add(supplier)
#     await db.commit()
#     await db.refresh(supplier)
#     return supplier

# @router.put("/suppliers/{supplier_id}", response_model=SupplierSchema)
# async def update_supplier(
#     supplier_id: int,
#     supplier_update: SupplierUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update supplier."""
#     result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
#     supplier = result.scalar_one_or_none()
    
#     if not supplier:
#         raise HTTPException(status_code=404, detail="Supplier not found")
    
#     update_data = supplier_update.model_dump(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(supplier, field, value)
    
#     await db.commit()
#     await db.refresh(supplier)
#     return supplier

# @router.delete("/suppliers/{supplier_id}", response_model=DeleteResponse)
# async def delete_supplier(
#     supplier_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete supplier."""
#     result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
#     supplier = result.scalar_one_or_none()
    
#     if not supplier:
#         raise HTTPException(status_code=404, detail="Supplier not found")
    
#     await db.delete(supplier)
#     await db.commit()
#     return DeleteResponse(message="Supplier deleted successfully")

# # ==================== STORES MANAGEMENT ====================

# @router.get("/stores", response_model=List[StoreSchema])
# async def get_all_stores(
#     featured: Optional[bool] = None,
#     is_open: Optional[bool] = None,
#     city: Optional[str] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all stores with their services."""
#     query = select(Store).options(selectinload(Store.services))
    
#     if featured is not None:
#         query = query.where(Store.featured == featured)
    
#     if is_open is not None:
#         query = query.where(Store.is_open == is_open)
    
#     if city:
#         query = query.where(Store.city.ilike(f"%{city}%"))
    
#     query = query.order_by(Store.name)
#     result = await db.execute(query)
#     return result.scalars().all()

# @router.post("/stores", response_model=StoreSchema)
# async def create_store(
#     store_data: StoreCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create new store with services."""
#     store_dict = store_data.model_dump()
#     services = store_dict.pop('services', [])
    
#     store = Store(**store_dict)
#     db.add(store)
#     await db.flush()  # Get the store ID
    
#     # Add services
#     for service_name in services:
#         service = StoreService(store_id=store.id, service_name=service_name)
#         db.add(service)
    
#     await db.commit()
#     await db.refresh(store)
    
#     # Load with services
#     result = await db.execute(
#         select(Store).options(selectinload(Store.services)).where(Store.id == store.id)
#     )
#     return result.scalar_one()

# @router.put("/stores/{store_id}", response_model=StoreSchema)
# async def update_store(
#     store_id: int,
#     store_update: StoreUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update store and its services."""
#     result = await db.execute(select(Store).where(Store.id == store_id))
#     store = result.scalar_one_or_none()
    
#     if not store:
#         raise HTTPException(status_code=404, detail="Store not found")
    
#     update_data = store_update.model_dump(exclude_unset=True)
#     services = update_data.pop('services', None)
    
#     # Update store fields
#     for field, value in update_data.items():
#         setattr(store, field, value)
    
#     # Update services if provided
#     if services is not None:
#         # Delete existing services
#         await db.execute(delete(StoreService).where(StoreService.store_id == store_id))
        
#         # Add new services
#         for service_name in services:
#             service = StoreService(store_id=store_id, service_name=service_name)
#             db.add(service)
    
#     await db.commit()
    
#     # Load with services
#     result = await db.execute(
#         select(Store).options(selectinload(Store.services)).where(Store.id == store_id)
#     )
#     return result.scalar_one()

# @router.delete("/stores/{store_id}", response_model=DeleteResponse)
# async def delete_store(
#     store_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete store and its services."""
#     result = await db.execute(select(Store).where(Store.id == store_id))
#     store = result.scalar_one_or_none()
    
#     if not store:
#         raise HTTPException(status_code=404, detail="Store not found")
    
#     await db.delete(store)
#     await db.commit()
#     return DeleteResponse(message="Store deleted successfully")

# # ==================== NEWSLETTER SUBSCRIBERS MANAGEMENT ====================

# @router.get("/newsletter-subscribers", response_model=Dict[str, Any])
# async def get_newsletter_subscribers(
#     page: int = Query(1, ge=1),
#     per_page: int = Query(50, ge=1, le=200),
#     is_active: Optional[bool] = None,
#     search: Optional[str] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get newsletter subscribers with pagination."""
#     query = select(NewsletterSubscriber)
    
#     if is_active is not None:
#         query = query.where(NewsletterSubscriber.is_active == is_active)
    
#     if search:
#         query = query.where(
#             or_(
#                 NewsletterSubscriber.email.ilike(f"%{search}%"),
#                 NewsletterSubscriber.first_name.ilike(f"%{search}%"),
#                 NewsletterSubscriber.last_name.ilike(f"%{search}%")
#             )
#         )
    
#     # Count total
#     count_query = select(func.count()).select_from(query.subquery())
#     total_result = await db.execute(count_query)
#     total = total_result.scalar()
    
#     # Apply pagination
#     offset = (page - 1) * per_page
#     query = query.order_by(NewsletterSubscriber.subscribed_at.desc()).offset(offset).limit(per_page)
    
#     result = await db.execute(query)
#     subscribers = result.scalars().all()
    
#     return {
#         "items": subscribers,
#         "total": total,
#         "page": page,
#         "per_page": per_page,
#         "pages": (total + per_page - 1) // per_page
#     }

# @router.post("/newsletter-subscribers", response_model=NewsletterSubscriberSchema)
# async def add_newsletter_subscriber(
#     subscriber_data: NewsletterSubscriberCreate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Add newsletter subscriber."""
#     # Check if email exists
#     existing = await db.execute(
#         select(NewsletterSubscriber).where(NewsletterSubscriber.email == subscriber_data.email)
#     )
#     if existing.scalar_one_or_none():
#         raise HTTPException(status_code=400, detail="Email already subscribed")
    
#     subscriber = NewsletterSubscriber(**subscriber_data.model_dump())
#     db.add(subscriber)
#     await db.commit()
#     await db.refresh(subscriber)
#     return subscriber

# @router.put("/newsletter-subscribers/{subscriber_id}", response_model=NewsletterSubscriberSchema)
# async def update_newsletter_subscriber(
#     subscriber_id: int,
#     subscriber_update: NewsletterSubscriberUpdate,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update newsletter subscriber."""
#     result = await db.execute(
#         select(NewsletterSubscriber).where(NewsletterSubscriber.id == subscriber_id)
#     )
#     subscriber = result.scalar_one_or_none()
    
#     if not subscriber:
#         raise HTTPException(status_code=404, detail="Subscriber not found")
    
#     update_data = subscriber_update.model_dump(exclude_unset=True)
    
#     # Handle unsubscribe
#     if 'is_active' in update_data and not update_data['is_active'] and subscriber.is_active:
#         subscriber.unsubscribed_at = datetime.utcnow()
#     elif 'is_active' in update_data and update_data['is_active'] and not subscriber.is_active:
#         subscriber.unsubscribed_at = None
    
#     for field, value in update_data.items():
#         setattr(subscriber, field, value)
    
#     await db.commit()
#     await db.refresh(subscriber)
#     return subscriber

# @router.delete("/newsletter-subscribers/{subscriber_id}", response_model=DeleteResponse)
# async def delete_newsletter_subscriber(
#     subscriber_id: int,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Delete newsletter subscriber."""
#     result = await db.execute(
#         select(NewsletterSubscriber).where(NewsletterSubscriber.id == subscriber_id)
#     )
#     subscriber = result.scalar_one_or_none()
    
#     if not subscriber:
#         raise HTTPException(status_code=404, detail="Subscriber not found")
    
#     await db.delete(subscriber)
#     await db.commit()
#     return DeleteResponse(message="Subscriber deleted successfully")

# @router.post("/newsletter-subscribers/bulk-delete", response_model=BulkDeleteResponse)
# async def bulk_delete_newsletter_subscribers(
#     subscriber_ids: List[int],
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Bulk delete newsletter subscribers."""
#     result = await db.execute(
#         delete(NewsletterSubscriber).where(NewsletterSubscriber.id.in_(subscriber_ids))
#     )
#     await db.commit()
#     return BulkDeleteResponse(
#         message=f"Deleted {result.rowcount} subscribers",
#         deleted_count=result.rowcount
#     )

# # ==================== ANALYTICS DASHBOARD ====================

# @router.get("/analytics/search-queries")
# async def get_search_queries(
#     limit: int = Query(100, le=1000),
#     start_date: Optional[datetime] = None,
#     end_date: Optional[datetime] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get search queries analytics."""
#     query = select(
#         SearchQuery.query_text,
#         func.count(SearchQuery.id).label('count'),
#         func.avg(SearchQuery.results_count).label('avg_results')
#     ).group_by(SearchQuery.query_text)
    
#     if start_date:
#         query = query.where(SearchQuery.created_at >= start_date)
    
#     if end_date:
#         query = query.where(SearchQuery.created_at <= end_date)
    
#     query = query.order_by(func.count(SearchQuery.id).desc()).limit(limit)
    
#     result = await db.execute(query)
#     return [
#         {
#             "query": row.query_text,
#             "count": row.count,
#             "avg_results": float(row.avg_results) if row.avg_results else 0
#         }
#         for row in result
#     ]

# @router.get("/analytics/traffic-sources")
# async def get_traffic_sources(
#     start_date: Optional[datetime] = None,
#     end_date: Optional[datetime] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get traffic sources analytics."""
#     query = select(TrafficSource)
    
#     if start_date:
#         query = query.where(TrafficSource.created_at >= start_date)
    
#     if end_date:
#         query = query.where(TrafficSource.created_at <= end_date)
    
#     query = query.order_by(TrafficSource.sessions.desc())
    
#     result = await db.execute(query)
#     return result.scalars().all()

# @router.get("/analytics/conversion-funnel")
# async def get_conversion_funnel(
#     start_date: Optional[datetime] = None,
#     end_date: Optional[datetime] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get conversion funnel data."""
#     query = select(ConversionFunnel)
    
#     if start_date:
#         query = query.where(ConversionFunnel.date >= start_date.date())
    
#     if end_date:
#         query = query.where(ConversionFunnel.date <= end_date.date())
    
#     query = query.order_by(ConversionFunnel.date.desc())
    
#     result = await db.execute(query)
#     data = result.scalars().all()
    
#     # Calculate conversion rates
#     funnel_data = []
#     for record in data:
#         funnel_data.append({
#             "date": record.date,
#             "visitors": record.visitors,
#             "product_views": record.product_views,
#             "add_to_cart": record.add_to_cart,
#             "add_to_wishlist": record.add_to_wishlist,
#             "checkout": record.checkout,
#             "purchase": record.purchase,
#             "conversion_rates": {
#                 "visitor_to_view": (record.product_views / record.visitors * 100) if record.visitors > 0 else 0,
#                 "view_to_cart": (record.add_to_cart / record.product_views * 100) if record.product_views > 0 else 0,
#                 "cart_to_checkout": (record.checkout / record.add_to_cart * 100) if record.add_to_cart > 0 else 0,
#                 "checkout_to_purchase": (record.purchase / record.checkout * 100) if record.checkout > 0 else 0,
#                 "overall": (record.purchase / record.visitors * 100) if record.visitors > 0 else 0
#             }
#         })
    
#     return funnel_data

# # Export router
# __all__ = ["router"]