import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine
from contextlib import asynccontextmanager
import time
from app.config import settings
from app.api import auth, products, users, cart, categories,  orders, paynow, xadmin, auth_admin, site, site_admin

# Database engine
# DATABASE_URL = os.getenv("DATABASE_URL","postgresql+asyncpg://postgres:root@localhost/ecommerce_db")

DATABASE_URL = os.getenv("DATABASE_URL","postgresql+asyncpg://hnh_ehouseandhome:knAAApGzBILkR6ZxhelNz4q11RUVBCCY@dpg-d22bt5vgi27c73epjhg0-a/hnh_ehouseandhome_5ir6")
engine = create_async_engine(DATABASE_URL, echo=settings.debug)

from pathlib import Path

async def initialize_schema():
    print("🛠 Initializing database schema from init_schema.sql...")
    try:
        schema_path = Path(__file__).parent.parent / "init_schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_commands = f.read()

        # Split commands by semicolon, but beware of semicolons inside functions or strings:
        # For most cases, a simple split on semicolon works fine if your SQL is straightforward.
        commands = [cmd.strip() for cmd in sql_commands.split(";") if cmd.strip()]

        async with engine.begin() as conn:
            for cmd in commands:
                await conn.exec_driver_sql(cmd)

        print("✅ Database schema initialized successfully.")
    except Exception as e:
        print(f"❌ Failed to initialize schema: {e}")


# Application lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting up House & Home E-commerce API...")
    # await initialize_schema()
    yield
    print("🛑 Shutting down House & Home E-commerce API...")
    await engine.dispose()

# FastAPI application setup
app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description="""
        🚀 High-Performance House & Home E-Commerce Server

        Welcome to the backend engine powering a modern, scalable, and lightning-fast e-commerce platform.
        This Server is designed with performance, security, and developer experience at its core.

        ✨ Features
        - Secure Authentication & Authorization
        - Product & Category Management
        - Cart and Checkout Logic
        - Order Processing System
        - Admin and User Interfaces
        - Payment Gateway Integrations
        - Scalable Microservice Architecture Ready
        - Comprehensive API Documentation
       
        ---
  
        👨‍💻 Developed & Maintained By
        AstraMinds — Your Ultimate Partner for All Business Technology Needs 
        Harare, Zimbabwe 🇿🇼  
        📞 +263 771 393 916  
        📧 info@astraminds.co.zw  
        🌐 https://www.astraminds.co.zw

        ---
    """,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],  # Allow all origins in development
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "https://houseandhome.co.zw/",  # Add your production frontend URL
        # Or use ["*"] to allow all origins (not recommended for production)
    ],
)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allows all headers
    expose_headers=["*"]  # Exposes all headers to the frontend
)

# Trusted Host middleware (only in production)
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["houseandhome.co.zw", "*.houseandhome.co.zw"]
    )

# Middleware to measure request processing time
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    response.headers["X-Process-Time"] = str(duration)
    return response

# Global error handler
@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.debug else "Something went wrong"
        }
    )

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to House & Home E-commerce API!",
        "status": "running",
        "version": settings.version,
        "environment": settings.environment,
        "developer": "AstraMinds",
        "developer_site": "https://astraminds.co.zw/"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "message": "House & Home E-commerce API",
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.version,
        "docs": "/docs" if settings.debug else None,
        "health": "/health",
        "developer": "AstraMinds",
        "developer_site": "https://astraminds.co.zw"
    }

# Register routers
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(categories.router, prefix=settings.api_v1_prefix)
app.include_router(products.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(cart.router, prefix=settings.api_v1_prefix)

app.include_router(orders.router, prefix=settings.api_v1_prefix)
app.include_router(paynow.router, prefix=settings.api_v1_prefix)

app.include_router(auth_admin.router, prefix=settings.api_v1_prefix)
app.include_router(xadmin.router, prefix=settings.api_v1_prefix)

app.include_router(site.router, prefix=settings.api_v1_prefix)
app.include_router(site_admin.router, prefix=settings.api_v1_prefix)

# Entry point for local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )

