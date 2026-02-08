"""
Migration script to convert product categories from strings to foreign keys.

This script:
1. Reads existing products and their string categories
2. Creates Category records for unique categories
3. Updates products to use category_id instead of category string
4. Drops the old category column

Run this AFTER deploying the new models but BEFORE using the app.
"""
import asyncio
from sqlalchemy import text
from app.database import engine, async_session
from app.models import Category, Product


async def migrate():
    print("Starting migration...")

    async with async_session() as session:
        # Step 1: Get unique categories from existing products
        print("\n1. Finding existing categories...")
        result = await session.execute(
            text("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
        )
        existing_categories = [row[0] for row in result.fetchall()]
        print(f"Found {len(existing_categories)} unique categories: {existing_categories}")

        if not existing_categories:
            print("No existing categories found. Migration complete.")
            return

        # Step 2: Create Category records
        print("\n2. Creating category records...")
        category_map = {}  # Map old category name to new category_id

        for cat_name in existing_categories:
            # Check if category already exists
            result = await session.execute(
                text("SELECT id FROM categories WHERE name = :name"),
                {"name": cat_name}
            )
            existing = result.fetchone()

            if existing:
                category_id = existing[0]
                print(f"  - Category '{cat_name}' already exists (id: {category_id})")
            else:
                # Create new category
                result = await session.execute(
                    text("INSERT INTO categories (name, created_at) VALUES (:name, NOW()) RETURNING id"),
                    {"name": cat_name}
                )
                category_id = result.fetchone()[0]
                print(f"  - Created category '{cat_name}' (id: {category_id})")

            category_map[cat_name] = category_id

        await session.commit()

        # Step 3: Add category_id column if it doesn't exist
        print("\n3. Adding category_id column...")
        try:
            await session.execute(
                text("""
                    ALTER TABLE products
                    ADD COLUMN IF NOT EXISTS category_id INTEGER
                    REFERENCES categories(id)
                """)
            )
            await session.commit()
            print("  - category_id column added")
        except Exception as e:
            print(f"  - column might already exist: {e}")
            await session.rollback()

        # Step 4: Update products with category_id
        print("\n4. Updating products with category_id...")
        for cat_name, cat_id in category_map.items():
            result = await session.execute(
                text("""
                    UPDATE products
                    SET category_id = :category_id
                    WHERE category = :category_name
                """),
                {"category_id": cat_id, "category_name": cat_name}
            )
            count = result.rowcount
            print(f"  - Updated {count} products with category '{cat_name}' -> id {cat_id}")

        await session.commit()

        # Step 5: Make category_id NOT NULL
        print("\n5. Making category_id NOT NULL...")
        try:
            await session.execute(
                text("ALTER TABLE products ALTER COLUMN category_id SET NOT NULL")
            )
            await session.commit()
            print("  - category_id is now NOT NULL")
        except Exception as e:
            print(f"  - Error: {e}")
            await session.rollback()

        # Step 6: Drop old category column
        print("\n6. Dropping old category column...")
        try:
            await session.execute(
                text("ALTER TABLE products DROP COLUMN IF EXISTS category")
            )
            await session.commit()
            print("  - Old category column dropped")
        except Exception as e:
            print(f"  - Error: {e}")
            await session.rollback()

    print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
