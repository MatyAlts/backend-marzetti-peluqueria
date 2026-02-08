import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from app.config import get_settings
from app.database import engine, Base, async_session
from app.models import Admin, Product, Category  # noqa: F401 — ensure models are registered
from app.auth import hash_password
from app.routers import products as products_router
from app.routers import auth as auth_router
from app.routers import categories as categories_router
from app.admin.router import router as admin_router

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create default admin if none exists
    settings = get_settings()
    async with async_session() as db:
        result = await db.execute(select(Admin))
        if not result.scalar_one_or_none():
            admin = Admin(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
            )
            db.add(admin)
            await db.commit()

    yield

    await engine.dispose()


app = FastAPI(title="Marzetti Backend", lifespan=lifespan)

settings = get_settings()
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static uploads
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Routers
app.include_router(products_router.router)
app.include_router(categories_router.router)
app.include_router(auth_router.router)
app.include_router(admin_router)
