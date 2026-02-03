"""Custom exceptions for the service layer."""

from uuid import UUID


class ServiceError(Exception):
    """Base exception for service layer errors."""

    def __init__(self, message: str, code: str = "SERVICE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(ServiceError):
    """Resource not found error."""

    def __init__(self, resource_type: str, resource_id: UUID):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            message=f"{resource_type} with ID {resource_id} not found",
            code=f"{resource_type.upper()}_NOT_FOUND"
        )


class SimulationNotFoundError(NotFoundError):
    """Simulation job not found error."""

    def __init__(self, job_id: UUID):
        super().__init__("Simulation", job_id)


class SimulationNotCompletedError(ServiceError):
    """Simulation not yet completed error."""

    def __init__(self, job_id: UUID):
        self.job_id = job_id
        super().__init__(
            message=f"Simulation {job_id} is not completed yet",
            code="SIMULATION_NOT_COMPLETED"
        )


class ResultNotFoundError(ServiceError):
    """Simulation result not available error."""

    def __init__(self, job_id: UUID):
        self.job_id = job_id
        super().__init__(
            message=f"Result for simulation {job_id} not found",
            code="RESULT_NOT_FOUND"
        )


class ReportNotFoundError(NotFoundError):
    """Report not found error."""

    def __init__(self, report_id: UUID):
        super().__init__("Report", report_id)


class UserNotFoundError(NotFoundError):
    """User not found error."""

    def __init__(self, user_id: UUID):
        super().__init__("User", user_id)


class AuthenticationError(ServiceError):
    """Authentication failed error."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code="AUTHENTICATION_FAILED")


class AuthorizationError(ServiceError):
    """Authorization failed error."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message=message, code="ACCESS_DENIED")
