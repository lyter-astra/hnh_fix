from app.models.base import BaseModel
from app.models.user import User, Address, Notification
from app.models.product import (
    Category,
    Subcategory,
    Product,
    ProductImage,
    ProductVariant,
    ProductAttribute,
    ProductReview
)
from app.models.order import (
    CartItem,
    Wishlist,
    Order,
    OrderItem,
    Payment,
    Coupon
)
from app.models.analytics import (
    AnalyticsEvent,
    SearchLog
)

__all__ = [
    "BaseModel",
    "User",
    "Address", 
    "Notification",
    "Category",
    "Subcategory",
    "Product",
    "ProductImage",
    "ProductVariant",
    "ProductAttribute",
    "ProductReview",
    "CartItem",
    "Wishlist",
    "Order",
    "OrderItem",
    "Payment",
    "Coupon",
    "AnalyticsEvent",
    "SearchLog"
]


# from app.models.base import BaseModel
# from app.models.user import User, Address, Notification
# from app.models.product import (
#     Category,
#     Subcategory,
#     Product,
#     ProductImage,
#     ProductVariant,
#     ProductAttribute,
#     ProductReview
# )
# from app.models.order import (
#     CartItem,
#     Wishlist,
#     Order,
#     OrderItem,
#     Payment,
#     Coupon
# )

# __all__ = [
#     "BaseModel",
#     "User",
#     "Address", 
#     "Notification",
#     "Category",
#     "Subcategory",
#     "Product",
#     "ProductImage",
#     "ProductVariant",
#     "ProductAttribute",
#     "ProductReview",
#     "CartItem",
#     "Wishlist",
#     "Order",
#     "OrderItem",
#     "Payment",
#     "Coupon"
# ]