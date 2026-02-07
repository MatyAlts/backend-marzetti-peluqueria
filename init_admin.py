"""Create or reset the admin user from environment variables."""

import asyncio
from sqlalchemy import select
from app.config import get_settings
from app.database import engine, Base, async_session
from app.models import Admin
from app.auth import hash_password


async def main():
    settings = get_settings()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        result = await db.execute(
            select(Admin).where(Admin.username == settings.ADMIN_USERNAME)
        )
        admin = result.scalar_one_or_none()

        if admin:
            admin.password_hash = hash_password(settings.ADMIN_PASSWORD)
            print(f"Admin '{settings.ADMIN_USERNAME}' password updated.")
        else:
            admin = Admin(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
            )
            db.add(admin)
            print(f"Admin '{settings.ADMIN_USERNAME}' created.")

        await db.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
