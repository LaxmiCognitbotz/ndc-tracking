import asyncio
import os
from dotenv import load_dotenv
from database import engine
from app.models import Base

# Ensure all models are imported so SQLAlchemy registers them on Base
from app.models.ndc_record import NdcRecord
from app.models.ndc_approval import NdcApproval
from app.models.upload_batch import UploadBatch


async def init_database():
    """Connect to the database and create tables if they do not exist."""
    print("Connecting to the database...")
    async with engine.begin() as conn:
        # Uncomment the line below if you want to drop all tables first before recreating them:
        # print("Dropping existing tables...")
        # await conn.run_sync(Base.metadata.drop_all)

        print("Creating tables (if they do not exist)...")
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database initialized successfully!")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(init_database())
