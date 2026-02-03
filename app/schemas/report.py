"""Pydantic schemas for report endpoints."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.report import ReportStatus


class ReportCreate(BaseModel):
    """Schema for creating a new report."""

    simulation_job_ids: list[UUID] = Field(
        ...,
        description="List of simulation job IDs to include in the report",
        min_length=1
    )
    report_type: str = Field(
        ...,
        description="Type of report to generate (opaque to the service)",
        min_length=1,
        max_length=255,
        examples=["summary", "detailed_analysis", "comparison"]
    )
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Report generation parameters"
    )
    output_format: str = Field(
        ...,
        description="Desired output format",
        examples=["PDF", "HTML", "JSON", "CSV"]
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Normalize output format to uppercase."""
        return v.upper()


class ReportResponse(BaseModel):
    """Schema for report response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    report_id: UUID = Field(..., alias="id", description="Unique report identifier")
    user_id: UUID = Field(..., description="Owner user ID")
    report_type: str = Field(..., description="Type of report")
    output_format: str = Field(..., description="Output format")
    status: ReportStatus = Field(..., description="Current report status")
    simulation_job_ids: list[UUID] = Field(..., description="Source simulation job IDs")
    created_at: datetime = Field(..., description="Report creation timestamp")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Report completion timestamp"
    )
    download_url: Optional[str] = Field(
        default=None,
        description="Pre-signed URL to download the report"
    )
    url_expires_at: Optional[datetime] = Field(
        default=None,
        description="Expiration time for the download URL"
    )
    content_type: Optional[str] = Field(
        default=None,
        description="MIME type of the report file"
    )
    size_bytes: Optional[int] = Field(
        default=None,
        description="Size of the report file in bytes"
    )
    error: Optional[dict[str, str]] = Field(
        default=None,
        description="Error information if report generation failed"
    )
