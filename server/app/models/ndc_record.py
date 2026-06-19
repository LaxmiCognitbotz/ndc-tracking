from sqlalchemy import (
    Column, Integer, BigInteger, String, Date, DateTime, CheckConstraint, Index,
    func,
)
from app.models import Base


class NdcRecord(Base):
    __tablename__ = "ndc_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_number = Column(BigInteger, nullable=False, unique=True)
    employee_name = Column(String(200), nullable=False)
    business_unit = Column(String(200))
    legal_employer = Column(String(200))
    location = Column(String(200))
    location_city = Column(String(100))
    department = Column(String(300))
    department_reporting_name = Column(String(200))
    ndc_stage = Column(String(50))
    resignation_date = Column(Date)
    last_working_date = Column(Date)
    ndc_assigned_date = Column(Date)
    ndc_initiated_date = Column(Date)
    ndc_completed_date = Column(Date)
    created_by = Column(String(200))
    source_file = Column(String(500))
    batch_id = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "ndc_stage IN ('Recovery Pending', 'GCC Pending', 'NDC Completed')",
            name="chk_stage",
        ),
        Index("idx_ndc_stage", "ndc_stage"),
        Index("idx_business_unit", "business_unit"),
        Index("idx_location_city", "location_city"),
        Index("idx_ndc_initiated", "ndc_initiated_date"),
    )
