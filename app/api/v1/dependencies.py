"""API dependencies for dependency injection."""

from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.storage.blob_storage import S3Storage, BlobStorage
from app.services.simulation_service import SimulationService
from app.services.report_service import ReportService
from app.services.user_service import UserService
from app.services.exceptions import AuthenticationError
from app.models.user import User

# Security scheme for JWT
security = HTTPBearer()


def get_blob_storage() -> BlobStorage:
    """Get blob storage client."""
    return S3Storage()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Get user service instance."""
    return UserService(db)


def get_simulation_service(
    db: Session = Depends(get_db),
    blob_storage: BlobStorage = Depends(get_blob_storage),
) -> SimulationService:
    """Get simulation service instance."""
    return SimulationService(db, blob_storage)


def get_report_service(
    db: Session = Depends(get_db),
    blob_storage: BlobStorage = Depends(get_blob_storage),
) -> ReportService:
    """Get report service instance."""
    return ReportService(db, blob_storage)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        user_service: User service instance
        
    Returns:
        Current User instance
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        payload = user_service.verify_token(token)
        
        if not payload.sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = user_service.get_user_by_id(UUID(payload.sub))
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e.message),
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(current_user: User = Depends(get_current_user)) -> UUID:
    """Get the current user's ID."""
    return current_user.id
