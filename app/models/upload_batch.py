from sqlalchemy import Column, Integer, String, DateTime, Text, func
from app.models import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(500))
    source_type = Column(String(100))
    records_count = Column(Integer)
    uploaded_by = Column(String(200))
    uploaded_at = Column(DateTime, server_default=func.now())
    status = Column(String(50))
    error_message = Column(Text)
