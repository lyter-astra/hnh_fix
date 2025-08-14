# app/api/v1/site.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.site import (
    HeroImage, HeroConfig, HeroButton, HeroPriceTag,
    Feature, Stat, SocialLink, QuickLinkCategory, QuickLink,
    PaymentMethod, ContactInfo, PromoMessage, Supplier, Store
)

router = APIRouter(prefix="/site", tags=["Site Data"])

# ==================== HERO SECTION ENDPOINTS ====================

@router.get("/hero-data")
async def get_hero_data(
    config_name: str = "main_hero",
    db: AsyncSession = Depends(get_db)
):
    """Get complete hero section data."""
    # Get hero configuration
    config_result = await db.execute(
        select(HeroConfig)
        .options(
            selectinload(HeroConfig.buttons),
            selectinload(HeroConfig.price_tags)
        )
        .where(
            HeroConfig.config_name == config_name,
            HeroConfig.is_active == True
        )
    )
    hero_config = config_result.scalar_one_or_none()
    
    if not hero_config:
        raise HTTPException(status_code=404, detail="Hero configuration not found")
    
    # Get hero images
    images_result = await db.execute(
        select(HeroImage)
        .where(HeroImage.is_active == True)
        .order_by(HeroImage.display_order)
    )
    hero_images = images_result.scalars().all()
    
    # Format response to match your frontend constants structure
    return {
        "heroImages": [img.image_url for img in hero_images],
        "heroConfig": {
            "title": {
                "primary": hero_config.title_primary,
                "secondary": hero_config.title_secondary
            },
            "subtitle": hero_config.subtitle,
            "description": hero_config.description,
            "buttons": {
                button.button_type: {
                    "text": button.button_text,
                    "icon": button.button_icon,
                    "url": button.button_url,
                    "action": button.button_action
                }
                for button in sorted(hero_config.buttons, key=lambda x: x.display_order)
                if button.is_active
            },
            "priceTag": {
                "label": hero_config.price_tags[0].label if hero_config.price_tags else "FROM",
                "price": hero_config.price_tags[0].price if hero_config.price_tags else "$0",
                "currency": hero_config.price_tags[0].currency_code if hero_config.price_tags else "USD"
            } if hero_config.price_tags else None
        }
    }

@router.get("/hero-images")
async def get_hero_images(db: AsyncSession = Depends(get_db)):
    """Get all active hero images."""
    result = await db.execute(
        select(HeroImage)
        .where(HeroImage.is_active == True)
        .order_by(HeroImage.display_order)
    )
    images = result.scalars().all()
    
    return {
        "images": [
            {
                "id": img.id,
                "url": img.image_url,
                "alt_text": img.alt_text,
                "display_order": img.display_order
            }
            for img in images
        ]
    }

@router.get("/hero-config/{config_name}")
async def get_hero_config(
    config_name: str,
    db: AsyncSession = Depends(get_db)
):
    """Get specific hero configuration."""
    result = await db.execute(
        select(HeroConfig)
        .options(
            selectinload(HeroConfig.buttons),
            selectinload(HeroConfig.price_tags)
        )
        .where(
            HeroConfig.config_name == config_name,
            HeroConfig.is_active == True
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Hero configuration not found")
    
    return {
        "config": {
            "id": config.id,
            "config_name": config.config_name,
            "title_primary": config.title_primary,
            "title_secondary": config.title_secondary,
            "subtitle": config.subtitle,
            "description": config.description,
            "buttons": [
                {
                    "id": btn.id,
                    "type": btn.button_type,
                    "text": btn.button_text,
                    "icon": btn.button_icon,
                    "url": btn.button_url,
                    "action": btn.button_action,
                    "display_order": btn.display_order
                }
                for btn in sorted(config.buttons, key=lambda x: x.display_order)
                if btn.is_active
            ],
            "price_tags": [
                {
                    "id": tag.id,
                    "label": tag.label,
                    "price": tag.price,
                    "currency_code": tag.currency_code
                }
                for tag in config.price_tags
                if tag.is_active
            ]
        }
    }

# ==================== EXISTING ENDPOINTS ====================

@router.get("/features")
async def get_features(db: AsyncSession = Depends(get_db)):
    """Get all active features for homepage."""
    result = await db.execute(
        select(Feature).order_by(Feature.id)
    )
    features = result.scalars().all()
    
    return {
        "features": [
            {
                "icon": f.icon,
                "text": f.text,
                "subtext": f.subtext,
                "bgColor": f.bg_color,
                "iconColor": f.icon_color
            }
            for f in features
        ]
    }

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get all stats for homepage."""
    result = await db.execute(
        select(Stat).order_by(Stat.id)
    )
    stats = result.scalars().all()
    
    return {
        "stats": [
            {
                "icon": s.icon,
                "number": s.number,
                "label": s.label,
                "color": s.color
            }
            for s in stats
        ]
    }

@router.get("/social-links")
async def get_social_links(db: AsyncSession = Depends(get_db)):
    """Get all social media links."""
    result = await db.execute(
        select(SocialLink).order_by(SocialLink.id)
    )
    links = result.scalars().all()
    
    return {
        "socialLinks": [
            {
                "icon": link.icon,
                "href": link.href,
                "label": link.label,
                "color": link.color
            }
            for link in links
        ]
    }

@router.get("/quick-links")
async def get_quick_links(db: AsyncSession = Depends(get_db)):
    """Get all quick links grouped by category."""
    result = await db.execute(
        select(QuickLinkCategory)
        .options(selectinload(QuickLinkCategory.quick_links))
        .order_by(QuickLinkCategory.id)
    )
    categories = result.scalars().all()
    
    quick_links = {}
    for category in categories:
        quick_links[category.category] = [
            {
                "name": link.name,
                "icon": link.icon
            }
            for link in category.quick_links
        ]
    
    return {"quickLinks": quick_links}

@router.get("/payment-methods")
async def get_payment_methods(db: AsyncSession = Depends(get_db)):
    """Get all active payment methods."""
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.is_active == True)
        .order_by(PaymentMethod.id)
    )
    methods = result.scalars().all()
    
    return {
        "paymentMethods": [method.name for method in methods]
    }

@router.get("/contact-info")
async def get_contact_info(db: AsyncSession = Depends(get_db)):
    """Get contact information."""
    result = await db.execute(select(ContactInfo).limit(1))
    contact = result.scalar_one_or_none()
    
    if not contact:
        return {
            "contact": {
                "address": {
                    "line1": "",
                    "line2": ""
                },
                "hours": {
                    "weekdays": "",
                    "weekends": ""
                },
                "phone": {
                    "display": "",
                    "href": ""
                },
                "email": ""
            }
        }
    
    return {
        "contact": {
            "address": {
                "line1": contact.address_line1 or "",
                "line2": contact.address_line2 or ""
            },
            "hours": {
                "weekdays": contact.weekday_hours or "",
                "weekends": contact.weekend_hours or ""
            },
            "phone": {
                "display": contact.phone or "",
                "href": contact.phone_href or ""
            },
            "email": contact.email or ""
        }
    }

@router.get("/promo-messages")
async def get_promo_messages(db: AsyncSession = Depends(get_db)):
    """Get active promotional messages."""
    result = await db.execute(
        select(PromoMessage)
        .where(PromoMessage.is_active == True)
        .order_by(PromoMessage.id)
    )
    messages = result.scalars().all()
    
    return {
        "promoMessages": [
            {
                "icon": msg.icon,
                "text": msg.text,
                "cta": msg.cta
            }
            for msg in messages
        ]
    }

@router.get("/suppliers")
async def get_suppliers(
    featured_only: bool = False,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get suppliers, optionally filtered by featured status or category."""
    query = select(Supplier)
    
    if featured_only:
        query = query.where(Supplier.featured == True)
    
    if category:
        query = query.where(Supplier.category == category)
    
    query = query.order_by(Supplier.name)
    result = await db.execute(query)
    suppliers = result.scalars().all()
    
    return {
        "suppliers": [
            {
                "id": s.id,
                "name": s.name,
                "logo": s.logo,
                "category": s.category,
                "featured": s.featured,
                "partnerSince": s.partner_since,
                "rating": float(s.rating) if s.rating else None,
                "growth": s.growth
            }
            for s in suppliers
        ]
    }

@router.get("/stores")
async def get_stores(
    city: Optional[str] = None,
    featured_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get stores with their services."""
    query = select(Store).options(selectinload(Store.services))
    
    if featured_only:
        query = query.where(Store.featured == True)
    
    if city:
        query = query.where(Store.city.ilike(f"%{city}%"))
    
    query = query.order_by(Store.featured.desc(), Store.name)
    result = await db.execute(query)
    stores = result.scalars().all()
    
    return {
        "stores": [
            {
                "id": store.id,
                "name": store.name,
                "address": store.address,
                "city": store.city,
                "state": store.state,
                "zip": store.zip,
                "phone": store.phone,
                "hours": {
                    "weekdays": store.hours_weekday,
                    "weekends": store.hours_weekend
                },
                "rating": float(store.rating) if store.rating else None,
                "reviews": store.reviews,
                "distance": store.distance,
                "coordinates": {
                    "lat": float(store.latitude) if store.latitude else None,
                    "lng": float(store.longitude) if store.longitude else None
                },
                "isOpen": store.is_open,
                "featured": store.featured,
                "services": [service.service_name for service in store.services]
            }
            for store in stores
        ]
    }

@router.get("/stores/{store_id}")
async def get_store_details(
    store_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific store."""
    result = await db.execute(
        select(Store)
        .options(selectinload(Store.services))
        .where(Store.id == store_id)
    )
    store = result.scalar_one_or_none()
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {
        "store": {
            "id": store.id,
            "name": store.name,
            "address": store.address,
            "city": store.city,
            "state": store.state,
            "zip": store.zip,
            "phone": store.phone,
            "hours": {
                "weekdays": store.hours_weekday,
                "weekends": store.hours_weekend
            },
            "rating": float(store.rating) if store.rating else None,
            "reviews": store.reviews,
            "distance": store.distance,
            "coordinates": {
                "lat": float(store.latitude) if store.latitude else None,
                "lng": float(store.longitude) if store.longitude else None
            },
            "isOpen": store.is_open,
            "featured": store.featured,
            "services": [service.service_name for service in store.services]
        }
    }

@router.post("/newsletter/subscribe")
async def subscribe_to_newsletter(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Subscribe to newsletter."""
    from app.models.site import NewsletterSubscriber
    from sqlalchemy import select
    
    # Check if already subscribed
    existing = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )
    subscriber = existing.scalar_one_or_none()
    
    if subscriber:
        if subscriber.is_active:
            return {"message": "Already subscribed", "status": "existing"}
        else:
            # Reactivate subscription
            subscriber.is_active = True
            subscriber.unsubscribed_at = None
            if first_name:
                subscriber.first_name = first_name
            if last_name:
                subscriber.last_name = last_name
            await db.commit()
            return {"message": "Subscription reactivated", "status": "reactivated"}
    
    # Create new subscriber
    new_subscriber = NewsletterSubscriber(
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=True
    )
    db.add(new_subscriber)
    await db.commit()
    
    return {"message": "Successfully subscribed", "status": "new"}

@router.post("/newsletter/unsubscribe")
async def unsubscribe_from_newsletter(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from newsletter."""
    from app.models.site import NewsletterSubscriber
    from datetime import datetime
    
    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )
    subscriber = result.scalar_one_or_none()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Email not found")
    
    if not subscriber.is_active:
        return {"message": "Already unsubscribed", "status": "already_unsubscribed"}
    
    subscriber.is_active = False
    subscriber.unsubscribed_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Successfully unsubscribed", "status": "unsubscribed"}

# ==================== COMPOSITE ENDPOINTS ====================

@router.get("/footer-data")
async def get_footer_data(db: AsyncSession = Depends(get_db)):
    """Get all data needed for the footer in one request."""
    # Get quick links
    quick_links_result = await db.execute(
        select(QuickLinkCategory)
        .options(selectinload(QuickLinkCategory.quick_links))
        .order_by(QuickLinkCategory.id)
    )
    categories = quick_links_result.scalars().all()
    
    quick_links = {}
    for category in categories:
        quick_links[category.category] = [
            {"name": link.name, "icon": link.icon}
            for link in category.quick_links
        ]
    
    # Get contact info
    contact_result = await db.execute(select(ContactInfo).limit(1))
    contact = contact_result.scalar_one_or_none()
    
    contact_data = {
        "address": {
            "line1": contact.address_line1 or "" if contact else "",
            "line2": contact.address_line2 or "" if contact else ""
        },
        "hours": {
            "weekdays": contact.weekday_hours or "" if contact else "",
            "weekends": contact.weekend_hours or "" if contact else ""
        },
        "phone": {
            "display": contact.phone or "" if contact else "",
            "href": contact.phone_href or "" if contact else ""
        },
        "email": contact.email or "" if contact else ""
    }
    
    # Get social links
    social_result = await db.execute(
        select(SocialLink).order_by(SocialLink.id)
    )
    social_links = social_result.scalars().all()
    
    # Get payment methods
    payment_result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.is_active == True)
        .order_by(PaymentMethod.id)
    )
    payment_methods = payment_result.scalars().all()
    
    return {
        "quickLinks": quick_links,
        "contact": contact_data,
        "socialLinks": [
            {
                "icon": link.icon,
                "href": link.href,
                "label": link.label,
                "color": link.color
            }
            for link in social_links
        ],
        "paymentMethods": [method.name for method in payment_methods]
    }

@router.get("/homepage-data")
async def get_homepage_data(db: AsyncSession = Depends(get_db)):
    """Get all data needed for the homepage in one request."""
    # Get hero data
    hero_data = await get_hero_data("main_hero", db)
    
    # Get features
    features_result = await db.execute(
        select(Feature).order_by(Feature.id)
    )
    features = features_result.scalars().all()
    
    # Get stats
    stats_result = await db.execute(
        select(Stat).order_by(Stat.id)
    )
    stats = stats_result.scalars().all()
    
    # Get promo messages
    promo_result = await db.execute(
        select(PromoMessage)
        .where(PromoMessage.is_active == True)
        .order_by(PromoMessage.id)
    )
    promo_messages = promo_result.scalars().all()
    
    # Get featured suppliers
    suppliers_result = await db.execute(
        select(Supplier)
        .where(Supplier.featured == True)
        .order_by(Supplier.name)
        .limit(6)  # Limit to 6 featured suppliers
    )
    featured_suppliers = suppliers_result.scalars().all()
    
    return {
        **hero_data,  # Include hero data
        "features": [
            {
                "icon": f.icon,
                "text": f.text,
                "subtext": f.subtext,
                "bgColor": f.bg_color,
                "iconColor": f.icon_color
            }
            for f in features
        ],
        "stats": [
            {
                "icon": s.icon,
                "number": s.number,
                "label": s.label,
                "color": s.color
            }
            for s in stats
        ],
        "promoMessages": [
            {
                "icon": msg.icon,
                "text": msg.text,
                "cta": msg.cta
            }
            for msg in promo_messages
        ],
        "featuredSuppliers": [
            {
                "id": s.id,
                "name": s.name,
                "logo": s.logo,
                "category": s.category,
                "partnerSince": s.partner_since,
                "rating": float(s.rating) if s.rating else None,
                "growth": s.growth
            }
            for s in featured_suppliers
        ]
    }

# ==================== ANALYTICS TRACKING ENDPOINTS ====================

@router.post("/track/search")
async def track_search_query(
    query: str,
    results_count: int,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Track search queries for analytics."""
    from app.models.site import SearchQuery
    
    search_query = SearchQuery(
        query_text=query,
        user_id=user_id,
        session_id=session_id,
        results_count=results_count
    )
    db.add(search_query)
    await db.commit()
    
    return {"status": "tracked"}

@router.post("/track/event")
async def track_event(
    event_name: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Track custom events for analytics."""
    from app.models.site import Event, EventType
    
    # Get or create event type
    result = await db.execute(
        select(EventType).where(EventType.event_name == event_name)
    )
    event_type = result.scalar_one_or_none()
    
    if not event_type:
        event_type = EventType(event_name=event_name)
        db.add(event_type)
        await db.flush()
    
    # Create event
    event = Event(
        event_type_id=event_type.id,
        user_id=user_id,
        session_id=session_id
    )
    db.add(event)
    await db.commit()
    
    return {"status": "tracked"}

# Export router
__all__ = ["router"]


# # app/api/v1/site.py

# from typing import List, Optional
# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload

# from app.database import get_db
# from app.models.site import (
#     Feature, Stat, SocialLink, QuickLinkCategory, QuickLink,
#     PaymentMethod, ContactInfo, PromoMessage, Supplier, Store
# )

# router = APIRouter(prefix="/site", tags=["Site Data"])

# # ==================== PUBLIC ENDPOINTS ====================

# @router.get("/features")
# async def get_features(db: AsyncSession = Depends(get_db)):
#     """Get all active features for homepage."""
#     result = await db.execute(
#         select(Feature).order_by(Feature.id)
#     )
#     features = result.scalars().all()
    
#     return {
#         "features": [
#             {
#                 "icon": f.icon,
#                 "text": f.text,
#                 "subtext": f.subtext,
#                 "bgColor": f.bg_color,
#                 "iconColor": f.icon_color
#             }
#             for f in features
#         ]
#     }

# @router.get("/stats")
# async def get_stats(db: AsyncSession = Depends(get_db)):
#     """Get all stats for homepage."""
#     result = await db.execute(
#         select(Stat).order_by(Stat.id)
#     )
#     stats = result.scalars().all()
    
#     return {
#         "stats": [
#             {
#                 "icon": s.icon,
#                 "number": s.number,
#                 "label": s.label,
#                 "color": s.color
#             }
#             for s in stats
#         ]
#     }

# @router.get("/social-links")
# async def get_social_links(db: AsyncSession = Depends(get_db)):
#     """Get all social media links."""
#     result = await db.execute(
#         select(SocialLink).order_by(SocialLink.id)
#     )
#     links = result.scalars().all()
    
#     return {
#         "socialLinks": [
#             {
#                 "icon": link.icon,
#                 "href": link.href,
#                 "label": link.label,
#                 "color": link.color
#             }
#             for link in links
#         ]
#     }

# @router.get("/quick-links")
# async def get_quick_links(db: AsyncSession = Depends(get_db)):
#     """Get all quick links grouped by category."""
#     result = await db.execute(
#         select(QuickLinkCategory)
#         .options(selectinload(QuickLinkCategory.quick_links))
#         .order_by(QuickLinkCategory.id)
#     )
#     categories = result.scalars().all()
    
#     quick_links = {}
#     for category in categories:
#         quick_links[category.category] = [
#             {
#                 "name": link.name,
#                 "icon": link.icon
#             }
#             for link in category.quick_links
#         ]
    
#     return {"quickLinks": quick_links}

# @router.get("/payment-methods")
# async def get_payment_methods(db: AsyncSession = Depends(get_db)):
#     """Get all active payment methods."""
#     result = await db.execute(
#         select(PaymentMethod)
#         .where(PaymentMethod.is_active == True)
#         .order_by(PaymentMethod.id)
#     )
#     methods = result.scalars().all()
    
#     return {
#         "paymentMethods": [method.name for method in methods]
#     }

# @router.get("/contact-info")
# async def get_contact_info(db: AsyncSession = Depends(get_db)):
#     """Get contact information."""
#     result = await db.execute(select(ContactInfo).limit(1))
#     contact = result.scalar_one_or_none()
    
#     if not contact:
#         return {
#             "contact": {
#                 "address": {
#                     "line1": "",
#                     "line2": ""
#                 },
#                 "hours": {
#                     "weekdays": "",
#                     "weekends": ""
#                 },
#                 "phone": {
#                     "display": "",
#                     "href": ""
#                 },
#                 "email": ""
#             }
#         }
    
#     return {
#         "contact": {
#             "address": {
#                 "line1": contact.address_line1 or "",
#                 "line2": contact.address_line2 or ""
#             },
#             "hours": {
#                 "weekdays": contact.weekday_hours or "",
#                 "weekends": contact.weekend_hours or ""
#             },
#             "phone": {
#                 "display": contact.phone or "",
#                 "href": contact.phone_href or ""
#             },
#             "email": contact.email or ""
#         }
#     }

# @router.get("/promo-messages")
# async def get_promo_messages(db: AsyncSession = Depends(get_db)):
#     """Get active promotional messages."""
#     result = await db.execute(
#         select(PromoMessage)
#         .where(PromoMessage.is_active == True)
#         .order_by(PromoMessage.id)
#     )
#     messages = result.scalars().all()
    
#     return {
#         "promoMessages": [
#             {
#                 "icon": msg.icon,
#                 "text": msg.text,
#                 "cta": msg.cta
#             }
#             for msg in messages
#         ]
#     }

# @router.get("/suppliers")
# async def get_suppliers(
#     featured_only: bool = False,
#     category: Optional[str] = None,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get suppliers, optionally filtered by featured status or category."""
#     query = select(Supplier)
    
#     if featured_only:
#         query = query.where(Supplier.featured == True)
    
#     if category:
#         query = query.where(Supplier.category == category)
    
#     query = query.order_by(Supplier.name)
#     result = await db.execute(query)
#     suppliers = result.scalars().all()
    
#     return {
#         "suppliers": [
#             {
#                 "id": s.id,
#                 "name": s.name,
#                 "logo": s.logo,
#                 "category": s.category,
#                 "featured": s.featured,
#                 "partnerSince": s.partner_since,
#                 "rating": float(s.rating) if s.rating else None,
#                 "growth": s.growth
#             }
#             for s in suppliers
#         ]
#     }

# @router.get("/stores")
# async def get_stores(
#     city: Optional[str] = None,
#     featured_only: bool = False,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get stores with their services."""
#     query = select(Store).options(selectinload(Store.services))
    
#     if featured_only:
#         query = query.where(Store.featured == True)
    
#     if city:
#         query = query.where(Store.city.ilike(f"%{city}%"))
    
#     query = query.order_by(Store.featured.desc(), Store.name)
#     result = await db.execute(query)
#     stores = result.scalars().all()
    
#     return {
#         "stores": [
#             {
#                 "id": store.id,
#                 "name": store.name,
#                 "address": store.address,
#                 "city": store.city,
#                 "state": store.state,
#                 "zip": store.zip,
#                 "phone": store.phone,
#                 "hours": {
#                     "weekdays": store.hours_weekday,
#                     "weekends": store.hours_weekend
#                 },
#                 "rating": float(store.rating) if store.rating else None,
#                 "reviews": store.reviews,
#                 "distance": store.distance,
#                 "coordinates": {
#                     "lat": float(store.latitude) if store.latitude else None,
#                     "lng": float(store.longitude) if store.longitude else None
#                 },
#                 "isOpen": store.is_open,
#                 "featured": store.featured,
#                 "services": [service.service_name for service in store.services]
#             }
#             for store in stores
#         ]
#     }

# @router.get("/stores/{store_id}")
# async def get_store_details(
#     store_id: int,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get detailed information about a specific store."""
#     result = await db.execute(
#         select(Store)
#         .options(selectinload(Store.services))
#         .where(Store.id == store_id)
#     )
#     store = result.scalar_one_or_none()
    
#     if not store:
#         raise HTTPException(status_code=404, detail="Store not found")
    
#     return {
#         "store": {
#             "id": store.id,
#             "name": store.name,
#             "address": store.address,
#             "city": store.city,
#             "state": store.state,
#             "zip": store.zip,
#             "phone": store.phone,
#             "hours": {
#                 "weekdays": store.hours_weekday,
#                 "weekends": store.hours_weekend
#             },
#             "rating": float(store.rating) if store.rating else None,
#             "reviews": store.reviews,
#             "distance": store.distance,
#             "coordinates": {
#                 "lat": float(store.latitude) if store.latitude else None,
#                 "lng": float(store.longitude) if store.longitude else None
#             },
#             "isOpen": store.is_open,
#             "featured": store.featured,
#             "services": [service.service_name for service in store.services]
#         }
#     }

# @router.post("/newsletter/subscribe")
# async def subscribe_to_newsletter(
#     email: str,
#     first_name: Optional[str] = None,
#     last_name: Optional[str] = None,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Subscribe to newsletter."""
#     from app.models.site import NewsletterSubscriber
#     from sqlalchemy import select
    
#     # Check if already subscribed
#     existing = await db.execute(
#         select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
#     )
#     subscriber = existing.scalar_one_or_none()
    
#     if subscriber:
#         if subscriber.is_active:
#             return {"message": "Already subscribed", "status": "existing"}
#         else:
#             # Reactivate subscription
#             subscriber.is_active = True
#             subscriber.unsubscribed_at = None
#             if first_name:
#                 subscriber.first_name = first_name
#             if last_name:
#                 subscriber.last_name = last_name
#             await db.commit()
#             return {"message": "Subscription reactivated", "status": "reactivated"}
    
#     # Create new subscriber
#     new_subscriber = NewsletterSubscriber(
#         email=email,
#         first_name=first_name,
#         last_name=last_name,
#         is_active=True
#     )
#     db.add(new_subscriber)
#     await db.commit()
    
#     return {"message": "Successfully subscribed", "status": "new"}

# @router.post("/newsletter/unsubscribe")
# async def unsubscribe_from_newsletter(
#     email: str,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Unsubscribe from newsletter."""
#     from app.models.site import NewsletterSubscriber
#     from datetime import datetime
    
#     result = await db.execute(
#         select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
#     )
#     subscriber = result.scalar_one_or_none()
    
#     if not subscriber:
#         raise HTTPException(status_code=404, detail="Email not found")
    
#     if not subscriber.is_active:
#         return {"message": "Already unsubscribed", "status": "already_unsubscribed"}
    
#     subscriber.is_active = False
#     subscriber.unsubscribed_at = datetime.utcnow()
#     await db.commit()
    
#     return {"message": "Successfully unsubscribed", "status": "unsubscribed"}

# # ==================== COMPOSITE ENDPOINTS ====================

# @router.get("/footer-data")
# async def get_footer_data(db: AsyncSession = Depends(get_db)):
#     """Get all data needed for the footer in one request."""
#     # Get quick links
#     quick_links_result = await db.execute(
#         select(QuickLinkCategory)
#         .options(selectinload(QuickLinkCategory.quick_links))
#         .order_by(QuickLinkCategory.id)
#     )
#     categories = quick_links_result.scalars().all()
    
#     quick_links = {}
#     for category in categories:
#         quick_links[category.category] = [
#             {"name": link.name, "icon": link.icon}
#             for link in category.quick_links
#         ]
    
#     # Get contact info
#     contact_result = await db.execute(select(ContactInfo).limit(1))
#     contact = contact_result.scalar_one_or_none()
    
#     contact_data = {
#         "address": {
#             "line1": contact.address_line1 or "" if contact else "",
#             "line2": contact.address_line2 or "" if contact else ""
#         },
#         "hours": {
#             "weekdays": contact.weekday_hours or "" if contact else "",
#             "weekends": contact.weekend_hours or "" if contact else ""
#         },
#         "phone": {
#             "display": contact.phone or "" if contact else "",
#             "href": contact.phone_href or "" if contact else ""
#         },
#         "email": contact.email or "" if contact else ""
#     }
    
#     # Get social links
#     social_result = await db.execute(
#         select(SocialLink).order_by(SocialLink.id)
#     )
#     social_links = social_result.scalars().all()
    
#     # Get payment methods
#     payment_result = await db.execute(
#         select(PaymentMethod)
#         .where(PaymentMethod.is_active == True)
#         .order_by(PaymentMethod.id)
#     )
#     payment_methods = payment_result.scalars().all()
    
#     return {
#         "quickLinks": quick_links,
#         "contact": contact_data,
#         "socialLinks": [
#             {
#                 "icon": link.icon,
#                 "href": link.href,
#                 "label": link.label,
#                 "color": link.color
#             }
#             for link in social_links
#         ],
#         "paymentMethods": [method.name for method in payment_methods]
#     }

# @router.get("/homepage-data")
# async def get_homepage_data(db: AsyncSession = Depends(get_db)):
#     """Get all data needed for the homepage in one request."""
#     # Get features
#     features_result = await db.execute(
#         select(Feature).order_by(Feature.id)
#     )
#     features = features_result.scalars().all()
    
#     # Get stats
#     stats_result = await db.execute(
#         select(Stat).order_by(Stat.id)
#     )
#     stats = stats_result.scalars().all()
    
#     # Get promo messages
#     promo_result = await db.execute(
#         select(PromoMessage)
#         .where(PromoMessage.is_active == True)
#         .order_by(PromoMessage.id)
#     )
#     promo_messages = promo_result.scalars().all()
    
#     # Get featured suppliers
#     suppliers_result = await db.execute(
#         select(Supplier)
#         .where(Supplier.featured == True)
#         .order_by(Supplier.name)
#         .limit(6)  # Limit to 6 featured suppliers
#     )
#     featured_suppliers = suppliers_result.scalars().all()
    
#     return {
#         "features": [
#             {
#                 "icon": f.icon,
#                 "text": f.text,
#                 "subtext": f.subtext,
#                 "bgColor": f.bg_color,
#                 "iconColor": f.icon_color
#             }
#             for f in features
#         ],
#         "stats": [
#             {
#                 "icon": s.icon,
#                 "number": s.number,
#                 "label": s.label,
#                 "color": s.color
#             }
#             for s in stats
#         ],
#         "promoMessages": [
#             {
#                 "icon": msg.icon,
#                 "text": msg.text,
#                 "cta": msg.cta
#             }
#             for msg in promo_messages
#         ],
#         "featuredSuppliers": [
#             {
#                 "id": s.id,
#                 "name": s.name,
#                 "logo": s.logo,
#                 "category": s.category,
#                 "partnerSince": s.partner_since,
#                 "rating": float(s.rating) if s.rating else None,
#                 "growth": s.growth
#             }
#             for s in featured_suppliers
#         ]
#     }

# # ==================== ANALYTICS TRACKING ENDPOINTS ====================

# @router.post("/track/search")
# async def track_search_query(
#     query: str,
#     results_count: int,
#     user_id: Optional[int] = None,
#     session_id: Optional[str] = None,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Track search queries for analytics."""
#     from app.models.site import SearchQuery
    
#     search_query = SearchQuery(
#         query_text=query,
#         user_id=user_id,
#         session_id=session_id,
#         results_count=results_count
#     )
#     db.add(search_query)
#     await db.commit()
    
#     return {"status": "tracked"}

# @router.post("/track/event")
# async def track_event(
#     event_name: str,
#     # metadata: Optional[dict] = None,
#     user_id: Optional[int] = None,
#     session_id: Optional[str] = None,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Track custom events for analytics."""
#     from app.models.site import Event, EventType
    
#     # Get or create event type
#     result = await db.execute(
#         select(EventType).where(EventType.event_name == event_name)
#     )
#     event_type = result.scalar_one_or_none()
    
#     if not event_type:
#         event_type = EventType(event_name=event_name)
#         db.add(event_type)
#         await db.flush()
    
#     # Create event
#     event = Event(
#         event_type_id=event_type.id,
#         user_id=user_id,
#         session_id=session_id,
#         # metadata=metadata or {}
#     )
#     db.add(event)
#     await db.commit()
    
#     return {"status": "tracked"}

# # Export router
# __all__ = ["router"]