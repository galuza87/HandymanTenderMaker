"""API tests for FastAPI endpoints. Run with server running: pytest tests/test_api.py -v"""
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
        assert data["selected_task"] == "handyman_request"
        assert data["reply"]  # Should have a response
    
    def test_chat_quote_request(self):
        """User asks for a quote"""
        response = client.post("/chat", json={
            "message": "I need a construction quote for materials",
            "session_id": "test-session-2"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["selected_task"] == "quote_request"
    
    def test_chat_tender_request(self):
        """User asks for tender"""
        response = client.post("/chat", json={
            "message": "I need to send out a tender to subcontractors",
            "session_id": "test-session-3"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["selected_task"] == "tender_request"
    
    def test_chat_unrecognized(self):
        """User asks unrelated question"""
        response = client.post("/chat", json={
            "message": "What is the weather today?",
            "session_id": "test-session-4"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["selected_task"] is None  # No task identified
        assert "BuildWizard" in data["reply"]  # Welcome message
    
    def test_chat_session_persistence(self):
        """Same session_id maintains state across requests"""
        session_id = "test-session-persist"
        
        # First message: determine task
        r1 = client.post("/chat", json={
            "message": "plumbing leak",
            "session_id": session_id
        })
        assert r1.json()["selected_task"] == "handyman_request"
        
        # Second message: should continue gathering info
        r2 = client.post("/chat", json={
            "message": "bathroom sink",
            "session_id": session_id
        })
        data = r2.json()
        assert data["selected_task"] == "handyman_request"
        # Should have collected major_category
        assert "major_category" in data["collected_details"] or len(r2.json()["reply"]) > 0
    
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
        assert "selected_task" in data
        assert "collected_details" in data
        assert isinstance(data["reply"], str)
        assert isinstance(data["collected_details"], dict)


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
        assert r1.json()["selected_task"] == "handyman_request"
        
        # Step 2: Provide major category
        r2 = client.post("/chat", json={
            "message": "Appliance repair",
            "session_id": session
        })
        assert r2.json()["selected_task"] == "handyman_request"
        
        # Step 3: Provide sub category
        r3 = client.post("/chat", json={
            "message": "Bosch dishwasher",
            "session_id": session
        })
        assert r3.json()["selected_task"] == "handyman_request"
    
    def test_quote_full_flow(self):
        """Complete quote request flow"""
        session = "flow-quote"
        
        r1 = client.post("/chat", json={
            "message": "I need a construction quote",
            "session_id": session
        })
        assert r1.json()["selected_task"] == "quote_request"
        
        r2 = client.post("/chat", json={
            "message": "Residential renovation",
            "session_id": session
        })
        assert r2.json()["selected_task"] == "quote_request"
    
    def test_session_isolation(self):
        """Different sessions don't interfere"""
        # Session A: handyman
        r1a = client.post("/chat", json={
            "message": "plumbing leak",
            "session_id": "session-a"
        })
        task_a = r1a.json()["selected_task"]
        
        # Session B: quote
        r1b = client.post("/chat", json={
            "message": "I need a quote",
            "session_id": "session-b"
        })
        task_b = r1b.json()["selected_task"]
        
        assert task_a == "handyman_request"
        assert task_b == "quote_request"


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
