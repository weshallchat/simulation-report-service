"""Report model."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, BigInteger, Text, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReportStatus(str, PyEnum):
    """Enumeration of possible report statuses."""

    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Report(Base):
    """
    Report model.
    
    Stores metadata about generated reports. The actual report files
    are stored in S3.
    """

    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Report type - opaque to the service
    report_type = Column(String(255), nullable=False, index=True)
    
    # Output format
    output_format = Column(String(50), nullable=False)  # PDF, HTML, JSON, etc.
    
    # Status
    status = Column(
        Enum(ReportStatus, name="report_status"),
        nullable=False,
        default=ReportStatus.PENDING,
        index=True
    )
    
    # Source simulation job IDs
    simulation_job_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    
    # Report generation parameters
    parameters = Column(JSONB, nullable=False, default=dict)
    
    # S3 storage reference
    s3_key = Column(String(512), nullable=True)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    
    # Error information
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For auto-cleanup

    # Relationships
    user = relationship("User", backref="reports")

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, type={self.report_type}, status={self.status})>"
