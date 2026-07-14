from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import time

from backend.v1.engine import Engine
from backend.v1.models import AgentState
from backend.v1.db.database import insert_test_run, insert_test_result, get_test_runs, get_test_results_by_run

router = APIRouter()

class TestCase(BaseModel):
    id: Optional[int] = None
    input: str
    expected: str  # "single", "multiple", or "not able to identify"

class TestRunRequest(BaseModel):
    test_type: str
    cases: List[TestCase]

@router.post("/run")
def run_tests(request: TestRunRequest):
    if not request.cases:
        raise HTTPException(status_code=400, detail="No test cases provided")
        
    engine = Engine()
    results = []
    correct_count = 0
    total_time = 0.0
    
    # Run each test case
    for case in request.cases:
        start_time = time.time()
        
        # Setup state
        state = AgentState(messages=[{"role": "user", "content": case.input}])
        
        # Execute the LLM node we are testing
        if request.test_type == "contractor-intent":
            # Run through the new multi-agent orchestrator
            state = engine.process(state)
            
            # The new Categorizer agent responds conversationally instead of returning hardcoded JSON.
            # We use a simple heuristic to determine what it categorized for testing purposes.
            reply = state.messages[-1].get("content", "").lower()
            
            if "and" in reply or "multiple" in reply or len(state.identified_categories) > 1:
                actual = "multiple"
            elif any(trade in reply for trade in ["plumber", "electrician", "carpenter", "roofer", "handyman"]):
                actual = "single"
            else:
                actual = "not able to identify"
        else:
            raise HTTPException(status_code=400, detail="Unknown test type")
            
        end_time = time.time()
        exec_time_ms = (end_time - start_time) * 1000
        total_time += exec_time_ms
        
        is_correct = (actual == case.expected)
        if is_correct:
            correct_count += 1
            
        results.append({
            "input": case.input,
            "expected": case.expected,
            "actual": actual,
            "exec_time": exec_time_ms,
            "is_correct": is_correct
        })
        
    # Calculate aggregate metrics
    accuracy = (correct_count / len(request.cases)) * 100.0
    avg_time = total_time / len(request.cases)
    
    # Save to database
    run_id = insert_test_run(request.test_type, accuracy, avg_time)
    if run_id:
        for res in results:
            insert_test_result(
                run_id, 
                res["input"], 
                res["expected"], 
                res["actual"], 
                res["exec_time"], 
                res["is_correct"]
            )
            
    return {
        "run_id": run_id,
        "accuracy": accuracy,
        "avg_time_ms": avg_time,
        "results": results
    }

@router.get("/history")
def get_history():
    runs = get_test_runs()
    return runs

@router.get("/runs/{run_id}")
def get_run_details(run_id: int):
    results = get_test_results_by_run(run_id)
    if not results:
        raise HTTPException(status_code=404, detail="Test run not found or no results")
    return results
