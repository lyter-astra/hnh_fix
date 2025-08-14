from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, JSON, TIMESTAMP, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from app.models.base import BaseModel

class AdminUser(BaseModel):
    __tablename__ = "admin_users"
    
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    role_id = Column(Integer, ForeignKey("admin_roles.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)
    last_login = Column(TIMESTAMP)
    profile_picture = Column(Text)
    phone = Column(String(20))
    department = Column(String(100))
    
    # Relationships
    role = relationship("AdminRole", back_populates="users")
    audit_logs = relationship("AdminAuditLog", back_populates="admin_user")
    notifications = relationship("AdminNotification", back_populates="admin_user")


class AdminRole(BaseModel):
    __tablename__ = "admin_roles"
    
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    permissions = Column(JSONB)  # Store permissions as JSON
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("AdminUser", back_populates="role")


class AdminAuditLog(BaseModel):
    __tablename__ = "admin_audit_logs"
    
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    action_type = Column(String(100), nullable=False)  # create, update, delete, export, login
    table_affected = Column(String(100))
    record_id = Column(Integer)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    ip_address = Column(Text)
    user_agent = Column(Text)
    # metadata = Column(JSONB)
    
    # Relationships
    admin_user = relationship("AdminUser", back_populates="audit_logs")


class AdminNotification(BaseModel):
    __tablename__ = "admin_notifications"
    
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"))
    type = Column(String(50), nullable=False)  # low_stock, new_order, review_pending, etc.
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    is_read = Column(Boolean, default=False)
    # metadata = Column(JSONB)
    action_url = Column(Text)  # Link to relevant admin page
    
    # Relationships
    admin_user = relationship("AdminUser", back_populates="notifications")


class SystemSetting(BaseModel):
    __tablename__ = "system_settings"
    
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    type = Column(String(50), default="string")  # string, integer, boolean, json
    category = Column(String(100))  # general, email, payment, shipping, etc.
    description = Column(Text)
    is_public = Column(Boolean, default=False)  # Whether visible to non-admin users


class EmailTemplate(BaseModel):
    __tablename__ = "email_templates"
    
    name = Column(String(100), unique=True, nullable=False)
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text)
    variables = Column(JSONB)  # Available template variables
    category = Column(String(50))  # order, user, marketing, system
    is_active = Column(Boolean, default=True)


class ReportSchedule(BaseModel):
    __tablename__ = "report_schedules"
    
    name = Column(String(100), nullable=False)
    report_type = Column(String(50), nullable=False)  # sales, inventory, customer, etc.
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly
    schedule_time = Column(String(10))  # HH:MM format
    recipients = Column(ARRAY(String))  # Email addresses
    parameters = Column(JSONB)  # Report-specific parameters
    last_run = Column(TIMESTAMP)
    next_run = Column(TIMESTAMP)
    is_active = Column(Boolean, default=True)


class BulkOperation(BaseModel):
    __tablename__ = "bulk_operations"
    
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    operation_type = Column(String(50), nullable=False)  # import, export, update, delete
    entity_type = Column(String(50), nullable=False)  # products, orders, customers, etc.
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    total_records = Column(Integer)
    processed_records = Column(Integer, default=0)
    success_records = Column(Integer, default=0)
    error_records = Column(Integer, default=0)
    file_url = Column(Text)
    error_file_url = Column(Text)
    parameters = Column(JSONB)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    
    # Relationships
    admin_user = relationship("AdminUser")


class DashboardWidget(BaseModel):
    __tablename__ = "dashboard_widgets"
    
    name = Column(String(100), nullable=False)
    widget_type = Column(String(50), nullable=False)  # chart, stat, table, etc.
    query = Column(Text)  # SQL query or API endpoint
    config = Column(JSONB)  # Widget-specific configuration
    position = Column(Integer)
    size = Column(String(20))  # small, medium, large, full
    refresh_interval = Column(Integer)  # In seconds
    roles = Column(ARRAY(String))  # Which roles can see this widget
    is_active = Column(Boolean, default=True)


class ExportHistory(BaseModel):
    __tablename__ = "export_history"
    
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    export_type = Column(String(50), nullable=False)  # orders, products, customers, etc.
    format = Column(String(20), nullable=False)  # csv, excel, pdf
    filters = Column(JSONB)  # Applied filters
    file_url = Column(Text)
    file_size = Column(Integer)
    record_count = Column(Integer)
    status = Column(String(20), default="pending")
    error_message = Column(Text)
    expires_at = Column(TIMESTAMP)
    
    # Relationships
    admin_user = relationship("AdminUser")


class LoginAttempt(BaseModel):
    __tablename__ = "login_attempts"
    
    email = Column(String(255), nullable=False)
    ip_address = Column(Text)
    user_agent = Column(Text)
    success = Column(Boolean, default=False)
    failure_reason = Column(String(100))
    attempted_at = Column(TIMESTAMP, nullable=False)


class APIKey(BaseModel):
    __tablename__ = "api_keys"
    
    name = Column(String(100), nullable=False)
    key_hash = Column(Text, nullable=False)
    permissions = Column(JSONB)
    rate_limit = Column(Integer, default=1000)  # Requests per hour
    last_used_at = Column(TIMESTAMP)
    expires_at = Column(TIMESTAMP)
    is_active = Column(Boolean, default=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"))
    
    # Relationships
    admin_user = relationship("AdminUser")


class Webhook(BaseModel):
    __tablename__ = "webhooks"
    
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    events = Column(ARRAY(String))  # order.created, product.updated, etc.
    headers = Column(JSONB)
    secret = Column(Text)
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(TIMESTAMP)
    failure_count = Column(Integer, default=0)
    
    # Relationships
    logs = relationship("WebhookLog", back_populates="webhook")


class WebhookLog(BaseModel):
    __tablename__ = "webhook_logs"
    
    webhook_id = Column(Integer, ForeignKey("webhooks.id"), nullable=False)
    event = Column(String(100), nullable=False)
    payload = Column(JSONB)
    response_status = Column(Integer)
    response_body = Column(Text)
    attempt_count = Column(Integer, default=1)
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    
    # Relationships
    webhook = relationship("Webhook", back_populates="logs")


class InventoryAdjustment(BaseModel):
    __tablename__ = "inventory_adjustments"
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"))
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    adjustment_type = Column(String(50), nullable=False)  # manual, return, damage, recount
    quantity_before = Column(Integer, nullable=False)
    quantity_adjusted = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(Text)
    reference_type = Column(String(50))  # order, return, etc.
    reference_id = Column(Integer)
    
    # Relationships
    product = relationship("Product")
    variant = relationship("ProductVariant")
    admin_user = relationship("AdminUser")


class PriceHistory(BaseModel):
    __tablename__ = "price_history"
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"))
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    price_before = Column(Numeric(10, 2), nullable=False)
    price_after = Column(Numeric(10, 2), nullable=False)
    cost_before = Column(Numeric(10, 2))
    cost_after = Column(Numeric(10, 2))
    reason = Column(Text)
    
    # Relationships
    product = relationship("Product")
    variant = relationship("ProductVariant")
    admin_user = relationship("AdminUser")


class TaxRate(BaseModel):
    __tablename__ = "tax_rates"
    
    name = Column(String(100), nullable=False)
    rate = Column(Numeric(5, 2), nullable=False)  # Percentage
    country = Column(String(2))
    state = Column(String(100))
    zip_code = Column(String(20))
    tax_class = Column(String(50))  # standard, reduced, zero
    is_compound = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)


class ShippingZone(BaseModel):
    __tablename__ = "shipping_zones"
    
    name = Column(String(100), nullable=False)
    countries = Column(ARRAY(String))
    states = Column(ARRAY(String))
    zip_codes = Column(ARRAY(String))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    methods = relationship("ShippingMethod", back_populates="zone")


class ShippingMethod(BaseModel):
    __tablename__ = "shipping_methods"
    
    zone_id = Column(Integer, ForeignKey("shipping_zones.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    calculation_type = Column(String(50))  # flat_rate, weight_based, price_based
    base_cost = Column(Numeric(10, 2))
    min_weight = Column(Numeric(8, 2))
    max_weight = Column(Numeric(8, 2))
    min_price = Column(Numeric(10, 2))
    max_price = Column(Numeric(10, 2))
    delivery_days_min = Column(Integer)
    delivery_days_max = Column(Integer)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    zone = relationship("ShippingZone", back_populates="methods")


class MarketingCampaign(BaseModel):
    __tablename__ = "marketing_campaigns"
    
    name = Column(String(200), nullable=False)
    type = Column(String(50))  # email, sms, push, banner
    status = Column(String(20), default="draft")  # draft, scheduled, active, paused, completed
    target_audience = Column(JSONB)  # Segmentation criteria
    content = Column(JSONB)  # Campaign content
    schedule_start = Column(TIMESTAMP)
    schedule_end = Column(TIMESTAMP)
    budget = Column(Numeric(10, 2))
    spent = Column(Numeric(10, 2), default=0)
    metrics = Column(JSONB)  # views, clicks, conversions, etc.
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"))
    
    # Relationships
    admin_user = relationship("AdminUser")


class CustomerSegment(BaseModel):
    __tablename__ = "customer_segments"
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    criteria = Column(JSONB)  # Segmentation rules
    customer_count = Column(Integer, default=0)
    is_dynamic = Column(Boolean, default=True)  # Auto-update membership
    last_updated = Column(TIMESTAMP)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"))
    
    # Relationships
    admin_user = relationship("AdminUser")