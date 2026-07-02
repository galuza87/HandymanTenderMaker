import os
import sys

# Add parent directory of 'backend' to python path so internal imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import evaluate, Client
from backend.v1.engine import Engine, get_llm
from backend.v1.models import AgentState

# Ensure we have our environment variables loaded
from dotenv import load_dotenv
load_dotenv()

def run_nodes(inputs: dict) -> dict:
    """
    Target function to evaluate. It receives the dataset inputs, 
    runs our state machine, and returns the output state.
    """
    prompt = inputs["prompt"]
    state = AgentState(messages=[{"role": "user", "content": prompt}], session_id="test_session")
    
    llm = get_llm()
    engine = Engine(llm=llm)
    
    # Run Node 1: Determine number of subtasks
    state = engine.determine_number_of_subtasks(state)
    
    # Run Node 2: Determine task category (subtasks creation)
    if state.next_step == "determine_task_category":
        state = engine.determine_task_category(state)
        
    return {
        "identified_categories": state.identified_categories,
        "sub_tasks": state.sub_tasks
    }

# --- Evaluators ---
def one_handyman_evaluator(run, example) -> dict:
    """
    Asserts that Node 1 understood only ONE handyman/category is needed.
    """
    outputs = run.outputs
    if not outputs:
        return {"key": "one_handyman_identified", "score": 0}
        
    categories = outputs.get("identified_categories", [])
    
    # Score 1 if exactly 1 category was identified, else 0
    score = 1 if len(categories) == 1 else 0
    return {"key": "one_handyman_identified", "score": score}

def appliance_fixing_evaluator(run, example) -> dict:
    """
    Asserts that Node 2 (or Node 1 category name) relates to Appliance Fixing.
    """
    outputs = run.outputs
    if not outputs:
        return {"key": "appliance_fixing_identified", "score": 0}
        
    categories = outputs.get("identified_categories", [])
    if not categories:
        return {"key": "appliance_fixing_identified", "score": 0}
        
    # Check if the name includes appliance keywords
    cat_name = categories[0].get("name", "").lower()
    
    # You can customize these keywords based on your DB's actual category names
    is_appliance_fixing = "appliance" in cat_name or "dishwasher" in cat_name or "repair" in cat_name or "fixing" in cat_name
    
    return {"key": "appliance_fixing_identified", "score": 1 if is_appliance_fixing else 0}

def main():
    print("Initializing LangSmith Client...")
    client = Client()
    
    dataset_name = "Dishwasher_Test"
    
    # Create the dataset if it doesn't exist
    if not client.has_dataset(dataset_name=dataset_name):
        print(f"Creating dataset '{dataset_name}'...")
        dataset = client.create_dataset(dataset_name=dataset_name)
        client.create_example(
            inputs={"prompt": "i need to fix my Dishwasher SN23EI03KE in is not responding , i need the fix as soon as possible , Knaan 16, Or Yehuda"},
            outputs={},
            dataset_id=dataset.id,
        )
    else:
        print(f"Dataset '{dataset_name}' already exists.")

    print("Running evaluation...")
    experiment_results = evaluate(
        run_nodes,
        data=dataset_name,
        evaluators=[one_handyman_evaluator, appliance_fixing_evaluator],
        experiment_prefix="dishwasher-evaluation"
    )
    
    print("\nEvaluation complete! Check your LangSmith dashboard for the results.")

if __name__ == "__main__":
    main()
