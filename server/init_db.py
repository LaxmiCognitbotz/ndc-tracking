import asyncio

from dotenv import load_dotenv

from app.models import Base
from app.models.employee_email_master import EmployeeEmailMaster
from app.models.ndc_approval import NdcApproval
from app.models.ndc_auth_audit_log import NdcAuthAuditLog
from app.models.ndc_record import NdcRecord
from app.models.ndc_user_access import NdcUserAccess
from app.models.rm_email_configuration import RmEmailConfiguration
from app.models.upload_batch import UploadBatch
from app.models.email_recipient import EmailRecipient
from config.database import engine

__all__ = [
    "EmployeeEmailMaster",
    "NdcApproval",
    "NdcAuthAuditLog",
    "NdcRecord",
    "NdcUserAccess",
    "RmEmailConfiguration",
    "UploadBatch",
    "EmailRecipient",
]


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
