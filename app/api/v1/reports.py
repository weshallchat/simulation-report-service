"""Report endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies import (
    get_report_service,
    get_current_user_id,
)
from app.services.report_service import ReportService
from app.services.exceptions import (
    ReportNotFoundError,
    SimulationNotFoundError,
    SimulationNotCompletedError,
)
from app.schemas.report import ReportCreate, ReportResponse
from app.models.report import ReportStatus

router = APIRouter()


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a report",
    description="""
    Request generation of a report from one or more completed simulation results.
    
    The service is report-agnostic - it doesn't interpret the report_type
    or parameters. These are passed through to the report handlers.
    
    All referenced simulation jobs must exist and be in COMPLETED status.
    
    Returns immediately with report metadata. Use the GET endpoint to check
    status and retrieve the download URL.
    """,
)
def create_report(
    data: ReportCreate,
    user_id: UUID = Depends(get_current_user_id),
    report_service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    """Request report generation."""
    try:
        report = report_service.create_report(user_id, data)
        return ReportResponse.model_validate(report)
        
    except SimulationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job {e.resource_id} not found",
        )
    except SimulationNotCompletedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Simulation job {e.job_id} is not completed",
        )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report",
    description="""
    Get report status and download URL if ready.
    
    When the report is completed, the response includes:
    - A pre-signed download URL (expires after 1 hour)
    - File metadata (content type, size)
    - Completion timestamp
    
    If the report is still generating, only status information is returned.
    """,
)
def get_report(
    report_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    report_service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    """Get report status and download URL."""
    try:
        report_data = report_service.get_report_with_url(user_id, report_id)
        
        # Map the dict to ReportResponse
        return ReportResponse(
            id=UUID(report_data["report_id"]),
            user_id=UUID(report_data["user_id"]),
            report_type=report_data["report_type"],
            output_format=report_data["output_format"],
            status=ReportStatus(report_data["status"]),
            simulation_job_ids=[UUID(sid) for sid in report_data["simulation_job_ids"]],
            created_at=report_data["created_at"],
            completed_at=report_data.get("completed_at"),
            download_url=report_data.get("download_url"),
            url_expires_at=report_data.get("url_expires_at"),
            content_type=report_data.get("content_type"),
            size_bytes=report_data.get("size_bytes"),
            error=report_data.get("error"),
        )
        
    except ReportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )


@router.get(
    "",
    response_model=list[ReportResponse],
    summary="List reports",
    description="List all reports for the current user with optional filtering.",
)
def list_reports(
    status: Optional[ReportStatus] = Query(
        default=None,
        description="Filter by report status"
    ),
    report_type: Optional[str] = Query(
        default=None,
        description="Filter by report type"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    user_id: UUID = Depends(get_current_user_id),
    report_service: ReportService = Depends(get_report_service),
) -> list[ReportResponse]:
    """List reports."""
    reports = report_service.list_reports(
        user_id=user_id,
        status=status,
        report_type=report_type,
        limit=limit,
        offset=offset,
    )
    return [ReportResponse.model_validate(report) for report in reports]
