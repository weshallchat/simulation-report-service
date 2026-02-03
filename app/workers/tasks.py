"""Celery tasks for async job processing."""

import logging
import time
from uuid import UUID

from celery import shared_task

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.storage.blob_storage import S3Storage
from app.services.simulation_service import SimulationService
from app.services.report_service import ReportService
from app.models.simulation import SimulationStatus
from app.models.report import ReportStatus
from app.handlers.registry import SimulationHandlerRegistry, ReportHandlerRegistry

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def process_simulation(self, job_id: str) -> dict:
    """
    Process a simulation job.
    
    This task is simulation-agnostic. It delegates the actual simulation
    execution to registered handlers based on the simulation_type.
    
    Args:
        job_id: Simulation job ID as string
        
    Returns:
        Result metadata
    """
    logger.info(f"Processing simulation job {job_id}")
    
    db = SessionLocal()
    blob_storage = S3Storage()
    service = SimulationService(db, blob_storage)
    
    try:
        job_uuid = UUID(job_id)
        
        # Update status to RUNNING
        service.update_job_status(job_uuid, SimulationStatus.RUNNING)
        
        # Get the job and its parameters
        job = service.get_job_by_id(job_uuid)
        parameters = service.get_job_parameters(job)
        job_metadata = job.job_metadata
        
        # Get the appropriate handler for this simulation type
        handler = SimulationHandlerRegistry.get_handler(job.simulation_type)
        
        if handler:
            # Execute the simulation via the handler
            logger.info(f"Executing simulation {job_id} with handler for {job.simulation_type}")
            result = handler.execute(
                job_id=str(job.id),
                simulation_type=job.simulation_type,
                parameters=parameters,
                progress_callback=lambda p: service.update_job_status(job_uuid, SimulationStatus.RUNNING, progress=p)
            )
        else:
            # No handler registered - use default placeholder behavior
            # In production, you would either:
            # 1. Require handlers for all simulation types
            # 2. Call an external simulation service
            logger.warning(f"No handler registered for simulation type: {job.simulation_type}")
            result = _default_simulation_handler(job.simulation_type, parameters)
        
        # Save the result
        service.save_result(job_uuid, result)
        
        logger.info(f"Simulation job {job_id} completed successfully")
        return {"status": "completed", "job_id": job_id}
        
    except Exception as e:
        logger.error(f"Simulation job {job_id} failed: {str(e)}")
        
        # Update job status to FAILED
        service.update_job_status(
            UUID(job_id),
            SimulationStatus.FAILED,
            error_code="SIMULATION_ERROR",
            error_message=str(e)
        )
        
        raise
        
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def generate_report(self, report_id: str) -> dict:
    """
    Generate a report.
    
    This task is report-agnostic. It delegates the actual report
    generation to registered handlers based on the report_type.
    
    Args:
        report_id: Report ID as string
        
    Returns:
        Result metadata
    """
    logger.info(f"Generating report {report_id}")
    
    db = SessionLocal()
    blob_storage = S3Storage()
    report_service = ReportService(db, blob_storage)
    simulation_service = SimulationService(db, blob_storage)
    
    try:
        report_uuid = UUID(report_id)
        
        # Update status to GENERATING
        report_service.update_report_status(report_uuid, ReportStatus.GENERATING)
        
        # Get the report
        report = report_service.get_report_by_id(report_uuid)
        
        # Gather all simulation results
        simulation_results = []
        for sim_id in report.simulation_job_ids:
            result = simulation_service.get_job_result(report.user_id, sim_id)
            simulation_results.append(result)
        
        # Get the appropriate handler for this report type
        handler = ReportHandlerRegistry.get_handler(report.report_type)
        
        if handler:
            # Generate the report via the handler
            logger.info(f"Generating report {report_id} with handler for {report.report_type}")
            file_content, content_type, filename = handler.generate(
                report_id=str(report.id),
                report_type=report.report_type,
                output_format=report.output_format,
                parameters=report.parameters,
                simulation_results=simulation_results,
            )
        else:
            # No handler registered - use default placeholder behavior
            logger.warning(f"No handler registered for report type: {report.report_type}")
            file_content, content_type, filename = _default_report_handler(
                report.report_type,
                report.output_format,
                report.parameters,
                simulation_results,
            )
        
        # Save the report file
        report_service.save_report_file(
            report_uuid,
            file_content,
            content_type,
            filename,
        )
        
        logger.info(f"Report {report_id} generated successfully")
        return {"status": "completed", "report_id": report_id}
        
    except Exception as e:
        logger.error(f"Report {report_id} generation failed: {str(e)}")
        
        # Update report status to FAILED
        report_service.update_report_status(
            UUID(report_id),
            ReportStatus.FAILED,
            error_code="REPORT_ERROR",
            error_message=str(e)
        )
        
        raise
        
    finally:
        db.close()


def _default_simulation_handler(simulation_type: str, parameters: dict) -> dict:
    """
    Default simulation handler for when no specific handler is registered.
    
    This is a placeholder that simulates work and returns dummy results.
    In production, either register proper handlers or integrate with
    external simulation services.
    """
    logger.info(f"Running default simulation handler for type: {simulation_type}")
    
    # Simulate some processing time
    time.sleep(2)
    
    return {
        "simulation_type": simulation_type,
        "input_parameters": parameters,
        "output": {
            "message": "Simulation completed (default handler)",
            "note": "Register a handler for this simulation type to get real results",
        },
        "metrics": {
            "processing_time_seconds": 2,
        }
    }


def _default_report_handler(
    report_type: str,
    output_format: str,
    parameters: dict,
    simulation_results: list,
) -> tuple[bytes, str, str]:
    """
    Default report handler for when no specific handler is registered.
    
    This is a placeholder that generates a simple JSON report.
    In production, either register proper handlers or integrate with
    external report generation services.
    """
    import json
    
    logger.info(f"Running default report handler for type: {report_type}")
    
    report_data = {
        "report_type": report_type,
        "output_format": output_format,
        "parameters": parameters,
        "simulation_results": simulation_results,
        "note": "Register a handler for this report type to get formatted reports",
    }
    
    # For the default handler, always output JSON regardless of requested format
    file_content = json.dumps(report_data, indent=2, default=str).encode("utf-8")
    content_type = "application/json"
    filename = f"report.json"
    
    return file_content, content_type, filename
