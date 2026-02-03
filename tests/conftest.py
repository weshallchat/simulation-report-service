"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.api.v1.dependencies import get_blob_storage
from app.storage.blob_storage import BlobStorage


# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MockBlobStorage(BlobStorage):
    """Mock blob storage for testing."""

    def __init__(self):
        self._storage = {}

    def upload_json(self, key: str, data: dict) -> str:
        import json
        self._storage[key] = json.dumps(data).encode()
        return key

    def download_json(self, key: str) -> dict:
        import json
        return json.loads(self._storage[key].decode())

    def upload_file(self, key: str, file_obj, content_type: str) -> str:
        self._storage[key] = file_obj.read()
        return key

    def download_file(self, key: str) -> bytes:
        return self._storage[key]

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"http://mock-storage/{key}?expires={expires_in}"

    def delete(self, key: str) -> bool:
        if key in self._storage:
            del self._storage[key]
            return True
        return False

    def get_object_size(self, key: str) -> int:
        return len(self._storage.get(key, b""))

    def exists(self, key: str) -> bool:
        return key in self._storage


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def mock_blob_storage():
    """Create a mock blob storage for testing."""
    return MockBlobStorage()


@pytest.fixture(scope="function")
def client(db_session, mock_blob_storage):
    """Create a test client with overridden dependencies."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_blob_storage():
        return mock_blob_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_blob_storage] = override_get_blob_storage

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(client):
    """Create a test user and return credentials."""
    user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201

    # Login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": user_data["email"], "password": user_data["password"]}
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"user_data": user_data, "token": token}


@pytest.fixture
def auth_headers(test_user):
    """Return authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {test_user['token']}"}
