"""API endpoint tests."""

import pytest


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuth:
    """Tests for authentication endpoints."""

    def test_register_user(self, client):
        """Test user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepass123",
                "full_name": "New User"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data

    def test_register_duplicate_email(self, client, test_user):
        """Test that duplicate email registration fails."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user["user_data"]["email"],
                "password": "anotherpass123",
                "full_name": "Another User"
            }
        )
        assert response.status_code == 409

    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user["user_data"]["email"],
                "password": test_user["user_data"]["password"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user["user_data"]["email"],
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401

    def test_get_current_user(self, client, auth_headers):
        """Test getting current user info."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"


class TestSimulations:
    """Tests for simulation endpoints."""

    def test_create_simulation(self, client, auth_headers):
        """Test creating a simulation job."""
        response = client.post(
            "/api/v1/simulations",
            headers=auth_headers,
            json={
                "simulation_type": "monte_carlo",
                "parameters": {"iterations": 1000, "seed": 42},
                "job_metadata": {"project": "test"}
            }
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "PENDING"

    def test_create_simulation_unauthorized(self, client):
        """Test that creating simulation without auth fails."""
        response = client.post(
            "/api/v1/simulations",
            json={
                "simulation_type": "monte_carlo",
                "parameters": {}
            }
        )
        assert response.status_code == 403

    def test_get_simulation_status(self, client, auth_headers):
        """Test getting simulation status."""
        # First create a simulation
        create_response = client.post(
            "/api/v1/simulations",
            headers=auth_headers,
            json={
                "simulation_type": "test_sim",
                "parameters": {"key": "value"}
            }
        )
        job_id = create_response.json()["job_id"]

        # Get status
        response = client.get(f"/api/v1/simulations/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["simulation_type"] == "test_sim"

    def test_get_simulation_not_found(self, client, auth_headers):
        """Test getting non-existent simulation."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/v1/simulations/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_list_simulations(self, client, auth_headers):
        """Test listing simulations."""
        # Create a few simulations
        for i in range(3):
            client.post(
                "/api/v1/simulations",
                headers=auth_headers,
                json={
                    "simulation_type": f"sim_type_{i}",
                    "parameters": {"index": i}
                }
            )

        # List simulations
        response = client.get("/api/v1/simulations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestReports:
    """Tests for report endpoints."""

    def test_create_report_no_completed_simulations(self, client, auth_headers):
        """Test that creating report with non-completed simulations fails."""
        # Create a simulation (will be PENDING)
        sim_response = client.post(
            "/api/v1/simulations",
            headers=auth_headers,
            json={
                "simulation_type": "test",
                "parameters": {}
            }
        )
        job_id = sim_response.json()["job_id"]

        # Try to create report - should fail because simulation is not completed
        response = client.post(
            "/api/v1/reports",
            headers=auth_headers,
            json={
                "simulation_job_ids": [job_id],
                "report_type": "summary",
                "output_format": "PDF"
            }
        )
        assert response.status_code == 400

    def test_get_report_not_found(self, client, auth_headers):
        """Test getting non-existent report."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/v1/reports/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_list_reports_empty(self, client, auth_headers):
        """Test listing reports when none exist."""
        response = client.get("/api/v1/reports", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
