import os
from pydantic_settings import BaseSettings
from pydantic import Extra
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://hnh_ehouseandhome:knAAApGzBILkR6ZxhelNz4q11RUVBCCY@dpg-d22bt5vgi27c73epjhg0-a/hnh_ehouseandhome_5ir6"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Security
    secret_key: str = "rebw54t54tcw54t54wy54"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1200
    
    # Admin Security Settings
    admin_token_expire_minutes: int = 60  # Admin tokens expire faster
    refresh_secret_key: str = os.getenv("REFRESH_SECRET_KEY", "your-refresh-secret-key-here")
    refresh_token_expire_days: int = 30
    
    # Password Security
    password_reset_token_expire_hours: int = 24
    email_verification_token_expire_days: int = 7
    session_token_expire_days: int = 30
    
    # Password Policy
    min_password_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special: bool = True
    
    # CORS
    allowed_origins: list[str] = ["*"]
    
    # Paynow Configuration - All with proper type annotations
    PAYNOW_INTEGRATION_ID: str = "21436"
    PAYNOW_INTEGRATION_KEY: str = "9597bbe1-5f34-4910-bb1b-58141ade69ba"
    PAYNOW_RETURN_URL: str = "https://houseandhome.co.zw/payment-return"
    PAYNOW_RESULT_URL: str = "https://houseandhome.co.zw/api/paynow/webhook"
    PAYNOW_ENVIRONMENT: str = "production" # "sandbox" or "production"
        
    # API Settings
    api_v1_prefix: str = "/api"
    project_name: str = "House & Home E-commerce API"
    version: str = "1.7.2"
    
    # Site Settings
    site_name: str = "House & Home"
    site_url: str = os.getenv("SITE_URL", "http://localhost:8080")
    
    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100
    
    # File Upload and Storage
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_upload_size: int = 10 * 1024 * 1024  # 10MB (alias for compatibility)
    max_image_size: int = 5 * 1024 * 1024   # 5MB
    upload_dir: str = "uploads"
    
    # Export/Import Paths
    export_path: str = os.getenv("EXPORT_PATH", "./exports")
    export_url_prefix: str = "/exports"
    upload_path: str = os.getenv("UPLOAD_PATH", "./uploads")
    upload_url_prefix: str = "/uploads"
    report_path: str = os.getenv("REPORT_PATH", "./reports")
    report_url_prefix: str = "/reports"
    
    # S3 Configuration (optional)
    use_s3: bool = os.getenv("USE_S3", "false").lower() == "true"
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY", None)
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: Optional[str] = os.getenv("S3_BUCKET", None)
    
    # Email Configuration (Enhanced)
    smtp_server: Optional[str] = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")  # Alias for compatibility
    smtp_port: Optional[int] = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: Optional[str] = os.getenv("SMTP_USERNAME", None)
    smtp_user: Optional[str] = os.getenv("SMTP_USER", None)  # Alias for compatibility
    smtp_password: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    from_email: str = os.getenv("FROM_EMAIL", "noreply@houseandhome.co.zw")
    from_name: str = os.getenv("FROM_NAME", "House & Home")
    
    # Environment
    environment: str = "development"
    debug: bool = False
    
    # Admin Dashboard Settings
    dashboard_refresh_interval: int = 300  # 5 minutes in seconds
    max_audit_log_days: int = 365  # Keep audit logs for 1 year
    max_export_retention_days: int = 7  # Keep export files for 7 days
    
    # Rate Limiting
    rate_limit_requests: int = 100  # Requests per window
    rate_limit_window: int = 60  # Window in seconds
    
    # Analytics Settings
    analytics_retention_days: int = 90  # Keep analytics data for 90 days
    
    # Webhook Settings
    webhook_timeout: int = 30  # Seconds
    webhook_max_retries: int = 3
    
    # Bulk Operations
    bulk_operation_chunk_size: int = 100
    max_csv_rows: int = 10000
    
    @property
    def paynow_url(self) -> str:
        """Get Paynow URL based on environment"""
        if self.PAYNOW_ENVIRONMENT == "production":
            return "https://www.paynow.co.zw/interface/initiatetransaction"
        else:
            return "https://sandbox.paynow.co.zw/interface/initiatetransaction"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"
    
    def get_smtp_settings(self) -> dict:
        """Get SMTP settings for email service"""
        return {
            "host": self.smtp_server or self.smtp_host,
            "port": self.smtp_port,
            "username": self.smtp_username or self.smtp_user,
            "password": self.smtp_password,
            "from_email": self.from_email,
            "from_name": self.from_name
        }

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = Extra.allow


settings = Settings()

