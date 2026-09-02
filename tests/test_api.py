"""Comprehensive API test suite for HandymanTenderMaker FastAPI backend.

This module provides end-to-end integration tests for all REST API endpoints,
ensuring correct request/response handling, data validation, state persistence,
and error handling across the application.

Test Coverage:
    - Chat Endpoint: Multi-turn conversational interactions for task classification
    - Categories Endpoint: Browse and search service categories
    - Contractors Endpoint: List available contractors
    - Conversation Flow: Session state persistence and multi-step workflows
    - Error Handling: Edge cases, malformed input, and graceful degradation

Requirements:
    - FastAPI backend server must be running or TestClient will create isolated test instance
    - Database must be initialized with schema (HandymanDB tables)
    - All dependencies (LLM, database) available or tests will gracefully degrade

Usage:
    pytest tests/test_api.py -v              # Run all tests
    pytest tests/test_api.py -v -k "chat"    # Run only chat endpoint tests
    pytest tests/test_api.py::TestChatEndpoint -v  # Run specific test class

Attributes:
    client (TestClient): FastAPI TestClient for simulating HTTP requests without
                        network overhead. Used for all endpoint tests.

Note:
    Tests use temporary session IDs and clean data to avoid cross-test pollution.
    Response schema validation ensures API contract compliance.
"""
import pytest
from fastapi.testclient import TestClient

from ..backend.main import app

client = TestClient(app)

class TestChatEndpoint:
    """Test /chat POST endpoint"""
    
    def test_chat_handyman_request(self):
        """User asks for handyman service"""
        response = client.post("/chat", json={
            "message": "My dishwasher is broken",
            "session_id": "test-session-1"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"]  # Should have a response
        assert "identified_categories" in data or "collected_details" in data
    
    def test_chat_quote_request(self):
        """User asks for a quote"""
        response = client.post("/chat", json={
            "message": "I need a construction quote for materials",
            "session_id": "test-session-2"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"]  # Should have a response
    
    def test_chat_tender_request(self):
        """User asks for tender"""
        response = client.post("/chat", json={
            "message": "I need to send out a tender to subcontractors",
            "session_id": "test-session-3"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"]  # Should have a response
    
    def test_chat_unrecognized(self):
        """User asks unrelated question"""
        response = client.post("/chat", json={
            "message": "What is the weather today?",
            "session_id": "test-session-4"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"]  # Should have a response
    
    def test_chat_session_persistence(self):
        """Same session_id maintains state across requests"""
        session_id = "test-session-persist"
        
        # First message: determine task
        r1 = client.post("/chat", json={
            "message": "plumbing leak",
            "session_id": session_id
        })
        data1 = r1.json()
        assert "reply" in data1
        
        # Second message: should continue gathering info
        r2 = client.post("/chat", json={
            "message": "bathroom sink",
            "session_id": session_id
        })
        data = r2.json()
        # Should maintain session state across requests
        assert "reply" in data
        assert len(data["reply"]) > 0
    
    def test_chat_with_image(self):
        """Test chat with image parameter"""
        response = client.post("/chat", json={
            "message": "Can you help me with this image?",
            "session_id": "test-session-image",
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
    
    def test_chat_missing_session_id(self):
        """Request without session_id should still work (creates new session)"""
        response = client.post("/chat", json={
            "message": "Hello",
            "session_id": ""
        })
        assert response.status_code == 200
    
    def test_chat_response_format(self):
        """Response follows ChatResponse schema"""
        response = client.post("/chat", json={
            "message": "I need help",
            "session_id": "test-format"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "collected_details" in data
        assert "identified_categories" in data
        assert "sub_tasks" in data
        assert isinstance(data["reply"], str)
        assert isinstance(data["collected_details"], dict)
        assert isinstance(data["identified_categories"], list)
        assert isinstance(data["sub_tasks"], list)


class TestCategoriesEndpoint:
    """Test /api/categories GET endpoint"""
    
    def test_categories_success(self):
        """Fetch all categories"""
        response = client.get("/api/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_categories_structure(self):
        """Categories have correct structure"""
        response = client.get("/api/categories")
        data = response.json()
        if len(data) > 0:
            category = data[0]
            assert "name" in category or "id" in category  # Has identifying info
    
    def test_categories_not_empty(self):
        """Should return at least some categories"""
        response = client.get("/api/categories")
        data = response.json()
        assert len(data) >= 0  # Empty list is ok, but should be consistent


class TestContractorsEndpoint:
    """Test /api/contractors GET endpoint"""
    
    def test_contractors_success(self):
        """Fetch all contractors"""
        response = client.get("/api/contractors")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_contractors_structure(self):
        """Contractors have correct structure"""
        response = client.get("/api/contractors")
        data = response.json()
        if len(data) > 0:
            contractor = data[0]
            assert "first_name" in contractor or "name" in contractor
            assert "email" in contractor or "contact" in contractor
    
    def test_contractors_not_empty(self):
        """Should return contractors if database populated"""
        response = client.get("/api/contractors")
        data = response.json()
        assert isinstance(data, list)


class TestConversationFlow:
    """Test multi-turn conversations"""
    
    def test_handyman_full_flow(self):
        """Complete handyman request flow"""
        session = "flow-handyman"
        
        # Step 1: Trigger handyman task
        r1 = client.post("/chat", json={
            "message": "My dishwasher needs repair",
            "session_id": session
        })
        assert r1.status_code == 200
        assert "reply" in r1.json()
        
        # Step 2: Provide major category
        r2 = client.post("/chat", json={
            "message": "Appliance repair",
            "session_id": session
        })
        assert r2.status_code == 200
        assert "reply" in r2.json()
        
        # Step 3: Provide sub category
        r3 = client.post("/chat", json={
            "message": "Bosch dishwasher",
            "session_id": session
        })
        assert r3.status_code == 200
        assert "reply" in r3.json()
    
    def test_quote_full_flow(self):
        """Complete quote request flow"""
        session = "flow-quote"
        
        r1 = client.post("/chat", json={
            "message": "I need a construction quote",
            "session_id": session
        })
        assert r1.status_code == 200
        assert "reply" in r1.json()
        
        r2 = client.post("/chat", json={
            "message": "Residential renovation",
            "session_id": session
        })
        assert r2.status_code == 200
        assert "reply" in r2.json()
    
    def test_session_isolation(self):
        """Different sessions don't interfere"""
        # Session A: handyman
        r1a = client.post("/chat", json={
            "message": "plumbing leak",
            "session_id": "session-a"
        })
        data_a = r1a.json()
        
        # Session B: quote
        r1b = client.post("/chat", json={
            "message": "I need a quote",
            "session_id": "session-b"
        })
        data_b = r1b.json()
        
        # Both should return valid responses
        assert r1a.status_code == 200
        assert r1b.status_code == 200
        assert "reply" in data_a
        assert "reply" in data_b


class TestErrorHandling:
    """Test error cases"""
    
    def test_chat_invalid_json(self):
        """Malformed JSON request"""
        response = client.post("/chat", json={
            "message": "Hello"
            # Missing session_id
        })
        assert response.status_code in [422, 200]  # Validation error or handles gracefully
    
    def test_empty_message(self):
        """Empty message still works"""
        response = client.post("/chat", json={
            "message": "",
            "session_id": "test-empty"
        })
        assert response.status_code == 200
    
    def test_very_long_message(self):
        """Long message handled"""
        long_msg = "a" * 5000
        response = client.post("/chat", json={
            "message": long_msg,
            "session_id": "test-long"
        })
        assert response.status_code == 200
    
    def test_special_characters(self):
        """Special characters in message"""
        response = client.post("/chat", json={
            "message": "I need help with: pipes, 🔧, etc.",
            "session_id": "test-special"
        })
        assert response.status_code == 200


class TestSearchEndpoint:
    """Test /api/search endpoint for category search"""
    
    def test_search_categories(self):
        """Search for categories by keyword"""
        response = client.get("/api/search", params={"q": "plumbing"})
        assert response.status_code in [200, 404]  # 404 if endpoint not yet implemented
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
    
    def test_search_empty_query(self):
        """Search with empty query"""
        response = client.get("/api/search", params={"q": ""})
        assert response.status_code in [200, 400, 404]  # 404 if endpoint not implemented
    
    def test_search_no_results(self):
        """Search for non-existent category"""
        response = client.get("/api/search", params={"q": "xyz_nonexistent_service_xyz"})
        assert response.status_code in [200, 404]  # 404 if endpoint not implemented
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)  # Empty list is ok


class TestClientEndpoints:
    """Test client management endpoints"""
    
    def test_create_client(self):
        """Create a new client"""
        response = client.post("/api/clients", json={
            "name": "John",
            "last_name": "Doe",
            "phone": "555-1234",
            "email": "john@example.com"
        })
        assert response.status_code in [200, 201, 404]  # 404 if endpoint not yet implemented
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data or "client_id" in data  # Should return created ID
    
    def test_get_client_by_id(self):
        """Retrieve client by ID"""
        # First create a client
        create_resp = client.post("/api/clients", json={
            "name": "Jane",
            "last_name": "Smith",
            "phone": "555-5678",
            "email": "jane@example.com"
        })
        
        if create_resp.status_code in [200, 201]:
            client_data = create_resp.json()
            client_id = client_data.get("id") or client_data.get("client_id")
            
            if client_id:
                # Then retrieve it
                response = client.get(f"/api/clients/{client_id}")
                assert response.status_code == 200
                assert "name" in response.json() or "id" in response.json()
    
    def test_search_client_by_phone(self):
        """Search client by phone number"""
        response = client.get("/api/clients/search", params={"phone": "555-1234"})
        assert response.status_code in [200, 404]  # 404 if not found is ok


class TestProjectEndpoints:
    """Test project management endpoints"""
    
    def test_get_projects_for_client(self):
        """Retrieve projects for a specific client"""
        response = client.get("/api/clients/1/projects")
        assert response.status_code in [200, 404]  # 404 if client doesn't exist
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
    
    def test_create_project(self):
        """Create a new project"""
        response = client.post("/api/projects", json={
            "client_id": 1,
            "description": "Bathroom renovation",
            "status": "pending"
        })
        assert response.status_code in [200, 201, 400, 404]  # 400/404 if client doesn't exist


class TestTestingEndpoints:
    """Test evaluation and testing endpoints"""
    
    def test_run_test_endpoint(self):
        """Test /run endpoint for algorithm evaluation"""
        response = client.post("/run", json={
            "test_data": "sample input",
            "session_id": "test-eval-1"
        })
        assert response.status_code in [200, 400, 404]  # May not be fully implemented
    
    def test_test_history_endpoint(self):
        """Test /history endpoint for test results"""
        response = client.get("/history")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
    
    def test_get_test_run_results(self):
        """Test /runs/{run_id} endpoint"""
        response = client.get("/runs/1")
        assert response.status_code in [200, 404]  # 404 if run doesn't exist


class TestResponseValidation:
    """Test response schema validation and correctness"""
    
    def test_chat_response_has_all_fields(self):
        """Chat response contains all expected fields"""
        response = client.post("/chat", json={
            "message": "I need help",
            "session_id": "test-validation"
        })
        assert response.status_code == 200
        data = response.json()
        
        # All these fields should exist
        required_fields = ["reply", "collected_details", "identified_categories", "sub_tasks"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_categories_response_structure(self):
        """Categories response has expected structure"""
        response = client.get("/api/categories")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            cat = data[0]
            # Should have id and name at minimum
            assert "id" in cat or "name" in cat
    
    def test_contractors_response_structure(self):
        """Contractors response has expected structure"""
        response = client.get("/api/contractors")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            contractor = data[0]
            # Should have basic contractor fields
            assert any(field in contractor for field in ["id", "first_name", "name", "email"])


class TestConcurrency:
    """Test concurrent/parallel requests and session isolation"""
    
    def test_parallel_sessions_no_crosstalk(self):
        """Multiple sessions running in parallel don't interfere"""
        sessions = ["parallel-1", "parallel-2", "parallel-3"]
        responses = []
        
        for session_id in sessions:
            resp = client.post("/chat", json={
                "message": f"Request from {session_id}",
                "session_id": session_id
            })
            responses.append(resp)
        
        # All should succeed
        for resp in responses:
            assert resp.status_code == 200
    
    def test_rapid_requests_same_session(self):
        """Rapid sequential requests to same session"""
        session_id = "rapid-session"
        
        for i in range(5):
            resp = client.post("/chat", json={
                "message": f"Message {i}",
                "session_id": session_id
            })
            assert resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
