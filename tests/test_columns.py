"""
Test HandymanDB column collection using the actual engine.process() from main.py.
Simulates user messages, tracks database inserts via LangSmith tracing.

Run in terminal with: python test_columns.py 
"""

import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load env (includes LANGSMITH_* vars)
load_dotenv()

from langsmith.schemas import Run, Example

import sys
sys.path.insert(0, '..')

from backend.v1 import engine
from backend.v1.engine import sessions
from backend.v1.models import AgentState

# --- Harness algorithm version    --- #
ALGORITHM_VERSION = os.getenv('ALGORITHM_VERSION', 'v1') # Get the active version or default to v1
if ALGORITHM_VERSION == 'v1':
    from backend.v1.engine import Engine
else:
    raise ValueError(f"Unknown version: {ALGORITHM_VERSION}")

engine = Engine()

# ─────────────────────────────────────────────────────────────────
# Evaluators
# ─────────────────────────────────────────────────────────────────

def eval_offer_details_complete(state: AgentState) -> dict:
    """Check if all offer_request columns collected by agent."""
    required_for_offer = ["category", "subcategory", "deadline", "prompt_text"]
    filled = all(state.collected_details.get(col) for col in required_for_offer)
    missing = [col for col in required_for_offer if not state.collected_details.get(col)]
    
    return {
        "key": "offer_details_complete",
        "score": 1.0 if filled else 0.0,
        "collected": state.collected_details,
        "missing": missing,
    }


def eval_client_info_complete(state: AgentState) -> dict:
    """Check if all client columns collected by agent."""
    required_for_client = ["name", "phone", "address"]
    filled = all(state.client_info.get(col) for col in required_for_client)
    missing = [col for col in required_for_client if not state.client_info.get(col)]
    
    return {
        "key": "client_info_complete",
        "score": 1.0 if filled else 0.0,
        "collected": state.client_info,
        "missing": missing,
    }


def eval_task_selected(state: AgentState) -> dict:
    """Check if task was selected."""
    return {
        "key": "task_selected",
        "score": 1.0 if state.selected_task else 0.0,
        "selected_task": state.selected_task,
    }


# ─────────────────────────────────────────────────────────────────
# Test conversation flow
# ─────────────────────────────────────────────────────────────────

def run_test_conversation():
    """
    Simulate a multi-turn conversation:
    1. User selects handyman task
    2. Agent collects job details (category, subcategory, deadline, job_description)
    3. Agent collects client info (name, phone, address)
    """
    
    session_id = "test_session_001"
    client_ip = "127.0.0.1"
    
    # Initialize session
    sessions[session_id] = AgentState(messages=[], ip_address=client_ip)
    state = sessions[session_id]
    
    print("=" * 70)
    print("HANDYMAN AGENT TEST - Column Collection via engine.process()")
    print("=" * 70)
    
    # Test messages (simulating user input)
    test_messages = [
        "Hi, I need help with a handyman job",
        "Plumbing",  # Task selection
        "Leak detection",  # Sub-category
        "There's water dripping from under the sink in my kitchen bathroom",  # Job description
        "2 weeks from today",  # Deadline
        "John Doe",  # Name
        "555-0123",  # Phone
        "123 Oak Street, Vienna, Austria",  # Address
    ]
    
    # Process each message through engine
    for turn, user_message in enumerate(test_messages, 1):
        print(f"\n--- Turn {turn} ---")
        print(f"[USER] {user_message}")
        
        # Add user message to state
        state.messages.append({"role": "user", "content": user_message})
        
        # Process through actual engine
        state = engine.process(state)
        sessions[session_id] = state
        
        # Print agent response
        if state.messages:
            last_msg = state.messages[-1]
            if isinstance(last_msg, dict):
                agent_reply = last_msg.get('content', '(no reply)')
            else:
                agent_reply = str(last_msg)
            print(f"[AGENT] {agent_reply[:200]}...")  # First 200 chars
        
        # Print current state
        if state.selected_task:
            print(f"  → Task: {state.selected_task}")
        if state.collected_details:
            print(f"  → Collected details: {state.collected_details}")
        if state.client_info:
            print(f"  → Client info: {state.client_info}")
    
    return state


# ─────────────────────────────────────────────────────────────────
# Run and evaluate
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run the conversation
    final_state = run_test_conversation()
    
    # Evaluate results
    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    
    evals = {
        "task_selected": eval_task_selected,
        "offer_details": eval_offer_details_complete,
        "client_info": eval_client_info_complete,
    }
    
    results = {}
    for name, eval_fn in evals.items():
        result = eval_fn(final_state)
        status = "✓ PASS" if result["score"] == 1.0 else "✗ FAIL"
        print(f"\n{status} | {result['key']}")
        print(f"   Score: {result['score']}")
        
        # Print details
        for key, val in result.items():
            if key not in ["key", "score"]:
                print(f"   {key}: {val}")
        
        results[name] = result
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total_score = sum(r["score"] for r in results.values()) / len(results)
    print(f"Overall score: {total_score:.1%}")
    print(f"Session ID: test_session_001")
    print("\nCheck LangSmith UI for full trace:")
    print(f"  https://smith.langchain.com/projects/HandymanTenderMaker")