from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, not_
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.product import Product, Category, Subcategory, ProductImage, ProductVariant, ProductAttribute, ProductReview
from app.models.user import User

from app.schemas.product import (
    Product as ProductSchema, 
    ProductDetail, 
    ProductCreate, 
    ProductUpdate,
    ProductFilter,
    ProductList,
    Category as CategorySchema,
    CategoryCreate,
    CategoryUpdate,
    ProductReview as ProductReviewSchema,
    ProductReviewCreate
)

from app.api.deps import get_current_user_optional, get_current_active_user
from app.config import settings

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("", response_model=ProductList)
async def get_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    subcategory_id: Optional[int] = None,
    exclude: Optional[Union[int, str]] = Query(None, description="Product ID(s) to exclude. Can be single ID or comma-separated IDs"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit results (overrides per_page when used)"),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    brand: Optional[str] = None,
    is_featured: Optional[bool] = None,
    in_stock: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|price|rating|name)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated list of products with filters.
    
    Example usage:
    - GET /api/products?subcategory_id=1&exclude=2&limit=4
    - GET /api/products?subcategory_id=1&exclude=2,5,8&limit=10
    """
    
    # Build query with images eagerly loaded
    query = select(Product).options(
        selectinload(Product.images)
    ).where(Product.status == "active")
    
    # Apply filters
    if category_id:
        query = query.where(Product.category_id == category_id)
        
    if subcategory_id:
        query = query.where(Product.subcategory_id == subcategory_id)
        
    if exclude:
        # Handle both single ID and comma-separated IDs
        if isinstance(exclude, str):
            try:
                # Split by comma and convert to integers
                exclude_ids = [int(id_str.strip()) for id_str in exclude.split(",") if id_str.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid exclude parameter. Must be integer or comma-separated integers."
                )
        else:
            exclude_ids = [exclude]
        
        if exclude_ids:
            query = query.where(not_(Product.id.in_(exclude_ids)))
    
    if min_price:
        query = query.where(Product.price >= min_price)
        
    if max_price:
        query = query.where(Product.price <= max_price)
        
    if brand:
        query = query.where(Product.brand.ilike(f"%{brand}%"))
        
    if is_featured is not None:
        query = query.where(Product.is_featured == is_featured)
        
    if in_stock:
        query = query.where(Product.stock_quantity > 0)
        
    if search:
        query = query.where(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%")
            )
        )
    
    # Apply sorting
    if sort_by == "created_at":
        order_by = Product.created_at.desc() if order == "desc" else Product.created_at.asc()
    elif sort_by == "price":
        order_by = Product.price.desc() if order == "desc" else Product.price.asc()
    elif sort_by == "rating":
        order_by = Product.rating.desc() if order == "desc" else Product.rating.asc()
    elif sort_by == "name":
        order_by = Product.name.desc() if order == "desc" else Product.name.asc()
    
    query = query.order_by(order_by)
    
    # Handle limit parameter (overrides pagination when specified)
    if limit:
        # When limit is specified, don't use pagination
        query = query.limit(limit)
        
        # Execute query
        result = await db.execute(query)
        products = result.scalars().all()
        
        return ProductList(
            items=products,
            total=len(products),
            page=1,
            per_page=limit,
            pages=1
        )
    else:
        # Count total results for pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Execute query
        result = await db.execute(query)
        products = result.scalars().all()
        
        return ProductList(
            items=products,
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )


# Keep all your existing endpoints below...
@router.get("/featured", response_model=List[ProductSchema])
async def get_featured_products(
    limit: int = Query(10, ge=1, le=50),
    exclude: Optional[Union[int, str]] = Query(None, description="Product ID(s) to exclude"),
    db: AsyncSession = Depends(get_db)
):
    """Get featured products with optional exclusions."""
    query = select(Product).options(
        selectinload(Product.images)
    ).where(
        and_(Product.is_featured == True, Product.status == "active")
    )
    
    # Handle exclude parameter
    if exclude:
        if isinstance(exclude, str):
            try:
                exclude_ids = [int(id_str.strip()) for id_str in exclude.split(",") if id_str.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid exclude parameter. Must be integer or comma-separated integers."
                )
        else:
            exclude_ids = [exclude]
        
        if exclude_ids:
            query = query.where(not_(Product.id.in_(exclude_ids)))
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    products = result.scalars().all()
    return products


@router.get("/search", response_model=ProductList)
async def search_products(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    exclude: Optional[Union[int, str]] = Query(None, description="Product ID(s) to exclude"),
    db: AsyncSession = Depends(get_db)
):
    """Search products by name, description, or brand with optional exclusions."""
    
    query = select(Product).options(
        selectinload(Product.images)
    ).where(
        and_(
            Product.status == "active",
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%"),
                Product.brand.ilike(f"%{q}%")
            )
        )
    )
    
    # Handle exclude parameter
    if exclude:
        if isinstance(exclude, str):
            try:
                exclude_ids = [int(id_str.strip()) for id_str in exclude.split(",") if id_str.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid exclude parameter. Must be integer or comma-separated integers."
                )
        else:
            exclude_ids = [exclude]
        
        if exclude_ids:
            query = query.where(not_(Product.id.in_(exclude_ids)))
    
    query = query.order_by(Product.created_at.desc())
    
    # Count total results
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    products = result.scalars().all()
    
    return ProductList(
        items=products,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """Get product by ID with all related data."""
    query = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.subcategory),
        selectinload(Product.images),
        selectinload(Product.variants),
        selectinload(Product.attributes)
    ).where(Product.id == product_id)
    
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return product


@router.get("/slug/{product_slug}", response_model=ProductDetail)
async def get_product_by_slug(
    product_slug: str, 
    db: AsyncSession = Depends(get_db)
):
    """Get product by slug with all related data."""
    query = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.subcategory),
        selectinload(Product.images),
        selectinload(Product.variants),
        selectinload(Product.attributes)
    ).where(Product.slug == product_slug)
    
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return product


@router.get("/slug_any_word/{product_slug}", response_model=List[ProductDetail])
async def get_products_by_partial_slug(
    product_slug: str, 
    db: AsyncSession = Depends(get_db)
):
    """Search products by partial slug match."""
    query = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.subcategory),
        selectinload(Product.images),
        selectinload(Product.variants),
        selectinload(Product.attributes)
    ).where(Product.slug.ilike(f"%{product_slug}%"))

    result = await db.execute(query)
    products = result.scalars().all()

    if not products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No products found for this keyword"
        )
    
    return products


@router.get("/{product_id}/reviews", response_model=List[ProductReviewSchema])
async def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get product reviews."""
    offset = (page - 1) * per_page
    
    query = select(ProductReview).options(
        selectinload(ProductReview.user)
    ).where(
        and_(
            ProductReview.product_id == product_id,
            ProductReview.is_approved == True
        )
    ).order_by(ProductReview.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    reviews = result.scalars().all()
    return reviews


@router.post("/{product_id}/reviews", response_model=ProductReviewSchema)
async def create_product_review(
    product_id: int,
    review_data: ProductReviewCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a product review."""
    # Check if product exists
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    if not product_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if user already reviewed this product
    existing_review = await db.execute(
        select(ProductReview).where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.user_id == current_user.id
            )
        )
    )
    if existing_review.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this product"
        )
    
    # Create review
    review = ProductReview(
        product_id=product_id,
        user_id=current_user.id,
        rating=review_data.rating,
        title=review_data.title,
        comment=review_data.comment
    )
    
    db.add(review)
    await db.commit()
    await db.refresh(review)
    
    return review


@router.get("/{product_id}/images", response_model=List[dict])
async def get_product_images(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all images for a specific product."""
    query = select(ProductImage).where(
        ProductImage.product_id == product_id
    ).order_by(ProductImage.sort_order, ProductImage.id)
    
    result = await db.execute(query)
    images = result.scalars().all()
    
    if not images:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No images found for this product"
        )
    
    return [
        {
            "id": img.id,
            "image_url": img.image_url,
            "alt_text": img.alt_text,
            "is_primary": img.is_primary,
            "sort_order": img.sort_order
        }
        for img in images
    ]

