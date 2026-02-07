import os
import uuid
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Product, Admin
from app.auth import verify_password, create_access_token, get_admin_from_cookie

router = APIRouter(prefix="/admin", tags=["admin"])

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


async def require_admin(request: Request, db: AsyncSession) -> Admin | None:
    admin = await get_admin_from_cookie(request, db)
    if not admin:
        return None
    return admin


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Admin).where(Admin.username == username))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(password, admin.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Credenciales inválidas"}
        )
    token = create_access_token({"sub": admin.username})
    response = RedirectResponse(url="/admin/products", status_code=303)
    response.set_cookie("access_token", token, httponly=True, max_age=86400)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)
    result = await db.execute(select(Product).order_by(Product.created_at.desc()))
    products = result.scalars().all()
    return templates.TemplateResponse(
        "products.html", {"request": request, "products": products, "admin": admin}
    )


@router.get("/products/new", response_class=HTMLResponse)
async def product_new_form(request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse(
        "product_form.html", {"request": request, "product": None, "admin": admin}
    )


@router.post("/products/new", response_class=HTMLResponse)
async def product_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form(...),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    admin = await require_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)

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
        description=description or None,
        price=price,
        category=category,
        image_path=image_path,
    )
    db.add(product)
    await db.commit()
    return RedirectResponse(url="/admin/products", status_code=303)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def product_edit_form(
    request: Request, product_id: int, db: AsyncSession = Depends(get_db)
):
    admin = await require_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return RedirectResponse(url="/admin/products", status_code=303)
    return templates.TemplateResponse(
        "product_form.html", {"request": request, "product": product, "admin": admin}
    )


@router.post("/products/{product_id}/edit", response_class=HTMLResponse)
async def product_update(
    request: Request,
    product_id: int,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form(...),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    admin = await require_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return RedirectResponse(url="/admin/products", status_code=303)

    product.name = name
    product.description = description or None
    product.price = price
    product.category = category

    if image and image.filename:
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
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/products/{product_id}/delete")
async def product_delete(
    request: Request, product_id: int, db: AsyncSession = Depends(get_db)
):
    admin = await require_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product:
        if product.image_path:
            filepath = os.path.join(UPLOAD_DIR, product.image_path)
            if os.path.exists(filepath):
                os.remove(filepath)
        await db.delete(product)
        await db.commit()
    return RedirectResponse(url="/admin/products", status_code=303)
