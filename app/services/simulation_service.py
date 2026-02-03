"""Simulation service for managing simulation jobs."""

import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models.simulation import SimulationJob, SimulationStatus
from app.schemas.simulation import SimulationCreate
from app.storage.blob_storage import BlobStorage, S3Storage
from app.services.exceptions import (
    SimulationNotFoundError,
    SimulationNotCompletedError,
    ResultNotFoundError,
)

logger = logging.getLogger(__name__)


class SimulationService:
    """
    Service for managing simulation jobs.
    
    This service is simulation-agnostic - it doesn't interpret the
    simulation type or parameters. The actual execution is handled
    by registered handlers or external services.
    """

    def __init__(self, db: Session, blob_storage: BlobStorage):
        """
        Initialize the simulation service.
        
        Args:
            db: SQLAlchemy database session
            blob_storage: Blob storage client for S3/compatible storage
        """
        self.db = db
        self.blob_storage = blob_storage

    def create_job(self, user_id: UUID, data: SimulationCreate) -> SimulationJob:
        """
        Create a new simulation job.
        
        Args:
            user_id: Owner user ID
            data: Simulation creation data
            
        Returns:
            Created SimulationJob instance
        """
        job = SimulationJob(
            user_id=user_id,
            simulation_type=data.simulation_type,
            job_metadata=data.job_metadata or {},
            callback_url=data.callback_url,
            status=SimulationStatus.PENDING,
        )
        
        # First add and flush to get the job ID
        self.db.add(job)
        self.db.flush()
        
        # Decide where to store parameters based on size
        params_json = json.dumps(data.parameters, default=str)
        params_size = len(params_json.encode("utf-8"))
        
        if params_size > settings.PARAMETERS_SIZE_THRESHOLD:
            # Store large parameters in S3
            s3_key = S3Storage.build_simulation_key(
                str(user_id), str(job.id), "parameters.json"
            )
            self.blob_storage.upload_json(s3_key, data.parameters)
            job.parameters = {"_s3_reference": True}
            job.parameters_s3_key = s3_key
            logger.info(f"Stored large parameters in S3: {s3_key}")
        else:
            # Store small parameters in PostgreSQL
            job.parameters = data.parameters
        
        self.db.commit()
        self.db.refresh(job)
        
        # Enqueue job for async processing
        self._enqueue_job(job.id)
        
        logger.info(f"Created simulation job {job.id} for user {user_id}")
        return job

    def get_job(self, user_id: UUID, job_id: UUID) -> SimulationJob:
        """
        Get a simulation job by ID (with ownership verification).
        
        Args:
            user_id: Requesting user ID
            job_id: Simulation job ID
            
        Returns:
            SimulationJob instance
            
        Raises:
            SimulationNotFoundError: If job doesn't exist or user doesn't own it
        """
        job = self.db.query(SimulationJob).filter(
            SimulationJob.id == job_id,
            SimulationJob.user_id == user_id
        ).first()
        
        if not job:
            raise SimulationNotFoundError(job_id)
        
        return job

    def get_job_by_id(self, job_id: UUID) -> SimulationJob:
        """
        Get a simulation job by ID (without ownership check).
        
        Used internally by workers.
        
        Args:
            job_id: Simulation job ID
            
        Returns:
            SimulationJob instance
            
        Raises:
            SimulationNotFoundError: If job doesn't exist
        """
        job = self.db.query(SimulationJob).filter(
            SimulationJob.id == job_id
        ).first()
        
        if not job:
            raise SimulationNotFoundError(job_id)
        
        return job

    def list_jobs(
        self,
        user_id: UUID,
        status: Optional[SimulationStatus] = None,
        simulation_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SimulationJob]:
        """
        List simulation jobs for a user.
        
        Args:
            user_id: Owner user ID
            status: Optional status filter
            simulation_type: Optional simulation type filter
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of SimulationJob instances
        """
        query = self.db.query(SimulationJob).filter(
            SimulationJob.user_id == user_id
        )
        
        if status:
            query = query.filter(SimulationJob.status == status)
        
        if simulation_type:
            query = query.filter(SimulationJob.simulation_type == simulation_type)
        
        return query.order_by(SimulationJob.created_at.desc()).offset(offset).limit(limit).all()

    def get_job_parameters(self, job: SimulationJob) -> dict[str, Any]:
        """
        Get full parameters for a job, fetching from S3 if needed.
        
        Args:
            job: SimulationJob instance
            
        Returns:
            Parameters dictionary
        """
        if job.parameters_s3_key:
            return self.blob_storage.download_json(job.parameters_s3_key)
        return job.parameters

    def get_job_result(self, user_id: UUID, job_id: UUID) -> dict[str, Any]:
        """
        Get simulation result.
        
        Args:
            user_id: Requesting user ID
            job_id: Simulation job ID
            
        Returns:
            Result data dictionary
            
        Raises:
            SimulationNotFoundError: If job doesn't exist or user doesn't own it
        """
        job = self.get_job(user_id, job_id)
        
        if job.status != SimulationStatus.COMPLETED:
            return {
                "job_id": str(job.id),
                "status": job.status.value,
                "message": f"Simulation is {job.status.value.lower()}"
            }
        
        if not job.result_s3_key:
            raise ResultNotFoundError(job_id)
        
        result_data = self.blob_storage.download_json(job.result_s3_key)
        
        return {
            "job_id": str(job.id),
            "status": "COMPLETED",
            "result": result_data,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        }

    def update_job_status(
        self,
        job_id: UUID,
        status: SimulationStatus,
        progress: Optional[float] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> SimulationJob:
        """
        Update job status.
        
        Args:
            job_id: Simulation job ID
            status: New status
            progress: Optional progress value (0.0 to 1.0)
            error_code: Error code if failed
            error_message: Error message if failed
            
        Returns:
            Updated SimulationJob instance
        """
        job = self.get_job_by_id(job_id)
        
        job.status = status
        
        if progress is not None:
            job.progress = progress
        
        if status == SimulationStatus.RUNNING and not job.started_at:
            job.started_at = datetime.utcnow()
        
        if status in (SimulationStatus.COMPLETED, SimulationStatus.FAILED, SimulationStatus.CANCELLED):
            job.completed_at = datetime.utcnow()
        
        if error_code:
            job.error_code = error_code
        if error_message:
            job.error_message = error_message
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info(f"Updated job {job_id} status to {status.value}")
        return job

    def save_result(self, job_id: UUID, result: dict[str, Any]) -> SimulationJob:
        """
        Save simulation result to S3 and update job status.
        
        Args:
            job_id: Simulation job ID
            result: Result data to save
            
        Returns:
            Updated SimulationJob instance
        """
        job = self.get_job_by_id(job_id)
        
        s3_key = S3Storage.build_simulation_key(
            str(job.user_id), str(job_id), "result.json"
        )
        self.blob_storage.upload_json(s3_key, result)
        
        job.result_s3_key = s3_key
        job.result_size_bytes = self.blob_storage.get_object_size(s3_key)
        job.status = SimulationStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 1.0
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info(f"Saved result for job {job_id} to {s3_key}")
        return job

    def cancel_job(self, user_id: UUID, job_id: UUID) -> SimulationJob:
        """
        Cancel a pending or running job.
        
        Args:
            user_id: Requesting user ID
            job_id: Simulation job ID
            
        Returns:
            Updated SimulationJob instance
        """
        job = self.get_job(user_id, job_id)
        
        if job.status not in (SimulationStatus.PENDING, SimulationStatus.RUNNING):
            raise ValueError(f"Cannot cancel job with status {job.status.value}")
        
        job.status = SimulationStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info(f"Cancelled job {job_id}")
        return job

    def _enqueue_job(self, job_id: UUID) -> None:
        """
        Enqueue job for async processing.
        
        Args:
            job_id: Simulation job ID to enqueue
        """
        # Import here to avoid circular imports
        from app.workers.tasks import process_simulation
        process_simulation.delay(str(job_id))
        logger.info(f"Enqueued job {job_id} for processing")
