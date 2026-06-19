import asyncio
from database import engine, async_session
from app.models import Base
from app.models.email_recipient import EmailRecipient

async def init_dummy_emails():
    # Create the table
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Insert dummy data if empty
    async with async_session() as session:
        from sqlalchemy import select
        res = await session.execute(select(EmailRecipient))
        if not res.scalars().first():
            dummy1 = EmailRecipient(name="Alice Manager", email="alice@company.com", department="HR", role="HR Head")
            dummy2 = EmailRecipient(name="Bob IT Support", email="bob.it@company.com", department="IT", role="SysAdmin")
            session.add_all([dummy1, dummy2])
            await session.commit()
            print("Inserted dummy email recipients.")
        else:
            print("Email recipients table already populated.")

if __name__ == "__main__":
    asyncio.run(init_dummy_emails())
