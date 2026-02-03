"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.dependencies import get_user_service, get_current_user
from app.services.user_service import UserService
from app.services.exceptions import AuthenticationError
from app.schemas.user import UserCreate, UserResponse, Token
from app.models.user import User

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
)
def register_user(
    data: UserCreate,
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Register a new user."""
    # Check if user already exists
    existing_user = user_service.get_user_by_email(data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    return user_service.create_user(data)


@router.post(
    "/login",
    response_model=Token,
    summary="Login to get access token",
    description="Authenticate with email and password to receive a JWT access token.",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends(get_user_service),
) -> dict:
    """
    Login and get access token.
    
    Uses OAuth2 password flow - username field should contain email.
    """
    try:
        user = user_service.authenticate_user(form_data.username, form_data.password)
        access_token = user_service.create_access_token(user.id)
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the currently authenticated user's information.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user information."""
    return current_user
