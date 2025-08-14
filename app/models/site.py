# app/models/site.py

from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, JSON, TIMESTAMP, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from app.models.base import BaseModel

# ==================== HERO SECTION MODELS ====================

class HeroImage(BaseModel):
    __tablename__ = "hero_images"
    
    image_url = Column(Text, nullable=False)
    alt_text = Column(String(255))
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)


class HeroConfig(BaseModel):
    __tablename__ = "hero_config"
    
    config_name = Column(String(100), unique=True, nullable=False)
    title_primary = Column(String(255), nullable=False)
    title_secondary = Column(String(255), nullable=False)
    subtitle = Column(String(255))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    buttons = relationship("HeroButton", back_populates="hero_config", cascade="all, delete-orphan")
    price_tags = relationship("HeroPriceTag", back_populates="hero_config", cascade="all, delete-orphan")


class HeroButton(BaseModel):
    __tablename__ = "hero_buttons"
    
    hero_config_id = Column(Integer, ForeignKey("hero_config.id"), nullable=False)
    button_type = Column(String(50), nullable=False)  # 'primary' or 'secondary'
    button_text = Column(String(100), nullable=False)
    button_icon = Column(String(50))
    button_url = Column(String(500))
    button_action = Column(String(100))
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    hero_config = relationship("HeroConfig", back_populates="buttons")


class HeroPriceTag(BaseModel):
    __tablename__ = "hero_price_tags"
    
    hero_config_id = Column(Integer, ForeignKey("hero_config.id"), nullable=False)
    label = Column(String(50), nullable=False)
    price = Column(String(20), nullable=False)
    currency_code = Column(String(3), default='USD')
    is_active = Column(Boolean, default=True)
    
    # Relationships
    hero_config = relationship("HeroConfig", back_populates="price_tags")


# ==================== EXISTING MODELS ====================

class Feature(BaseModel):
    __tablename__ = "features"
    
    icon = Column(String(50), nullable=False)
    text = Column(String(100), nullable=False)
    subtext = Column(String(100))
    bg_color = Column(String(50))
    icon_color = Column(String(50))


class Stat(BaseModel):
    __tablename__ = "stats"
    
    icon = Column(String(50), nullable=False)
    number = Column(String(20), nullable=False)
    label = Column(String(100), nullable=False)
    color = Column(String(50))


class SocialLink(BaseModel):
    __tablename__ = "social_links"
    
    icon = Column(String(50), nullable=False)
    href = Column(String(255), nullable=False)
    label = Column(String(50), nullable=False)
    color = Column(String(50))


class QuickLinkCategory(BaseModel):
    __tablename__ = "quick_link_categories"
    
    category = Column(String(50), nullable=False)
    icon = Column(String(50))
    
    # Relationships
    quick_links = relationship("QuickLink", back_populates="category", cascade="all, delete-orphan")


class QuickLink(BaseModel):
    __tablename__ = "quick_links"
    
    category_id = Column(Integer, ForeignKey("quick_link_categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    icon = Column(String(50))
    
    # Relationships
    category = relationship("QuickLinkCategory", back_populates="quick_links")


class PaymentMethod(BaseModel):
    __tablename__ = "payment_methods"
    
    name = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)


class ContactInfo(BaseModel):
    __tablename__ = "contact_info"
    
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    weekday_hours = Column(String(100))
    weekend_hours = Column(String(100))
    phone = Column(String(50))
    phone_href = Column(String(50))
    email = Column(String(100))


class PromoMessage(BaseModel):
    __tablename__ = "promo_messages"
    
    icon = Column(String(50))
    text = Column(Text, nullable=False)
    cta = Column(String(50))
    is_active = Column(Boolean, default=True)


class Supplier(BaseModel):
    __tablename__ = "suppliers"
    
    name = Column(String(100), nullable=False)
    logo = Column(String(500))
    category = Column(String(100))
    featured = Column(Boolean, default=False)
    partner_since = Column(String(20))
    rating = Column(Numeric(2, 1))
    growth = Column(String(20))


class Store(BaseModel):
    __tablename__ = "stores"
    
    name = Column(String(100), nullable=False)
    address = Column(String(255))
    city = Column(String(100))
    state = Column(String(50))
    zip = Column(String(20))
    phone = Column(String(50))
    hours_weekday = Column(String(100))
    hours_weekend = Column(String(100))
    rating = Column(Numeric(2, 1))
    reviews = Column(Integer)
    distance = Column(String(50))
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    is_open = Column(Boolean, default=True)
    featured = Column(Boolean, default=False)
    
    # Relationships
    services = relationship("StoreService", back_populates="store", cascade="all, delete-orphan")


class StoreService(BaseModel):
    __tablename__ = "store_services"
    
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    service_name = Column(String(100), nullable=False)
    
    # Relationships
    store = relationship("Store", back_populates="services")


class SearchQuery(BaseModel):
    __tablename__ = "search_queries"
    
    query_text = Column(String(500), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(100))
    results_count = Column(Integer)
    
    # Relationships
    user = relationship("User", backref="search_queries")


class TrafficSource(BaseModel):
    __tablename__ = "traffic_sources"
    
    source = Column(String(100), nullable=False)
    medium = Column(String(100))
    campaign = Column(String(200))
    sessions = Column(Integer, default=0)
    users = Column(Integer, default=0)
    bounce_rate = Column(Numeric(5, 2))


class RecentActivity(BaseModel):
    __tablename__ = "recent_activity"
    
    activity_type = Column(String(50), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    # metadata = Column(JSONB)
    
    # Relationships
    user = relationship("User", backref="recent_activities")


class NewsletterSubscriber(BaseModel):
    __tablename__ = "newsletter_subscribers"
    
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    subscribed_at = Column(TIMESTAMP, nullable=False, server_default="CURRENT_TIMESTAMP")
    unsubscribed_at = Column(TIMESTAMP)


class EventType(BaseModel):
    __tablename__ = "event_types"
    
    event_name = Column(String(100), nullable=False)
    category = Column(String(50))
    
    # Relationships
    events = relationship("Event", back_populates="event_type")


class Event(BaseModel):
    __tablename__ = "events"
    
    event_type_id = Column(Integer, ForeignKey("event_types.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(100))
    meta_data = Column(JSONB)
    
    # Relationships
    event_type = relationship("EventType", back_populates="events")
    user = relationship("User", backref="events")


class ConversionFunnel(BaseModel):
    __tablename__ = "conversion_funnel"
    
    date = Column(Date, nullable=False)
    visitors = Column(Integer, default=0)
    product_views = Column(Integer, default=0)
    add_to_cart = Column(Integer, default=0)
    add_to_wishlist = Column(Integer, default=0)
    checkout = Column(Integer, default=0)
    purchase = Column(Integer, default=0)
    
    
# # app/models/site.py

# from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, JSON, TIMESTAMP, Numeric, Date
# from sqlalchemy.orm import relationship
# from sqlalchemy.dialects.postgresql import ARRAY, JSONB
# from app.models.base import BaseModel

# class Feature(BaseModel):
#     __tablename__ = "features"
    
#     icon = Column(String(50), nullable=False)
#     text = Column(String(100), nullable=False)
#     subtext = Column(String(100))
#     bg_color = Column(String(50))
#     icon_color = Column(String(50))


# class Stat(BaseModel):
#     __tablename__ = "stats"
    
#     icon = Column(String(50), nullable=False)
#     number = Column(String(20), nullable=False)
#     label = Column(String(100), nullable=False)
#     color = Column(String(50))


# class SocialLink(BaseModel):
#     __tablename__ = "social_links"
    
#     icon = Column(String(50), nullable=False)
#     href = Column(String(255), nullable=False)
#     label = Column(String(50), nullable=False)
#     color = Column(String(50))


# class QuickLinkCategory(BaseModel):
#     __tablename__ = "quick_link_categories"
    
#     category = Column(String(50), nullable=False)
#     icon = Column(String(50))
    
#     # Relationships
#     quick_links = relationship("QuickLink", back_populates="category", cascade="all, delete-orphan")


# class QuickLink(BaseModel):
#     __tablename__ = "quick_links"
    
#     category_id = Column(Integer, ForeignKey("quick_link_categories.id"), nullable=False)
#     name = Column(String(100), nullable=False)
#     icon = Column(String(50))
    
#     # Relationships
#     category = relationship("QuickLinkCategory", back_populates="quick_links")


# class PaymentMethod(BaseModel):
#     __tablename__ = "payment_methods"
    
#     name = Column(String(50), nullable=False)
#     is_active = Column(Boolean, default=True)


# class ContactInfo(BaseModel):
#     __tablename__ = "contact_info"
    
#     address_line1 = Column(String(255))
#     address_line2 = Column(String(255))
#     weekday_hours = Column(String(100))
#     weekend_hours = Column(String(100))
#     phone = Column(String(50))
#     phone_href = Column(String(50))
#     email = Column(String(100))


# class PromoMessage(BaseModel):
#     __tablename__ = "promo_messages"
    
#     icon = Column(String(50))
#     text = Column(Text, nullable=False)
#     cta = Column(String(50))
#     is_active = Column(Boolean, default=True)


# class Supplier(BaseModel):
#     __tablename__ = "suppliers"
    
#     name = Column(String(100), nullable=False)
#     logo = Column(String(500))
#     category = Column(String(100))
#     featured = Column(Boolean, default=False)
#     partner_since = Column(String(20))
#     rating = Column(Numeric(2, 1))
#     growth = Column(String(20))


# class Store(BaseModel):
#     __tablename__ = "stores"
    
#     name = Column(String(100), nullable=False)
#     address = Column(String(255))
#     city = Column(String(100))
#     state = Column(String(50))
#     zip = Column(String(20))
#     phone = Column(String(50))
#     hours_weekday = Column(String(100))
#     hours_weekend = Column(String(100))
#     rating = Column(Numeric(2, 1))
#     reviews = Column(Integer)
#     distance = Column(String(50))
#     latitude = Column(Numeric(10, 7))
#     longitude = Column(Numeric(10, 7))
#     is_open = Column(Boolean, default=True)
#     featured = Column(Boolean, default=False)
    
#     # Relationships
#     services = relationship("StoreService", back_populates="store", cascade="all, delete-orphan")


# class StoreService(BaseModel):
#     __tablename__ = "store_services"
    
#     store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
#     service_name = Column(String(100), nullable=False)
    
#     # Relationships
#     store = relationship("Store", back_populates="services")


# class SearchQuery(BaseModel):
#     __tablename__ = "search_queries"
    
#     query_text = Column(String(500), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"))
#     session_id = Column(String(100))
#     results_count = Column(Integer)
    
#     # Relationships
#     user = relationship("User", backref="search_queries")


# class TrafficSource(BaseModel):
#     __tablename__ = "traffic_sources"
    
#     source = Column(String(100), nullable=False)
#     medium = Column(String(100))
#     campaign = Column(String(200))
#     sessions = Column(Integer, default=0)
#     users = Column(Integer, default=0)
#     bounce_rate = Column(Numeric(5, 2))


# class RecentActivity(BaseModel):
#     __tablename__ = "recent_activity"
    
#     activity_type = Column(String(50), nullable=False)
#     description = Column(Text)
#     user_id = Column(Integer, ForeignKey("users.id"))
#     # metadata = Column(JSONB)
    
#     # Relationships
#     user = relationship("User", backref="recent_activities")


# class NewsletterSubscriber(BaseModel):
#     __tablename__ = "newsletter_subscribers"
    
#     email = Column(String(255), unique=True, nullable=False)
#     first_name = Column(String(100))
#     last_name = Column(String(100))
#     is_active = Column(Boolean, default=True)
#     subscribed_at = Column(TIMESTAMP, nullable=False, server_default="CURRENT_TIMESTAMP")
#     unsubscribed_at = Column(TIMESTAMP)


# class EventType(BaseModel):
#     __tablename__ = "event_types"
    
#     event_name = Column(String(100), nullable=False)
#     category = Column(String(50))
    
#     # Relationships
#     events = relationship("Event", back_populates="event_type")


# class Event(BaseModel):
#     __tablename__ = "events"
    
#     event_type_id = Column(Integer, ForeignKey("event_types.id"), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"))
#     session_id = Column(String(100))
#     # metadata = Column(JSONB)
    
#     # Relationships
#     event_type = relationship("EventType", back_populates="events")
#     user = relationship("User", backref="events")


# class ConversionFunnel(BaseModel):
#     __tablename__ = "conversion_funnel"
    
#     date = Column(Date, nullable=False)
#     visitors = Column(Integer, default=0)
#     product_views = Column(Integer, default=0)
#     add_to_cart = Column(Integer, default=0)
#     add_to_wishlist = Column(Integer, default=0)
#     checkout = Column(Integer, default=0)
#     purchase = Column(Integer, default=0)