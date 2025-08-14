# 🏪 House & Home E-commerce API

A high-performance, scalable FastAPI backend for commercial e-commerce platforms. Built with modern Python async/await patterns, SQLAlchemy 2.0, and optimized for production deployment on Render.

## ✨ Features

- **🚀 High Performance**: Async FastAPI with Uvicorn workers via Gunicorn
- **🗄️ Modern Database**: PostgreSQL with SQLAlchemy 2.0 async ORM
- **🔐 Secure Authentication**: JWT tokens with bcrypt password hashing
- **📦 Complete E-commerce**: Products, categories, cart, orders, payments
- **🎯 Production Ready**: Optimized for Render deployment
- **📊 Admin Dashboard**: Complete admin API endpoints
- **🔍 Advanced Search**: Full-text search with filters and pagination
- **⭐ Reviews & Ratings**: Customer review system
- **💰 Promotions**: Coupon and discount system
- **📱 Mobile Friendly**: RESTful API perfect for web/mobile frontends

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI    │    │   PostgreSQL    │
│   (React/Vue)   │◄──►│   Backend    │◄──►│   Database      │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │
                       ┌──────────────┐
                       │   Redis      │
                       │   (Optional) │
                       └──────────────┘
```

## 📋 Requirements

- Python 3.11+
- PostgreSQL 13+
- Redis (optional, for caching)

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <your-repo>
cd ecommerce_backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Database Setup

```bash
# Run migrations
alembic upgrade head
```

### 4. Development Server

```bash
# Development mode
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000

# Production mode (local testing)
gunicorn app.app:app -c app/gunicorn_config.py
```

### 5. API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## 📚 API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/token` - OAuth2 token endpoint

### Products
- `GET /api/products` - List products (with filters)
- `GET /api/products/{id}` - Get product details
- `GET /api/products/search` - Search products
- `GET /api/products/featured` - Featured products
- `POST /api/products/{id}/reviews` - Add product review

### User Management
- `GET /api/user/profile` - Get user profile
- `PUT /api/user/profile` - Update profile
- `GET /api/user/addresses` - Get user addresses
- `POST /api/user/addresses` - Add new address

### Shopping Cart
- `GET /api/cart` - Get cart items
- `POST /api/cart` - Add to cart
- `PUT /api/cart/{id}` - Update cart item
- `DELETE /api/cart/{id}` - Remove from cart

### Orders
- `GET /api/orders` - Get user orders
- `POST /api/orders` - Create order (checkout)
- `GET /api/orders/{id}` - Get order details

### Admin (Authentication Required)
- `GET /api/admin/products` - Manage products
- `GET /api/admin/orders` - Manage orders
- `GET /api/admin/users` - Manage users
- `GET /api/admin/dashboard` - Dashboard stats

## 🗄️ Database Schema

### Core Entities
- **Users**: Customer accounts and authentication
- **Products**: Product catalog with variants and attributes
- **Categories**: Hierarchical product organization
- **Orders**: Purchase transactions and order management
- **Cart**: Shopping cart functionality
- **Reviews**: Customer feedback and ratings
- **Addresses**: Shipping and billing addresses
- **Payments**: Payment processing and history

### Key Features
- **Async Operations**: All database operations are async
- **Connection Pooling**: Optimized for high concurrency
- **Migrations**: Alembic for schema management
- **Indexing**: Strategic indexes for performance

## ⚡ Performance Optimizations

### Application Level
- **Async/Await**: Non-blocking I/O operations
- **Connection Pooling**: Reuse database connections
- **Pagination**: Efficient data loading
- **Query Optimization**: Eager loading for relationships

### Production Deployment
- **Gunicorn**: Multiple worker processes
- **Uvicorn Workers**: ASGI server for async support
- **Auto-scaling**: Worker count based on CPU cores
- **Health Checks**: Monitoring endpoints

## 🔒 Security Features

- **JWT Authentication**: Secure token-based auth
- **Password Hashing**: Bcrypt for password security
- **CORS Protection**: Configurable origin restrictions
- **Input Validation**: Pydantic schema validation
- **SQL Injection Prevention**: SQLAlchemy ORM protection

## 🌐 Deployment

### Render (Recommended)

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app.main:app -c app/gunicorn_config.py
```

See [Render Deployment Guide](./DEPLOYMENT.md) for detailed instructions.

### Environment Variables

Required environment variables:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=["https://yourdomain.com"]
```

## 📊 Monitoring

### Health Checks
- `GET /health` - Application health status
- Database connectivity check
- Response time monitoring

### Logging
- Structured logging with request tracing
- Error tracking and alerting
- Performance metrics

## 🔧 Development

### Project Structure
```
app/
├── main.py              # FastAPI application
├── config.py           # Configuration settings
├── database.py         # Database connection
├── models/             # SQLAlchemy models
├── schemas/            # Pydantic schemas
├── api/                # API route handlers
├── core/               # Core utilities
└── services/           # Business logic
```

### Code Quality
- **Type Hints**: Full Python type annotations
- **Async Best Practices**: Proper async/await usage
- **Error Handling**: Comprehensive exception handling
- **Documentation**: Inline code documentation

### Testing
```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the [API Documentation](http://localhost:8000/docs)
- Review the [Deployment Guide](./DEPLOYMENT.md)
- Open an issue for bugs or feature requests

---

**Built with ❤️ using FastAPI, SQLAlchemy, and PostgreSQL**