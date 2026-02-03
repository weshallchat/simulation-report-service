"""Simulation endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies import (
    get_simulation_service,
    get_current_user_id,
)
from app.services.simulation_service import SimulationService
from app.services.exceptions import SimulationNotFoundError, ResultNotFoundError
from app.schemas.simulation import (
    SimulationCreate,
    SimulationResponse,
    SimulationStatusResponse,
    SimulationResultResponse,
)
from app.models.simulation import SimulationStatus

router = APIRouter()


@router.post(
    "",
    response_model=SimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a simulation job",
    description="""
    Submit a new simulation job for processing.
    
    The service is simulation-agnostic - it doesn't interpret the simulation_type
    or parameters. These are passed through to the simulation handlers.
    
    Returns immediately with job metadata. Use the GET endpoints to check
    status and retrieve results.
    """,
)
def create_simulation(
    data: SimulationCreate,
    user_id: UUID = Depends(get_current_user_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> SimulationResponse:
    """Submit a new simulation job."""
    job = simulation_service.create_job(user_id, data)
    return SimulationResponse.model_validate(job)


@router.get(
    "/{job_id}",
    response_model=SimulationStatusResponse,
    summary="Get simulation status",
    description="""
    Get the current status and metadata of a simulation job.
    
    Returns job metadata including:
    - Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
    - Progress indicator (0.0 to 1.0) if available
    - Timestamps (created, started, completed)
    - Error information if failed
    """,
)
def get_simulation_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> SimulationStatusResponse:
    """Get simulation job status and metadata."""
    try:
        job = simulation_service.get_job(user_id, job_id)
        
        response = SimulationStatusResponse.model_validate(job)
        
        # Add error info if failed
        if job.status == SimulationStatus.FAILED and (job.error_code or job.error_message):
            response.error = {
                "code": job.error_code or "UNKNOWN",
                "message": job.error_message or "Unknown error"
            }
        
        return response
        
    except SimulationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job {job_id} not found",
        )


@router.get(
    "/{job_id}/result",
    response_model=SimulationResultResponse,
    summary="Get simulation result",
    description="""
    Get the result of a completed simulation job.
    
    If the simulation is not yet completed, returns the current status
    with a message indicating the job is still in progress.
    
    If completed, returns the full result payload.
    """,
)
def get_simulation_result(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> SimulationResultResponse:
    """Get simulation result."""
    try:
        result = simulation_service.get_job_result(user_id, job_id)
        return SimulationResultResponse(**result)
        
    except SimulationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job {job_id} not found",
        )
    except ResultNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result for simulation {job_id} not found",
        )


@router.get(
    "",
    response_model=list[SimulationStatusResponse],
    summary="List simulation jobs",
    description="List all simulation jobs for the current user with optional filtering.",
)
def list_simulations(
    status: Optional[SimulationStatus] = Query(
        default=None,
        description="Filter by job status"
    ),
    simulation_type: Optional[str] = Query(
        default=None,
        description="Filter by simulation type"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    user_id: UUID = Depends(get_current_user_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> list[SimulationStatusResponse]:
    """List simulation jobs."""
    jobs = simulation_service.list_jobs(
        user_id=user_id,
        status=status,
        simulation_type=simulation_type,
        limit=limit,
        offset=offset,
    )
    return [SimulationStatusResponse.model_validate(job) for job in jobs]


@router.post(
    "/{job_id}/cancel",
    response_model=SimulationStatusResponse,
    summary="Cancel a simulation job",
    description="Cancel a pending or running simulation job.",
)
def cancel_simulation(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> SimulationStatusResponse:
    """Cancel a simulation job."""
    try:
        job = simulation_service.cancel_job(user_id, job_id)
        return SimulationStatusResponse.model_validate(job)
        
    except SimulationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job {job_id} not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
