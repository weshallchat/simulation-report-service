"""User service for authentication and user management."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import bcrypt
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, TokenPayload
from app.services.exceptions import (
    UserNotFoundError,
    AuthenticationError,
)

logger = logging.getLogger(__name__)

# JWT settings
ALGORITHM = "HS256"


class UserService:
    """Service for user management and authentication."""

    def __init__(self, db: Session):
        """
        Initialize the user service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_user(self, data: UserCreate) -> User:
        """
        Create a new user.
        
        Args:
            data: User creation data
            
        Returns:
            Created User instance
        """
        hashed_password = self._hash_password(data.password)
        
        user = User(
            email=data.email,
            hashed_password=hashed_password,
            full_name=data.full_name,
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        logger.info(f"Created user {user.id} with email {user.email}")
        return user

    def get_user_by_id(self, user_id: UUID) -> User:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User instance
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise UserNotFoundError(user_id)
        
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: User email
            
        Returns:
            User instance or None
        """
        return self.db.query(User).filter(User.email == email).first()

    def authenticate_user(self, email: str, password: str) -> User:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Authenticated User instance
            
        Raises:
            AuthenticationError: If credentials are invalid
        """
        user = self.get_user_by_email(email)
        
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        if not self._verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
        
        return user

    def create_access_token(self, user_id: UUID) -> str:
        """
        Create a JWT access token for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            JWT token string
        """
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": str(user_id),
            "exp": expire,
        }
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> TokenPayload:
        """
        Verify a JWT token and extract payload.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenPayload with user ID
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            return TokenPayload(sub=payload.get("sub"), exp=payload.get("exp"))
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        # Encode to bytes and hash
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
