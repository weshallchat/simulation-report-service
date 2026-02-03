"""Report service for managing report generation."""

import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models.report import Report, ReportStatus
from app.models.simulation import SimulationJob, SimulationStatus
from app.schemas.report import ReportCreate
from app.storage.blob_storage import BlobStorage, S3Storage
from app.services.exceptions import (
    ReportNotFoundError,
    SimulationNotFoundError,
    SimulationNotCompletedError,
)

logger = logging.getLogger(__name__)


class ReportService:
    """
    Service for managing report generation.
    
    This service is report-agnostic - it doesn't interpret the
    report type or parameters. The actual generation is handled
    by registered handlers or external services.
    """

    def __init__(self, db: Session, blob_storage: BlobStorage):
        """
        Initialize the report service.
        
        Args:
            db: SQLAlchemy database session
            blob_storage: Blob storage client for S3/compatible storage
        """
        self.db = db
        self.blob_storage = blob_storage

    def create_report(self, user_id: UUID, data: ReportCreate) -> Report:
        """
        Create a new report generation job.
        
        Args:
            user_id: Owner user ID
            data: Report creation data
            
        Returns:
            Created Report instance
            
        Raises:
            SimulationNotFoundError: If a referenced simulation doesn't exist
            SimulationNotCompletedError: If a referenced simulation isn't completed
        """
        # Verify all simulation jobs exist and are completed
        for sim_id in data.simulation_job_ids:
            job = self.db.query(SimulationJob).filter(
                SimulationJob.id == sim_id,
                SimulationJob.user_id == user_id
            ).first()
            
            if not job:
                raise SimulationNotFoundError(sim_id)
            
            if job.status != SimulationStatus.COMPLETED:
                raise SimulationNotCompletedError(sim_id)
        
        report = Report(
            user_id=user_id,
            report_type=data.report_type,
            output_format=data.output_format,
            simulation_job_ids=data.simulation_job_ids,
            parameters=data.parameters or {},
            status=ReportStatus.PENDING,
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        # Enqueue for async generation
        self._enqueue_report(report.id)
        
        logger.info(f"Created report {report.id} for user {user_id}")
        return report

    def get_report(self, user_id: UUID, report_id: UUID) -> Report:
        """
        Get a report by ID (with ownership verification).
        
        Args:
            user_id: Requesting user ID
            report_id: Report ID
            
        Returns:
            Report instance
            
        Raises:
            ReportNotFoundError: If report doesn't exist or user doesn't own it
        """
        report = self.db.query(Report).filter(
            Report.id == report_id,
            Report.user_id == user_id
        ).first()
        
        if not report:
            raise ReportNotFoundError(report_id)
        
        return report

    def get_report_by_id(self, report_id: UUID) -> Report:
        """
        Get a report by ID (without ownership check).
        
        Used internally by workers.
        
        Args:
            report_id: Report ID
            
        Returns:
            Report instance
            
        Raises:
            ReportNotFoundError: If report doesn't exist
        """
        report = self.db.query(Report).filter(Report.id == report_id).first()
        
        if not report:
            raise ReportNotFoundError(report_id)
        
        return report

    def get_report_with_url(self, user_id: UUID, report_id: UUID) -> dict[str, Any]:
        """
        Get report with download URL if ready.
        
        Args:
            user_id: Requesting user ID
            report_id: Report ID
            
        Returns:
            Report data with optional download URL
        """
        report = self.get_report(user_id, report_id)
        
        response = {
            "report_id": str(report.id),
            "user_id": str(report.user_id),
            "status": report.status.value,
            "report_type": report.report_type,
            "output_format": report.output_format,
            "simulation_job_ids": [str(sid) for sid in report.simulation_job_ids],
            "created_at": report.created_at.isoformat(),
        }
        
        if report.status == ReportStatus.COMPLETED and report.s3_key:
            # Generate pre-signed URL
            expires_in = settings.PRESIGNED_URL_EXPIRY
            response["download_url"] = self.blob_storage.generate_presigned_url(
                report.s3_key,
                expires_in=expires_in
            )
            response["url_expires_at"] = (
                datetime.utcnow() + timedelta(seconds=expires_in)
            ).isoformat()
            response["content_type"] = report.content_type
            response["size_bytes"] = report.size_bytes
            response["completed_at"] = report.completed_at.isoformat() if report.completed_at else None
        
        if report.status == ReportStatus.FAILED:
            response["error"] = {
                "code": report.error_code,
                "message": report.error_message
            }
        
        return response

    def list_reports(
        self,
        user_id: UUID,
        status: Optional[ReportStatus] = None,
        report_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Report]:
        """
        List reports for a user.
        
        Args:
            user_id: Owner user ID
            status: Optional status filter
            report_type: Optional report type filter
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of Report instances
        """
        query = self.db.query(Report).filter(Report.user_id == user_id)
        
        if status:
            query = query.filter(Report.status == status)
        
        if report_type:
            query = query.filter(Report.report_type == report_type)
        
        return query.order_by(Report.created_at.desc()).offset(offset).limit(limit).all()

    def update_report_status(
        self,
        report_id: UUID,
        status: ReportStatus,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Report:
        """
        Update report status.
        
        Args:
            report_id: Report ID
            status: New status
            error_code: Error code if failed
            error_message: Error message if failed
            
        Returns:
            Updated Report instance
        """
        report = self.get_report_by_id(report_id)
        
        report.status = status
        
        if status in (ReportStatus.COMPLETED, ReportStatus.FAILED):
            report.completed_at = datetime.utcnow()
        
        if error_code:
            report.error_code = error_code
        if error_message:
            report.error_message = error_message
        
        self.db.commit()
        self.db.refresh(report)
        
        logger.info(f"Updated report {report_id} status to {status.value}")
        return report

    def save_report_file(
        self,
        report_id: UUID,
        file_content: bytes,
        content_type: str,
        filename: str,
    ) -> Report:
        """
        Save generated report file to S3.
        
        Args:
            report_id: Report ID
            file_content: Report file content
            content_type: MIME type of the file
            filename: Filename for storage
            
        Returns:
            Updated Report instance
        """
        report = self.get_report_by_id(report_id)
        
        s3_key = S3Storage.build_report_key(
            str(report.user_id), str(report_id), filename
        )
        
        file_obj = BytesIO(file_content)
        self.blob_storage.upload_file(s3_key, file_obj, content_type)
        
        report.s3_key = s3_key
        report.content_type = content_type
        report.size_bytes = len(file_content)
        report.status = ReportStatus.COMPLETED
        report.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(report)
        
        logger.info(f"Saved report file for {report_id} to {s3_key}")
        return report

    def _enqueue_report(self, report_id: UUID) -> None:
        """
        Enqueue report for async generation.
        
        Args:
            report_id: Report ID to enqueue
        """
        # Import here to avoid circular imports
        from app.workers.tasks import generate_report
        generate_report.delay(str(report_id))
        logger.info(f"Enqueued report {report_id} for generation")
