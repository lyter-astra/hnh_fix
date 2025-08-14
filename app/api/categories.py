from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.product import (
    Category, Subcategory
)
from app.api.deps import require_admin

# Import schemas
from app.schemas.xadmin import (
    CategorySchema,
    SubcategorySchema
)

router = APIRouter(prefix="/categories", tags=["Categories"])

# Generic response models
class DeleteResponse(BaseModel):
    message: str
    deleted_count: int = 1

class BulkDeleteResponse(BaseModel):
    message: str
    deleted_count: int

class StatsResponse(BaseModel):
    total_users: int
    total_products: int
    total_orders: int
    total_revenue: float
    active_carts: int
    pending_orders: int

# ==================== CATEGORY MANAGEMENT ====================

@router.get("/categories", response_model=List[CategorySchema])
async def get_all_categories(
    db: AsyncSession = Depends(get_db)
):
    """Get all categories - no authentication required."""
    result = await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )
    return result.scalars().all()


# ==================== SUBCATEGORY MANAGEMENT ====================

@router.get("/subcategories", response_model=List[SubcategorySchema])
async def get_all_subcategories(
    category_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all subcategories, optionally filtered by category - no authentication required."""
    query = select(Subcategory).options(selectinload(Subcategory.category))
    
    if category_id:
        query = query.where(Subcategory.category_id == category_id)
    
    query = query.order_by(Subcategory.sort_order, Subcategory.name)
    result = await db.execute(query)
    return result.scalars().all()

# Export router
__all__ = ["router"]


# from typing import List, Optional
# from fastapi import APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from pydantic import BaseModel

# from app.database import get_db
# from app.models.user import User
# from app.models.product import (
#     Category, Subcategory
# )
# from app.api.deps import require_admin

# # Import schemas
# from app.schemas.admin import (
#     CategorySchema,
#     SubcategorySchema
# )

# router = APIRouter(prefix="/categories", tags=["Categories"])

# # Generic response models
# class DeleteResponse(BaseModel):
#     message: str
#     deleted_count: int = 1

# class BulkDeleteResponse(BaseModel):
#     message: str
#     deleted_count: int

# class StatsResponse(BaseModel):
#     total_users: int
#     total_products: int
#     total_orders: int
#     total_revenue: float
#     active_carts: int
#     pending_orders: int

# # ==================== CATEGORY MANAGEMENT ====================

# @router.get("/categories", response_model=List[CategorySchema])
# async def get_all_categories(
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all categories."""
#     result = await db.execute(
#         select(Category).order_by(Category.sort_order, Category.name)
#     )
#     return result.scalars().all()


# # ==================== SUBCATEGORY MANAGEMENT ====================

# @router.get("/subcategories", response_model=List[SubcategorySchema])
# async def get_all_subcategories(
#     category_id: Optional[int] = None,
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all subcategories, optionally filtered by category."""
#     query = select(Subcategory).options(selectinload(Subcategory.category))
    
#     if category_id:
#         query = query.where(Subcategory.category_id == category_id)
    
#     query = query.order_by(Subcategory.sort_order, Subcategory.name)
#     result = await db.execute(query)
#     return result.scalars().all()

# # Export router
# __all__ = ["router"]