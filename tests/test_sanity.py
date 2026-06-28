from backend.v1.fallback_engine import fallback_determine_task
from backend.v1.engine import AgentState

def test_determine_task_handyman():
    """Sanity check: rule-based task determination works"""
    state = AgentState(
        messages=[{"role": "user", "content": "My dishwasher is broken"}],
        selected_task=None
    )
    result = fallback_determine_task(state)
    assert result.selected_task == "handyman_request"
    assert len(result.messages) > 1

def test_determine_task_quote():
    state = AgentState(
        messages=[{"role": "user", "content": "I need a quote for materials"}],
        selected_task=None
    )
    result = fallback_determine_task(state)
    assert result.selected_task == "quote_request"