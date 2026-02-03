"""Simulation job model."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Numeric, BigInteger, Text, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SimulationStatus(str, PyEnum):
    """Enumeration of possible simulation job statuses."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SimulationJob(Base):
    """
    Simulation job model.
    
    Stores metadata about simulation jobs. The actual simulation parameters
    and results may be stored in S3 for large payloads.
    """

    __tablename__ = "simulation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Simulation type - opaque to the service
    simulation_type = Column(String(255), nullable=False, index=True)
    
    # Job status
    status = Column(
        Enum(SimulationStatus, name="simulation_status"),
        nullable=False,
        default=SimulationStatus.PENDING,
        index=True
    )
    progress = Column(Numeric(5, 4), nullable=True)  # 0.0000 to 1.0000
    
    # Parameters - stored in DB if small, or reference to S3
    parameters = Column(JSONB, nullable=False, default=dict)
    parameters_s3_key = Column(String(512), nullable=True)
    
    # Result reference - always stored in S3 for consistency
    result_s3_key = Column(String(512), nullable=True)
    result_size_bytes = Column(BigInteger, nullable=True)
    
    # Error information
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # User-defined metadata (named job_metadata to avoid SQLAlchemy reserved name)
    job_metadata = Column(JSONB, nullable=False, default=dict)
    
    # Callback URL for completion notification
    callback_url = Column(String(2048), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="simulation_jobs")

    def __repr__(self) -> str:
        return f"<SimulationJob(id={self.id}, type={self.simulation_type}, status={self.status})>"
