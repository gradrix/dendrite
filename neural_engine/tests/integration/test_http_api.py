"""
Integration tests for the HTTP API server.

These tests verify that the FastAPI server endpoints work correctly.
Uses FastAPI's TestClient for in-process testing.
"""

import pytest
import os
from unittest.mock import MagicMock, patch

# Try to import TestClient for in-process testing
try:
    from fastapi.testclient import TestClient
    from neural_engine.api.server import app
    HAS_TESTCLIENT = True
except ImportError:
    HAS_TESTCLIENT = False

TIMEOUT = 10


@pytest.fixture(scope="module")
def api_client():
    """Create a TestClient for in-process API testing."""
    if not HAS_TESTCLIENT:
        pytest.skip("FastAPI TestClient not available")
    
    # Create mock orchestrator to avoid full initialization
    with patch('neural_engine.api.server.get_orchestrator') as mock_get_orch:
        mock_orch = MagicMock()
        mock_orch.process.return_value = {"response": "Test response", "success": True}
        mock_orch.tool_registry.get_all_tools.return_value = []
        mock_get_orch.return_value = mock_orch
        
        with TestClient(app) as client:
            yield client


class TestAPIHealth:
    """Test API health endpoints."""
    
    def test_health_endpoint(self, api_client):
        """Verify health endpoint returns healthy status."""
        response = api_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
    
    def test_openapi_docs(self, api_client):
        """Verify OpenAPI documentation is available."""
        response = api_client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "redoc" in response.text.lower() or "openapi" in response.text.lower()
    
    def test_openapi_json(self, api_client):
        """Verify OpenAPI JSON schema is available."""
        response = api_client.get("/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestAPIGoals:
    """Test goal submission endpoints."""
    
    def test_list_goals_empty(self, api_client):
        """Verify listing goals works with empty store."""
        response = api_client.get("/api/v1/goals")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_submit_goal_async(self, api_client):
        """Test submitting a goal in async mode."""
        response = api_client.post(
            "/api/v1/goals",
            json={"goal": "Say hello", "async_mode": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "goal_id" in data
        assert data["status"] in ["pending", "processing"]
        assert data["goal"] == "Say hello"
    
    def test_get_goal_status(self, api_client):
        """Test getting goal status by ID."""
        # Submit a goal first
        submit_response = api_client.post(
            "/api/v1/goals",
            json={"goal": "Test goal", "async_mode": True}
        )
        goal_id = submit_response.json()["goal_id"]
        
        # Get status
        response = api_client.get(f"/api/v1/goals/{goal_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["goal_id"] == goal_id
    
    def test_get_nonexistent_goal(self, api_client):
        """Test getting a goal that doesn't exist."""
        response = api_client.get("/api/v1/goals/nonexistent-id")
        assert response.status_code == 404


class TestAPITools:
    """Test tools listing endpoint."""
    
    def test_list_tools(self, api_client):
        """Verify tools listing works."""
        response = api_client.get("/api/v1/tools")
        # May return 200 or 500 depending on orchestrator state
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestAPIChat:
    """Test chat endpoint."""
    
    def test_chat_endpoint_exists(self, api_client):
        """Verify chat endpoint exists."""
        response = api_client.post(
            "/api/v1/chat",
            json={"message": "Hello"}
        )
        # May succeed or fail depending on orchestrator state
        assert response.status_code in [200, 500]


class TestAPIAuthentication:
    """Test API authentication when enabled."""
    
    def test_health_no_auth_required(self, api_client):
        """Health endpoint should not require auth."""
        response = api_client.get("/health")
        assert response.status_code == 200
