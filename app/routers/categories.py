from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Category, Admin, Product
from app.schemas import CategoryResponse, CategoryCreate, CategoryUpdate
from app.auth import get_current_admin

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Get all categories (public endpoint)"""
    result = await db.execute(select(Category).order_by(Category.name))
    categories = result.scalars().all()
    return categories


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single category by ID"""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return category


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    category_data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Create a new category (admin only)"""
    # Check if category already exists
    result = await db.execute(
        select(Category).where(Category.name == category_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="La categoría ya existe")

    category = Category(name=category_data.name)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Update a category (admin only)"""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    # Check if new name already exists (excluding current category)
    result = await db.execute(
        select(Category).where(
            Category.name == category_data.name, Category.id != category_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El nombre de categoría ya existe")

    category.name = category_data.name
    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Delete a category (admin only)"""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    # Check if category has products
    result = await db.execute(
        select(Product).where(Product.category_id == category_id).limit(1)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar una categoría que tiene productos asociados",
        )

    await db.delete(category)
    await db.commit()
