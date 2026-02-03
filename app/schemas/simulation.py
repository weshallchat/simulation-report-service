"""Pydantic schemas for simulation endpoints."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.models.simulation import SimulationStatus


class SimulationCreate(BaseModel):
    """Schema for creating a new simulation job."""

    simulation_type: str = Field(
        ...,
        description="Type of simulation to run (opaque to the service)",
        min_length=1,
        max_length=255,
        examples=["monte_carlo", "finite_element", "weather_forecast"]
    )
    parameters: dict[str, Any] = Field(
        ...,
        description="Simulation parameters (arbitrary JSON, not interpreted by the service)"
    )
    job_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="User-defined metadata for the job"
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification",
        max_length=2048
    )


class SimulationResponse(BaseModel):
    """Schema for simulation job response after creation."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_id: UUID = Field(..., alias="id", description="Unique job identifier")
    user_id: UUID = Field(..., description="Owner user ID")
    status: SimulationStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")


class SimulationStatusResponse(BaseModel):
    """Schema for simulation job status response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_id: UUID = Field(..., alias="id", description="Unique job identifier")
    user_id: UUID = Field(..., description="Owner user ID")
    simulation_type: str = Field(..., description="Type of simulation")
    status: SimulationStatus = Field(..., description="Current job status")
    progress: Optional[float] = Field(
        default=None,
        description="Job progress (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    job_metadata: dict[str, Any] = Field(default_factory=dict, description="User-defined metadata")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")
    error: Optional[dict[str, str]] = Field(
        default=None,
        description="Error information if job failed"
    )


class SimulationResultResponse(BaseModel):
    """Schema for simulation result response."""

    job_id: UUID = Field(..., description="Unique job identifier")
    status: SimulationStatus = Field(..., description="Current job status")
    result: Optional[dict[str, Any]] = Field(
        default=None,
        description="Simulation result (only present when COMPLETED)"
    )
    output_format: Optional[str] = Field(
        default=None,
        description="Format of the result data"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Job completion timestamp"
    )
    message: Optional[str] = Field(
        default=None,
        description="Status message if job is not completed"
    )
