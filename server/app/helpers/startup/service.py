import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ndc_user_access import NdcUserAccess
from app.utils.password import hash_password

logger = logging.getLogger(__name__)



class StartupService:
    @staticmethod
    async def run_migrations(session: AsyncSession) -> None:
        """Run schema migrations to ensure required columns exist."""
        # Ensure hashed_password, reset_token, reset_token_expires_at exist on ndc_user_access
        try:
            await session.execute(text("ALTER TABLE ndc_user_access ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255)"))
            await session.execute(text("ALTER TABLE ndc_user_access ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255)"))
            await session.execute(text("ALTER TABLE ndc_user_access ADD COLUMN IF NOT EXISTS reset_token_expires_at TIMESTAMP"))
            await session.commit()
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE ndc_user_access ADD COLUMN hashed_password VARCHAR(255)"))
                await session.execute(text("ALTER TABLE ndc_user_access ADD COLUMN reset_token VARCHAR(255)"))
                await session.execute(text("ALTER TABLE ndc_user_access ADD COLUMN reset_token_expires_at TIMESTAMP"))
                await session.commit()
            except Exception:
                await session.rollback()

        # Ensure is_fnf_email_sent exists on ndc_records
        try:
            await session.execute(text("ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS is_fnf_email_sent BOOLEAN DEFAULT false"))
            await session.commit()
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE ndc_records ADD COLUMN is_fnf_email_sent BOOLEAN DEFAULT false"))
                await session.commit()
            except Exception:
                await session.rollback()

        # Ensure is_fnf_revision_email_sent exists on ndc_records
        try:
            await session.execute(text("ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS is_fnf_revision_email_sent BOOLEAN DEFAULT false"))
            await session.commit()
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE ndc_records ADD COLUMN is_fnf_revision_email_sent BOOLEAN DEFAULT false"))
                await session.commit()
            except Exception:
                await session.rollback()


    @staticmethod
    async def seed_super_admins(session: AsyncSession) -> None:
        """Seed or ensure super admin users exist in the database."""
        super_admin_env = os.getenv("SUPER_ADMIN_EMAIL", "")
        super_admins = [e.strip().lower() for e in super_admin_env.split(",") if e.strip()]

        for sa_email in super_admins:
            stmt = select(NdcUserAccess).where(NdcUserAccess.email == sa_email)
            res = await session.execute(stmt)
            user_access = res.scalar_one_or_none()
            if not user_access:
                print(f"Seeding super admin: {sa_email}")
                user_access = NdcUserAccess(
                    email=sa_email,
                    name=sa_email.split('@')[0],
                    role="super_admin",
                    status="approved",
                    hashed_password=hash_password("Adani@123"),
                    approved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    approved_by="system"
                )
                session.add(user_access)
            else:
                print(f"Ensuring super admin privileges: {sa_email}")
                user_access.role = "super_admin"
                user_access.status = "approved"
                if not user_access.hashed_password:
                    user_access.hashed_password = hash_password("Adani@123")
                # Update attributes in-place to ensure SQLAlchemy flushes correctly
                session.add(user_access)


    @staticmethod
    async def seed_demo_admin(session: AsyncSession) -> None:
        """Seed the demo admin user if it doesn't exist."""
        stmt = select(NdcUserAccess).where(NdcUserAccess.email == "demo.admin@adani.com")
        res = await session.execute(stmt)
        demo_admin = res.scalar_one_or_none()
        if not demo_admin:
            print("Seeding demo admin: demo.admin@adani.com")
            demo_admin = NdcUserAccess(
                email="demo.admin@adani.com",
                name="Demo Admin",
                role="admin",
                status="approved",
                hashed_password=hash_password("Adani@123"),
                approved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                approved_by="system"
            )
            session.add(demo_admin)
        else:
            if not demo_admin.hashed_password:
                demo_admin.hashed_password = hash_password("Adani@123")
            session.add(demo_admin)
