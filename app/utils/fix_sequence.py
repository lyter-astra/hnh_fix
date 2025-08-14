from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def fix_sequence(db: AsyncSession, table_name: str, sequence_name: str = None):
    """Fix a PostgreSQL sequence for a given table."""
    if sequence_name is None:
        sequence_name = f"{table_name}_id_seq"
    
    try:
        await db.execute(text(f"""
            SELECT setval('{sequence_name}', 
                          COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1, 
                          false)
        """))
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        print(f"Error fixing sequence {sequence_name}: {str(e)}")
        return False

async def fix_all_sequences(db: AsyncSession):
    """Fix all sequences in the database."""
    tables = [
        'categories', 'subcategories', 'products', 'product_images',
        'product_variants', 'product_attributes', 'users', 'orders',
        'order_items', 'cart_items', 'product_reviews', 'coupons',
        'notifications', 'analytics_events', 'search_logs'
    ]
    
    results = {}
    for table in tables:
        result = await fix_sequence(db, table)
        results[table] = result
    
    return results
