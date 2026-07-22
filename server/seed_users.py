import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Load environment variables from .env
load_dotenv()

# Set PYTHONPATH/import structure
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.ndc_user_access import NdcUserAccess
from app.utils.password import hash_password
from config.database import async_session

# Define the user list from the requested screenshot
USERS_TO_SEED = [
    {
        "email": "subratkumar.sahu@adani.com",
        "name": "Subrat Kumar Sahu",
        "role": "super_admin",
        "status": "approved",
        "password": "Adani@123"
    },
    {
        "email": "tathagat.vyas@adani.com",
        "name": "tathagat.vyas",
        "role": "super_admin",
        "status": "approved",
        "password": "Adani@123"
    },
    {
        "email": "demo.admin@adani.com",
        "name": "Demo Admin",
        "role": "admin",
        "status": "approved",
        "password": "Adani@123"
    },
    {
        "email": "laxminarayana@adani.com",
        "name": "laxmi narayan",
        "role": "super_admin",
        "status": "approved",
        "password": "Adani@123"
    },
    {
        "email": "sahil.singh1@adani.com",
        "name": "sahil.singh1",
        "role": "super_admin",
        "status": "approved",
        "password": "Adani@123"
    }
]

async def seed_users():
    print("Connecting to the database and seeding users...")
    async with async_session() as session:
        for u_data in USERS_TO_SEED:
            email = u_data["email"].strip().lower()
            name = u_data["name"]
            role = u_data["role"]
            status = u_data["status"]
            password = u_data["password"]
            hashed = hash_password(password)

            stmt = select(NdcUserAccess).where(NdcUserAccess.email == email)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if user:
                print(f"Updating user: {email} -> Role: {role}, Status: {status}")
                user.name = name
                user.role = role
                user.status = status
                user.hashed_password = hashed
                # Reset tokens if they exist so the login is fresh
                user.approval_token = None
                user.reset_token = None
                user.reset_token_expires_at = None
                session.add(user)
            else:
                print(f"Creating user: {email} -> Role: {role}, Status: {status}")
                user = NdcUserAccess(
                    email=email,
                    name=name,
                    role=role,
                    status=status,
                    hashed_password=hashed,
                    approved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    approved_by="system_seed"
                )
                session.add(user)

        await session.commit()
    print("\nDatabase seeding completed successfully!")
    print("\n" + "=" * 50)
    print("           LOGIN DETAILS FOR SEEDED USERS")
    print("=" * 50)
    for u_data in USERS_TO_SEED:
        print(f"Name:     {u_data['name']}")
        print(f"Email:    {u_data['email']}")
        print(f"Password: {u_data['password']}")
        print(f"Role:     {u_data['role']}")
        print(f"Status:   {u_data['status']}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(seed_users())
