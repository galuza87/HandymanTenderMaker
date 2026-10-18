import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.models import AgentState, ChatRequest, ChatResponse
from backend.bootstrap import (
    create_app,
    load_state_for_session,
    format_chat_response,
)


@pytest.fixture
def mock_engine():
    """Create a mock engine with both process and aprocess capabilities."""
    engine = MagicMock()
    
    async def mock_aprocess(state: AgentState) -> AgentState:
        # Simulate slight network delay
        await asyncio.sleep(0.01)
        state_copy = state.model_copy(deep=True)
        state_copy.messages.append({
            "role": "assistant",
            "content": "Hello! I can help you with your plumbing repair."
        })
        state_copy.identified_categories = [{"category_id": 1, "name": "Plumbing"}]
        state_copy.prompts = [{"id": 1, "category_id": 1, "prompt_text": "Fix sink"}]
        state_copy.collected_details = {"room": "kitchen"}
        state_copy.is_finished = False
        return state_copy

    engine.aprocess = AsyncMock(side_effect=mock_aprocess)
    engine.process = MagicMock(side_effect=lambda s: asyncio.run(mock_aprocess(s)))
    return engine


def test_load_state_for_session_new():
    """Test loading state when no prior session exists in DB."""
    with patch("backend.bootstrap.get_conversation", return_value=None), \
         patch("backend.bootstrap.get_client_by_id", return_value={"name": "Alice", "last_name": "Smith", "phone": "050-1111111", "address": "1 Main St"}):
        state = load_state_for_session("new-session-123", "127.0.0.1", user_id=42)
        assert state.session_id == "new-session-123"
        assert state.ip_address == "127.0.0.1"
        assert state.user_id == 42
        assert state.client_info["name"] == "Alice Smith"
        assert state.client_info["phone"] == "050-1111111"
        assert state.messages == []


def test_load_state_for_session_existing():
    """Test loading state when prior session exists in DB."""
    saved_state = {
        "session_id": "existing-session",
        "messages": [{"role": "user", "content": "Initial message"}],
        "user_id": 10,
        "client_info": {"name": "Bob", "phone": "052-2222222", "address": "2 Oak St"},
        "CategorizerDecision": None,
    }
    with patch("backend.bootstrap.get_conversation", return_value=saved_state):
        state = load_state_for_session("existing-session", "10.0.0.1", user_id=None)
        assert state.session_id == "existing-session"
        assert len(state.messages) == 1
        assert state.client_info["name"] == "Bob"


def test_format_chat_response():
    """Test extracting new assistant messages and response metadata."""
    state = AgentState(
        messages=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Assistant reply 1"},
            {"role": "assistant", "content": "Assistant reply 2"}
        ],
        identified_categories=[{"category_id": 1, "name": "Plumbing"}],
        prompts=[{"id": 1, "prompt_text": "Fix leak"}],
        collected_details={"key": "val"}
    )
    # old_msg_count is 1 (only the user message was in old state)
    resp = format_chat_response(state, old_msg_count=1)
    assert isinstance(resp, ChatResponse)
    assert resp.reply == "Assistant reply 1\n\nAssistant reply 2"
    assert len(resp.identified_categories) == 1
    assert len(resp.prompts) == 1
    assert resp.collected_details == {"key": "val"}


def test_chat_endpoint_concurrent_execution(mock_engine):
    """Test /chat endpoint runs aprocess and ensures both incoming and final states are saved."""
    save_calls = []

    def mock_save_conversation(session_id, client_id, state_json, is_finished):
        save_calls.append({
            "session_id": session_id,
            "client_id": client_id,
            "state_json": state_json,
            "is_finished": is_finished
        })

    with patch("backend.bootstrap.get_conversation", return_value=None), \
         patch("backend.bootstrap.get_client_by_id", return_value=None), \
         patch("backend.bootstrap.save_conversation", side_effect=mock_save_conversation), \
         patch("backend.bootstrap.Engine", return_value=mock_engine):
        
        app = create_app()
        client = TestClient(app)

        payload = {
            "session_id": "test-async-sess",
            "message": "I have a plumbing issue in my bathroom",
            "user_id": 5
        }

        response = client.post("/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "plumbing" in data["reply"].lower()
        assert len(data["identified_categories"]) == 1
        assert mock_engine.aprocess.await_count == 1

        # Verify save_conversation was called twice:
        # 1. Incoming user state
        # 2. Final state with assistant reply
        assert len(save_calls) == 2
        assert "plumbing issue in my bathroom" in save_calls[0]["state_json"]
        assert "Hello! I can help you" in save_calls[1]["state_json"]
        assert save_calls[0]["is_finished"] is False
