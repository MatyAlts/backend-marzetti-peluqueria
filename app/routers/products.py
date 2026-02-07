import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Product, Admin
from app.schemas import ProductResponse
from app.auth import get_current_admin

router = APIRouter(prefix="/api/products", tags=["products"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


def product_to_response(product: Product) -> ProductResponse:
    image_url = f"/uploads/{product.image_path}" if product.image_path else None
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        price=float(product.price),
        category=product.category,
        image_url=image_url,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("", response_model=list[ProductResponse])
async def list_products(
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).order_by(Product.created_at.desc())
    if category:
        query = query.where(Product.category == category)
    result = await db.execute(query)
    products = result.scalars().all()
    return [product_to_response(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product_to_response(product)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    name: str = Form(...),
    description: str | None = Form(None),
    price: float = Form(...),
    category: str = Form(...),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    image_path = None
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1]
        image_path = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, image_path)
        content = await image.read()
        with open(filepath, "wb") as f:
            f.write(content)

    product = Product(
        name=name,
        description=description,
        price=price,
        category=category,
        image_path=image_path,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product_to_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    name: str | None = Form(None),
    description: str | None = Form(None),
    price: float | None = Form(None),
    category: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if name is not None:
        product.name = name
    if description is not None:
        product.description = description
    if price is not None:
        product.price = price
    if category is not None:
        product.category = category

    if image and image.filename:
        # Delete old image
        if product.image_path:
            old_path = os.path.join(UPLOAD_DIR, product.image_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        ext = os.path.splitext(image.filename)[1]
        product.image_path = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, product.image_path)
        content = await image.read()
        with open(filepath, "wb") as f:
            f.write(content)

    await db.commit()
    await db.refresh(product)
    return product_to_response(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if product.image_path:
        filepath = os.path.join(UPLOAD_DIR, product.image_path)
        if os.path.exists(filepath):
            os.remove(filepath)

    await db.delete(product)
    await db.commit()
