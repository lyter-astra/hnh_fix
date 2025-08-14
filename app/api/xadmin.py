from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, text, and_, or_, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
import json

from app.database import get_db
from app.models.user import User, Address, Notification
from app.models.order import CartItem, Wishlist, Order, OrderItem, Payment, Coupon
from app.models.product import (
    Product, Category, Subcategory, ProductImage, 
    ProductVariant, ProductAttribute, ProductReview
)
from app.models.analytics import AnalyticsEvent, SearchLog
from app.api.deps import get_current_active_user, require_admin

# Import schemas
from app.schemas.xadmin import (
    CategoryCreate, CategoryUpdate, CategorySchema,
    SubcategoryCreate, SubcategoryUpdate, SubcategorySchema,
    ProductCreate, ProductUpdate, ProductSchema,
    ProductImageCreate, ProductImageUpdate, ProductImageSchema,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantSchema,
    ProductAttributeCreate, ProductAttributeUpdate, ProductAttributeSchema,
    CouponCreate, CouponUpdate, CouponSchema,
    OrderUpdate, OrderSchema,
    PaymentUpdate,
    UserCreate, UserUpdate, UserSchema,
    NotificationCreate,
    ProductReviewSchema
)

# If schemas are not available, use inline models
from typing import Optional as Opt

from app.utils.fix_sequence import fix_all_sequences

router = APIRouter(prefix="/admin", tags=["Admin"])

# Generic response models
class DeleteResponse(BaseModel):
    message: str
    deleted_count: int = 1

class BulkDeleteResponse(BaseModel):
    message: str
    deleted_count: int

# Updated response models for stats
class RecentOrder(BaseModel):
    id: int
    order_number: str
    user_email: str
    total_amount: float
    status: str
    created_at: datetime

class LowStockProduct(BaseModel):
    id: int
    name: str
    sku: str
    stock_quantity: int
    price: float

class StatsResponse(BaseModel):
    total_users: int
    total_products: int
    total_orders: int
    total_revenue: float
    active_carts: int
    pending_orders: int
    recent_orders: List[RecentOrder]
    low_stock_alert: List[LowStockProduct]

# ==================== Automated Sequence Fix Function ====================

# Add this endpoint to your admin router
@router.post("/maintenance/fix-sequences")
async def fix_database_sequences(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Fix all PostgreSQL sequences."""
    try:
        results = await fix_all_sequences(db)
        
        fixed_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        return {
            "message": f"Fixed {fixed_count}/{total_count} sequences",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fixing sequences: {str(e)}")
    


# ==================== DASHBOARD & STATS ====================

@router.get("/stats", response_model=StatsResponse)
async def get_admin_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    low_stock_threshold: int = 10  # Products with stock below this are considered low
):
    """Get dashboard statistics with recent orders and low stock alerts."""
    # Total users
    users_count = await db.execute(select(func.count(User.id)))
    total_users = users_count.scalar()
    
    # Total products
    products_count = await db.execute(select(func.count(Product.id)))
    total_products = products_count.scalar()
    
    # Total orders
    orders_count = await db.execute(select(func.count(Order.id)))
    total_orders = orders_count.scalar()
    
    # Total revenue
    revenue_result = await db.execute(
        select(func.sum(Order.total_amount))
        .where(Order.payment_status == 'paid')
    )
    total_revenue = revenue_result.scalar() or 0
    
    # Active carts
    active_carts = await db.execute(
        select(func.count(func.distinct(CartItem.user_id)))
    )
    active_carts_count = active_carts.scalar()
    
    # Pending orders
    pending_orders = await db.execute(
        select(func.count(Order.id))
        .where(Order.status == 'pending')
    )
    pending_count = pending_orders.scalar()
    
    # Recent orders (last 5 orders)
    recent_orders_query = await db.execute(
        select(Order)
        .options(selectinload(Order.user))
        .order_by(desc(Order.created_at))
        .limit(5)
    )
    recent_orders_data = recent_orders_query.scalars().all()
    
    recent_orders = []
    for order in recent_orders_data:
        recent_orders.append(RecentOrder(
            id=order.id,
            order_number=order.order_number,
            user_email=order.user.email if order.user else "Guest",
            total_amount=float(order.total_amount),
            status=order.status,
            created_at=order.created_at
        ))
    
    # Low stock products
    low_stock_query = await db.execute(
        select(Product)
        .where(
            and_(
                Product.stock_quantity < low_stock_threshold,
                Product.status == 'active'
            )
        )
        .order_by(Product.stock_quantity.asc())
        .limit(10)  # Show top 10 low stock items
    )
    low_stock_products = low_stock_query.scalars().all()
    
    low_stock_alert = []
    for product in low_stock_products:
        low_stock_alert.append(LowStockProduct(
            id=product.id,
            name=product.name,
            sku=product.sku,
            stock_quantity=product.stock_quantity,
            price=float(product.price)
        ))
    
    return StatsResponse(
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=float(total_revenue),
        active_carts=active_carts_count,
        pending_orders=pending_count,
        recent_orders=recent_orders if recent_orders else [],
        low_stock_alert=low_stock_alert if low_stock_alert else []
    )

# ==================== CATEGORY MANAGEMENT ====================

@router.get("/categories", response_model=List[CategorySchema])
async def get_all_categories(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all categories."""
    result = await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )
    return result.scalars().all()


@router.post("/categories", response_model=CategorySchema)
async def create_category(
    category_data: CategoryCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new category."""
    try:
        # Check if slug already exists
        existing_category = await db.execute(
            select(Category).where(Category.slug == category_data.slug)
        )
        if existing_category.scalar_one_or_none():
            raise HTTPException(
                status_code=400, 
                detail=f"Category with slug '{category_data.slug}' already exists"
            )
        
        # Generate slug if not provided
        if not hasattr(category_data, 'slug') or not category_data.slug:
            slug = category_data.name.lower().replace(' ', '-').replace('/', '-')
            category_data.slug = slug
        
        category = Category(**category_data.model_dump())
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        # Check if it's a primary key constraint violation
        if "duplicate key value violates unique constraint" in str(e) and "categories_pkey" in str(e):
            try:
                # Reset the sequence and retry once
                await db.execute(text("""
                    SELECT setval('categories_id_seq', 
                                  COALESCE((SELECT MAX(id) FROM categories), 0) + 1, 
                                  false)
                """))
                await db.commit()
                
                # Retry the insert
                category = Category(**category_data.model_dump())
                db.add(category)
                await db.commit()
                await db.refresh(category)
                return category
                
            except Exception as retry_error:
                await db.rollback()
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to create category after sequence reset: {str(retry_error)}"
                )
        else:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/categories/{category_id}", response_model=CategorySchema)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update category."""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    await db.commit()
    await db.refresh(category)
    return category

@router.delete("/categories/{category_id}", response_model=DeleteResponse)
async def delete_category(
    category_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete category and all related data."""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    await db.delete(category)
    await db.commit()
    return DeleteResponse(message="Category deleted successfully")

# ==================== SUBCATEGORY MANAGEMENT ====================

@router.get("/subcategories", response_model=List[SubcategorySchema])
async def get_all_subcategories(
    category_id: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all subcategories, optionally filtered by category."""
    query = select(Subcategory).options(selectinload(Subcategory.category))
    
    if category_id:
        query = query.where(Subcategory.category_id == category_id)
    
    query = query.order_by(Subcategory.sort_order, Subcategory.name)
    result = await db.execute(query)
    subcategories = result.scalars().all()
    # Return as list with category relationship loaded
    return [
        {
            "id": sub.id,
            "category_id": sub.category_id,
            "category": {
                "id": sub.category.id,
                "name": sub.category.name,
                "slug": sub.category.slug,
                "created_at": sub.category.created_at.isoformat() if sub.category.created_at else None,
                "updated_at": sub.category.updated_at.isoformat() if sub.category.updated_at else None
            } if sub.category else None,
            "name": sub.name,
            "slug": sub.slug,
            "description": sub.description,
            "image_url": sub.image_url,
            "is_active": sub.is_active,
            "sort_order": sub.sort_order,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None
        }
        for sub in subcategories
    ]
    
    # Return as list with category relationship loaded
    # return [
    #     {
    #         "id": sub.id,
    #         "category_id": sub.category_id,
    #         "category": {
    #             "id": sub.category.id,
    #             "name": sub.category.name,
    #             "slug": sub.category.slug
    #         } if sub.category else None,
    #         "name": sub.name,
    #         "slug": sub.slug,
    #         "description": sub.description,
    #         "image_url": sub.image_url,
    #         "is_active": sub.is_active,
    #         "sort_order": sub.sort_order,
    #         "created_at": sub.created_at.isoformat() if sub.created_at else None,
    #         "updated_at": sub.updated_at.isoformat() if sub.updated_at else None
    #     }
    #     for sub in subcategories
    # ]

@router.post("/subcategories", response_model=SubcategorySchema)
async def create_subcategory(
    subcategory_data: SubcategoryCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new subcategory."""
    subcategory = Subcategory(**subcategory_data.model_dump())
    db.add(subcategory)
    await db.commit()
    await db.refresh(subcategory)
    
    # Load the relationship explicitly to avoid lazy loading issues
    result = await db.execute(
        select(Subcategory)
        .options(selectinload(Subcategory.category))
        .where(Subcategory.id == subcategory.id)
    )
    subcategory_with_category = result.scalar_one()
    
    return subcategory_with_category


@router.put("/subcategories/{subcategory_id}", response_model=SubcategorySchema)
async def update_subcategory(
    subcategory_id: int,
    subcategory_update: SubcategoryUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update subcategory."""
    try:
        # First, get the subcategory
        result = await db.execute(select(Subcategory).where(Subcategory.id == subcategory_id))
        subcategory = result.scalar_one_or_none()
        
        if not subcategory:
            raise HTTPException(status_code=404, detail="Subcategory not found")
        
        # If category_id is being updated, verify the new category exists
        update_data = subcategory_update.model_dump(exclude_unset=True)
        if 'category_id' in update_data:
            category_check = await db.execute(
                select(Category).where(Category.id == update_data['category_id'])
            )
            if not category_check.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Category not found")
        
        # Check if slug already exists (if being updated)
        if 'slug' in update_data and update_data['slug'] != subcategory.slug:
            existing_subcategory = await db.execute(
                select(Subcategory).where(
                    and_(
                        Subcategory.slug == update_data['slug'],
                        Subcategory.id != subcategory_id
                    )
                )
            )
            if existing_subcategory.scalar_one_or_none():
                raise HTTPException(
                    status_code=400, 
                    detail=f"Subcategory with slug '{update_data['slug']}' already exists"
                )
        
        # Update the subcategory
        for field, value in update_data.items():
            setattr(subcategory, field, value)
        
        subcategory.updated_at = datetime.utcnow()
        await db.commit()
        
        # Load the updated subcategory with its category relationship
        result = await db.execute(
            select(Subcategory)
            .options(selectinload(Subcategory.category))
            .where(Subcategory.id == subcategory_id)
        )
        updated_subcategory = result.scalar_one()
        
        return updated_subcategory
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    
@router.delete("/subcategories/{subcategory_id}", response_model=DeleteResponse)
async def delete_subcategory(
    subcategory_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete subcategory."""
    result = await db.execute(select(Subcategory).where(Subcategory.id == subcategory_id))
    subcategory = result.scalar_one_or_none()
    
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    
    await db.delete(subcategory)
    await db.commit()
    return DeleteResponse(message="Subcategory deleted successfully")

# ==================== PRODUCT MANAGEMENT ====================

@router.get("/products", response_model=Dict[str, Any])
async def get_all_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all products with filters."""
    query = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.subcategory),
        selectinload(Product.images),
        selectinload(Product.variants),
        selectinload(Product.attributes)
    )
    
    # Apply filters
    if search:
        query = query.where(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%")
            )
        )
    
    if category_id:
        query = query.where(Product.category_id == category_id)
    
    if status:
        query = query.where(Product.status == status)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(Product.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    products = result.scalars().all()
    
    # Convert products to serializable format
    serialized_products = []
    for product in products:
        product_dict = {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "short_description": product.short_description,
            "price": float(product.price) if product.price else 0,
            "original_price": float(product.original_price) if product.original_price else None,
            "cost_price": float(product.cost_price) if product.cost_price else None,
            "rating": float(product.rating) if product.rating else 0,
            "review_count": product.review_count,
            "stock_quantity": product.stock_quantity,
            "low_stock_threshold": product.low_stock_threshold,
            "sku": product.sku,
            "barcode": product.barcode,
            "weight": float(product.weight) if product.weight else None,
            "dimensions": product.dimensions,
            "category_id": product.category_id,
            "subcategory_id": product.subcategory_id,
            "brand": product.brand,
            "status": product.status,
            "is_featured": product.is_featured,
            "meta_title": product.meta_title,
            "meta_description": product.meta_description,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            
            # Related data
            "category": {
                "id": product.category.id,
                "name": product.category.name,
                "slug": product.category.slug
            } if product.category else None,
            
            "subcategory": {
                "id": product.subcategory.id,
                "name": product.subcategory.name,
                "slug": product.subcategory.slug
            } if product.subcategory else None,
            
            "images": [
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "alt_text": img.alt_text,
                    "sort_order": img.sort_order,
                    "is_primary": img.is_primary
                } for img in product.images
            ],
            
            "variants": [
                {
                    "id": var.id,
                    "name": var.name,
                    "sku": var.sku,
                    "price": float(var.price) if var.price else None,
                    "stock_quantity": var.stock_quantity,
                    "color_name": var.color_name,
                    "color_hex": var.color_hex,
                    "size_name": var.size_name,
                    "weight": float(var.weight) if var.weight else None,
                    "is_active": var.is_active
                } for var in product.variants
            ],
            
            "attributes": [
                {
                    "id": attr.id,
                    "name": attr.name,
                    "value": attr.value,
                    "type": attr.type,
                    "is_filterable": attr.is_filterable,
                    "sort_order": attr.sort_order
                } for attr in product.attributes
            ]
        }
        serialized_products.append(product_dict)
    
    return {
        "items": serialized_products,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

@router.post("/products", response_model=ProductSchema)
async def create_product(
    product_data: ProductCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new product."""
    # Generate slug if not provided
    if not hasattr(product_data, 'slug') or not product_data.slug:
        slug = product_data.name.lower().replace(' ', '-').replace('/', '-')
        product_data.slug = slug
    
    product = Product(**product_data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Load relationships
    result = await db.execute(
        select(Product).options(
            selectinload(Product.category),
            selectinload(Product.subcategory),
            selectinload(Product.images),
            selectinload(Product.variants),
            selectinload(Product.attributes)
        ).where(Product.id == product.id)
    )
    product = result.scalar_one()
    
    return product

@router.put("/products/{product_id}", response_model=ProductSchema)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow()
    await db.commit()
    
    # Load relationships with nested loading for subcategory.category
    result = await db.execute(
        select(Product).options(
            selectinload(Product.category),
            selectinload(Product.subcategory).selectinload(Subcategory.category),
            selectinload(Product.images),
            selectinload(Product.variants),
            selectinload(Product.attributes)
        ).where(Product.id == product.id)
    )
    product = result.scalar_one()
    
    return product

@router.delete("/products/{product_id}", response_model=DeleteResponse)
async def delete_product(
    product_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete product and all related data."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(product)
    await db.commit()
    return DeleteResponse(message="Product deleted successfully")

@router.post("/products/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_products(
    product_ids: List[int],
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk delete products."""
    result = await db.execute(
        delete(Product).where(Product.id.in_(product_ids))
    )
    await db.commit()
    return BulkDeleteResponse(
        message=f"Deleted {result.rowcount} products",
        deleted_count=result.rowcount
    )

# ==================== PRODUCT IMAGES MANAGEMENT ====================

@router.post("/products/{product_id}/images", response_model=ProductImageSchema)
async def add_product_image(
    product_id: int,
    image_data: ProductImageCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add image to product."""
    # Verify product exists
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    try:
        # If setting as primary, unset other primary images
        if image_data.is_primary:
            await db.execute(
                update(ProductImage)
                .where(ProductImage.product_id == product_id)
                .values(is_primary=False)
            )
        
        # Create the image record - let PostgreSQL auto-generate the ID
        image_dict = image_data.model_dump()
        image_dict['product_id'] = product_id
        
        image = ProductImage(**image_dict)
        db.add(image)
        await db.commit()
        await db.refresh(image)
        return image
        
    except Exception as e:
        await db.rollback()
        # Check if it's a primary key constraint violation
        if "duplicate key value violates unique constraint" in str(e):
            # Try to fix the sequence and retry once
            try:
                # Reset the sequence
                await db.execute(text("""
                    SELECT setval('product_images_id_seq', 
                                  COALESCE((SELECT MAX(id) FROM product_images), 0) + 1, 
                                  false)
                """))
                await db.commit()
                
                # Retry the insert
                image = ProductImage(**image_dict)
                db.add(image)
                await db.commit()
                await db.refresh(image)
                return image
                
            except Exception as retry_error:
                await db.rollback()
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to create image after sequence reset: {str(retry_error)}"
                )
        else:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/images/{image_id}", response_model=ProductImageSchema)
async def update_product_image(
    image_id: int,
    image_update: ProductImageUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update product image."""
    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # If setting as primary, unset other primary images
    if image_update.is_primary:
        await db.execute(
            update(ProductImage)
            .where(
                and_(
                    ProductImage.product_id == image.product_id,
                    ProductImage.id != image_id
                )
            )
            .values(is_primary=False)
        )
    
    update_data = image_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(image, field, value)
    
    await db.commit()
    await db.refresh(image)
    return image

@router.delete("/images/{image_id}", response_model=DeleteResponse)
async def delete_product_image(
    image_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete product image."""
    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    await db.delete(image)
    await db.commit()
    return DeleteResponse(message="Image deleted successfully")

# ==================== PRODUCT VARIANTS MANAGEMENT ====================

@router.post("/products/{product_id}/variants", response_model=ProductVariantSchema)
async def add_product_variant(
    product_id: int,
    variant_data: ProductVariantCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add variant to product."""
    # Verify product exists
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    variant = ProductVariant(product_id=product_id, **variant_data.model_dump())
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant

@router.put("/variants/{variant_id}", response_model=ProductVariantSchema)
async def update_product_variant(
    variant_id: int,
    variant_update: ProductVariantUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update product variant."""
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    update_data = variant_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(variant, field, value)
    
    variant.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(variant)
    return variant

@router.delete("/variants/{variant_id}", response_model=DeleteResponse)
async def delete_product_variant(
    variant_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete product variant."""
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    await db.delete(variant)
    await db.commit()
    return DeleteResponse(message="Variant deleted successfully")

# ==================== PRODUCT ATTRIBUTES MANAGEMENT ====================

@router.post("/products/{product_id}/attributes", response_model=ProductAttributeSchema)
async def add_product_attribute(
    product_id: int,
    attribute_data: ProductAttributeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add attribute to product."""
    # Verify product exists
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    attribute = ProductAttribute(product_id=product_id, **attribute_data.model_dump())
    db.add(attribute)
    await db.commit()
    await db.refresh(attribute)
    return attribute

@router.put("/attributes/{attribute_id}", response_model=ProductAttributeSchema)
async def update_product_attribute(
    attribute_id: int,
    attribute_update: ProductAttributeUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update product attribute."""
    result = await db.execute(select(ProductAttribute).where(ProductAttribute.id == attribute_id))
    attribute = result.scalar_one_or_none()
    
    if not attribute:
        raise HTTPException(status_code=404, detail="Attribute not found")
    
    update_data = attribute_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(attribute, field, value)
    
    await db.commit()
    await db.refresh(attribute)
    return attribute

@router.delete("/attributes/{attribute_id}", response_model=DeleteResponse)
async def delete_product_attribute(
    attribute_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete product attribute."""
    result = await db.execute(select(ProductAttribute).where(ProductAttribute.id == attribute_id))
    attribute = result.scalar_one_or_none()
    
    if not attribute:
        raise HTTPException(status_code=404, detail="Attribute not found")
    
    await db.delete(attribute)
    await db.commit()
    return DeleteResponse(message="Attribute deleted successfully")

# ==================== USER MANAGEMENT ====================

@router.get("/users", response_model=Dict[str, Any])
async def get_all_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all users with filters."""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.phone_number.ilike(f"%{search}%")
            )
        )
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Serialize users
    serialized_users = []
    for user in users:
        serialized_users.append({
            "id": user.id,
            "email": user.email,
            "phone_number": user.phone_number,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
            "gender": user.gender,
            "profile_picture": user.profile_picture,
            "email_verified": user.email_verified,
            "phone_verified": user.phone_verified,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        })
    
    return {
        "items": serialized_users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

@router.post("/users", response_model=UserSchema)
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new user."""
    # Check if email exists
    existing_user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(**user_data.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.put("/users/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{user_id}", response_model=DeleteResponse)
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete user and all related data."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    return DeleteResponse(message="User deleted successfully")

@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle user active status."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    await db.commit()
    
    return {"message": f"User {'activated' if user.is_active else 'deactivated'} successfully"}

# ==================== ORDER MANAGEMENT ====================

@router.get("/orders", response_model=Dict[str, Any])
async def get_all_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    user_id: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all orders with filters."""
    query = select(Order).options(
        selectinload(Order.user),
        selectinload(Order.order_items).selectinload(OrderItem.product)
    )
    
    # Apply filters
    if status:
        query = query.where(Order.status == status)
    
    if payment_status:
        query = query.where(Order.payment_status == payment_status)
    
    if user_id:
        query = query.where(Order.user_id == user_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(Order.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    orders = result.scalars().all()
    
    # Manually serialize orders to avoid Pydantic issues
    serialized_orders = []
    for order in orders:
        order_dict = {
            "id": order.id,
            "user_id": order.user_id,
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "currency": order.currency,
            "subtotal": float(order.subtotal) if order.subtotal else 0,
            "tax_amount": float(order.tax_amount) if order.tax_amount else 0,
            "shipping_cost": float(order.shipping_cost) if order.shipping_cost else 0,
            "discount_amount": float(order.discount_amount) if order.discount_amount else 0,
            "total_amount": float(order.total_amount) if order.total_amount else 0,
            "notes": order.notes,
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            
            # User info
            "user": {
                "id": order.user.id,
                "email": order.user.email,
                "first_name": order.user.first_name,
                "last_name": order.user.last_name
            } if order.user else None,
            
            # Order items
            "order_items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price) if item.unit_price else 0,
                    "total_price": float(item.total_price) if item.total_price else 0,
                    "product": {
                        "id": item.product.id,
                        "name": item.product.name,
                        "slug": item.product.slug
                    } if item.product else None
                } for item in order.order_items
            ],
            
            # Shipping address
            "shipping_address": {
                "first_name": order.shipping_first_name,
                "last_name": order.shipping_last_name,
                "company": order.shipping_company,
                "address_line1": order.shipping_address_line1,
                "address_line2": order.shipping_address_line2,
                "city": order.shipping_city,
                "province": order.shipping_province,
                "postal_code": order.shipping_postal_code,
                "country": order.shipping_country,
                "phone": order.shipping_phone
            },
            
            # Billing address
            "billing_address": {
                "first_name": order.billing_first_name,
                "last_name": order.billing_last_name,
                "company": order.billing_company,
                "address_line1": order.billing_address_line1,
                "address_line2": order.billing_address_line2,
                "city": order.billing_city,
                "province": order.billing_province,
                "postal_code": order.billing_postal_code,
                "country": order.billing_country,
                "phone": order.billing_phone
            }
        }
        serialized_orders.append(order_dict)
    
    return {
        "items": serialized_orders,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

@router.get("/orders/{order_id}", response_model=Dict[str, Any])
async def get_order(
    order_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a single order by ID."""
    try:
        # Load order with all relationships
        result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.order_items).selectinload(OrderItem.product),
                selectinload(Order.payments)
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Manually serialize the order
        order_dict = {
            "id": order.id,
            "user_id": order.user_id,
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "currency": order.currency,
            "subtotal": float(order.subtotal) if order.subtotal else 0,
            "tax_amount": float(order.tax_amount) if order.tax_amount else 0,
            "shipping_cost": float(order.shipping_cost) if order.shipping_cost else 0,
            "discount_amount": float(order.discount_amount) if order.discount_amount else 0,
            "total_amount": float(order.total_amount) if order.total_amount else 0,
            "notes": order.notes,
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            
            # User info
            "user": {
                "id": order.user.id,
                "email": order.user.email,
                "first_name": order.user.first_name,
                "last_name": order.user.last_name
            } if order.user else None,
            
            # Order items
            "order_items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price) if item.unit_price else 0,
                    "total_price": float(item.total_price) if item.total_price else 0,
                    "product": {
                        "id": item.product.id,
                        "name": item.product.name,
                        "slug": item.product.slug
                    } if item.product else None
                } for item in order.order_items
            ],
            
            # Payments
            "payments": [
                {
                    "id": payment.id,
                    "payment_method": payment.payment_method,
                    "payment_provider": payment.payment_provider,
                    "transaction_id": payment.transaction_id,
                    "amount": float(payment.amount) if payment.amount else 0,
                    "currency": payment.currency,
                    "status": payment.status,
                    "processed_at": payment.processed_at.isoformat() if payment.processed_at else None
                } for payment in order.payments
            ],
            
            # Shipping address
            "shipping_address": {
                "first_name": order.shipping_first_name,
                "last_name": order.shipping_last_name,
                "company": order.shipping_company,
                "address_line1": order.shipping_address_line1,
                "address_line2": order.shipping_address_line2,
                "city": order.shipping_city,
                "province": order.shipping_province,
                "postal_code": order.shipping_postal_code,
                "country": order.shipping_country,
                "phone": order.shipping_phone
            },
            
            # Billing address
            "billing_address": {
                "first_name": order.billing_first_name,
                "last_name": order.billing_last_name,
                "company": order.billing_company,
                "address_line1": order.billing_address_line1,
                "address_line2": order.billing_address_line2,
                "city": order.billing_city,
                "province": order.billing_province,
                "postal_code": order.billing_postal_code,
                "country": order.billing_country,
                "phone": order.billing_phone
            }
        }
        
        return order_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@router.put("/orders/{order_id}", response_model=OrderSchema)
async def update_order(
    order_id: int,
    order_update: OrderUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update order status and details."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    update_data = order_update.model_dump(exclude_unset=True)
    
    # Track status changes for timestamps
    if "status" in update_data:
        if update_data["status"] == "shipped" and not order.shipped_at:
            order.shipped_at = datetime.utcnow()
        elif update_data["status"] == "delivered" and not order.delivered_at:
            order.delivered_at = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(order, field, value)
    
    order.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(order)
    return order

@router.delete("/orders/{order_id}", response_model=DeleteResponse)
async def delete_order(
    order_id: int,
    force: bool = Query(False, description="Force delete regardless of status"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete order (use with caution)."""
    try:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Check order status unless force delete is requested
        if not force and order.status not in ['cancelled', 'refunded']:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete order with status '{order.status}'. Only cancelled or refunded orders can be deleted. Use force=true to override."
            )
        
        await db.delete(order)
        await db.commit()
        return DeleteResponse(message="Order deleted successfully")
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== REVIEW MANAGEMENT ====================

@router.get("/reviews", response_model=Dict[str, Any])
async def get_all_reviews(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    is_approved: Optional[bool] = None,
    product_id: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all product reviews."""
    query = select(ProductReview).options(
        selectinload(ProductReview.user),
        selectinload(ProductReview.product)
    )
    
    # Apply filters
    if is_approved is not None:
        query = query.where(ProductReview.is_approved == is_approved)
    
    if product_id:
        query = query.where(ProductReview.product_id == product_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(ProductReview.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    reviews = result.scalars().all()
    
    # Manually serialize reviews to avoid Pydantic serialization issues
    serialized_reviews = []
    for review in reviews:
        review_dict = {
            "id": review.id,
            "user_id": review.user_id,
            "product_id": review.product_id,
            "rating": review.rating,
            "title": getattr(review, 'title', None),
            "comment": getattr(review, 'comment', None),
            "is_approved": getattr(review, 'is_approved', False),
            "is_verified_purchase": getattr(review, 'is_verified_purchase', False),
            "helpful_count": getattr(review, 'helpful_count', 0),
            "created_at": review.created_at.isoformat() if hasattr(review, 'created_at') and review.created_at else None,
            "updated_at": review.updated_at.isoformat() if hasattr(review, 'updated_at') and review.updated_at else None,
            
            # User info
            "user": {
                "id": review.user.id,
                "email": review.user.email,
                "first_name": review.user.first_name,
                "last_name": review.user.last_name
            } if review.user else None,
            
            # Product info
            "product": {
                "id": review.product.id,
                "name": review.product.name,
                "slug": review.product.slug,
                "sku": getattr(review.product, 'sku', None)
            } if review.product else None
        }
        serialized_reviews.append(review_dict)
    
    return {
        "items": serialized_reviews,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

@router.patch("/reviews/{review_id}/approve")
async def approve_review(
    review_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a review."""
    result = await db.execute(select(ProductReview).where(ProductReview.id == review_id))
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review.is_approved = not review.is_approved
    await db.commit()
    
    # Update product rating
    if review.is_approved:
        await _update_product_rating(db, review.product_id)
    
    return {"message": f"Review {'approved' if review.is_approved else 'rejected'}"}

@router.delete("/reviews/{review_id}", response_model=DeleteResponse)
async def delete_review(
    review_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete review."""
    result = await db.execute(select(ProductReview).where(ProductReview.id == review_id))
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    product_id = review.product_id
    await db.delete(review)
    await db.commit()
    
    # Update product rating
    await _update_product_rating(db, product_id)
    
    return DeleteResponse(message="Review deleted successfully")

# ==================== COUPON MANAGEMENT ====================

@router.get("/coupons", response_model=List[CouponSchema])
async def get_all_coupons(
    is_active: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all coupons."""
    query = select(Coupon).order_by(Coupon.created_at.desc())
    
    if is_active is not None:
        query = query.where(Coupon.is_active == is_active)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/coupons", response_model=CouponSchema)
async def create_coupon(
    coupon_data: CouponCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new coupon."""
    # Check if code exists
    existing = await db.execute(
        select(Coupon).where(Coupon.code == coupon_data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    
    coupon = Coupon(**coupon_data.model_dump())
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon

@router.put("/coupons/{coupon_id}", response_model=CouponSchema)
async def update_coupon(
    coupon_id: int,
    coupon_update: CouponUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update coupon."""
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    
    update_data = coupon_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(coupon, field, value)
    
    await db.commit()
    await db.refresh(coupon)
    return coupon

@router.delete("/coupons/{coupon_id}", response_model=DeleteResponse)
async def delete_coupon(
    coupon_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete coupon."""
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    
    await db.delete(coupon)
    await db.commit()
    return DeleteResponse(message="Coupon deleted successfully")


# ==================== ANALYTICS & LOGS ====================

@router.get("/analytics/events")
async def get_analytics_events(
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get analytics events."""
    query = select(AnalyticsEvent).options(selectinload(AnalyticsEvent.user))
    
    if event_type:
        query = query.where(AnalyticsEvent.event_type == event_type)
    
    if user_id:
        query = query.where(AnalyticsEvent.user_id == user_id)
    
    if start_date:
        query = query.where(AnalyticsEvent.created_at >= start_date)
    
    if end_date:
        query = query.where(AnalyticsEvent.created_at <= end_date)
    
    query = query.order_by(AnalyticsEvent.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/analytics/search-logs")
async def get_search_logs(
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get search logs."""
    query = select(SearchLog).options(selectinload(SearchLog.user))
    
    if user_id:
        query = query.where(SearchLog.user_id == user_id)
    
    if start_date:
        query = query.where(SearchLog.created_at >= start_date)
    
    if end_date:
        query = query.where(SearchLog.created_at <= end_date)
    
    query = query.order_by(SearchLog.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

# ==================== NOTIFICATION MANAGEMENT ====================

@router.post("/notifications/broadcast")
async def broadcast_notification(
    notification_data: NotificationCreate,
    user_ids: Optional[List[int]] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Send notification to all users or specific users."""
    if user_ids:
        # Send to specific users
        users = await db.execute(select(User).where(User.id.in_(user_ids)))
        target_users = users.scalars().all()
    else:
        # Send to all active users
        users = await db.execute(select(User).where(User.is_active == True))
        target_users = users.scalars().all()
    
    notifications = []
    for user in target_users:
        notification = Notification(
            user_id=user.id,
            **notification_data.model_dump()
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    await db.commit()
    
    return {
        "message": f"Notification sent to {len(notifications)} users",
        "user_count": len(notifications)
    }

# ==================== DATABASE MAINTENANCE ====================

@router.post("/maintenance/clear-old-carts")
async def clear_old_carts(
    days_old: int = 30,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Clear cart items older than specified days."""
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    result = await db.execute(
        delete(CartItem).where(CartItem.updated_at < cutoff_date)
    )
    await db.commit()
    
    return {
        "message": f"Cleared {result.rowcount} old cart items",
        "deleted_count": result.rowcount
    }

@router.post("/maintenance/clear-old-analytics")
async def clear_old_analytics(
    days_old: int = 90,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Clear analytics data older than specified days."""
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    # Clear analytics events
    events_result = await db.execute(
        delete(AnalyticsEvent).where(AnalyticsEvent.created_at < cutoff_date)
    )
    
    # Clear search logs
    search_result = await db.execute(
        delete(SearchLog).where(SearchLog.created_at < cutoff_date)
    )
    
    await db.commit()
    
    return {
        "message": "Old analytics data cleared",
        "deleted_events": events_result.rowcount,
        "deleted_searches": search_result.rowcount
    }

# ==================== HELPER FUNCTIONS ====================

async def _update_product_rating(db: AsyncSession, product_id: int):
    """Update product rating based on approved reviews."""
    result = await db.execute(
        select(
            func.avg(ProductReview.rating).label('avg_rating'),
            func.count(ProductReview.id).label('count')
        )
        .where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.is_approved == True
            )
        )
    )
    data = result.first()
    
    if data and data.avg_rating:
        await db.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(
                rating=round(float(data.avg_rating), 2),
                review_count=data.count
            )
        )
        await db.commit()

# Export router
__all__ = ["router"]
