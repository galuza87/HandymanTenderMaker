# Testing with LangSmith Tools

LangSmith is a powerful tool for tracing, evaluating, and monitoring your LLM applications. Based on your codebase (specifically `tests/test_langsmith.py`), you are already using the LangSmith Evaluation framework.

Here is a complete explanation of how you can test your application using LangSmith, broken down into the three main concepts: **Datasets**, **Target Functions**, and **Evaluators**.

## 1. Creating and Managing Datasets

A dataset in LangSmith is a collection of examples (inputs and optionally expected outputs) that you want to test your application against.

In your `test_langsmith.py`, you are doing this programmatically:

```python
client = Client()
dataset_name = "Dishwasher_Test"

if not client.has_dataset(dataset_name=dataset_name):
    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_example(
        inputs={"prompt": "i need to fix my Dishwasher SN23EI03KE..."},
        outputs={}, # Optional expected outputs to compare against
        dataset_id=dataset.id,
    )
```

**How to improve this:**

- **Add more examples:** Testing on one example isn't enough. You should add diverse examples (e.g., edge cases, unrelated prompts, prompts missing details).
- **Use the UI:** You can also create datasets directly in the LangSmith Web UI by uploading CSV/JSON files or by converting production traces (logs) into dataset examples.
- **Define expected outputs:** If you provide `outputs` when creating examples, you can use them in your evaluators to compare the actual LLM output against the ground truth.

## 2. Defining the Target Function

The target function is the wrapper around your application logic that LangSmith will call for *each* example in your dataset.

In your code, your target function is:

```python
def run_nodes(inputs: dict) -> dict:
    prompt = inputs["prompt"]
    # ... setup state, llm, engine ...
  
    # Run the nodes
    state = engine.determine_number_of_subtasks(state)
    if state.next_step == "determine_task_category":
        state = engine.determine_task_category(state)
      
    return {
        "identified_categories": state.identified_categories,
        "sub_tasks": state.sub_tasks
    }
```

**How it works:**
LangSmith passes the `inputs` dictionary from your dataset into this function, runs it, and captures the dictionary you `return` as the actual outputs of the run.

## 3. Creating Evaluators

Evaluators are functions that grade the output of your target function. They look at what your app produced and assign a score (e.g., 1 or 0, or a continuous value).

You have defined heuristic (rule-based) evaluators:

```python
def one_handyman_evaluator(run, example) -> dict:
    outputs = run.outputs
    categories = outputs.get("identified_categories", [])
    # Score 1 if exactly 1 category was identified, else 0
    score = 1 if len(categories) == 1 else 0
    return {"key": "one_handyman_identified", "score": score}
```

**Types of Evaluators you can use:**

1. **Rule-based Evaluators (Heuristics):** Like yours, these check for specific keywords, array lengths, or exact string matches. They are fast and cheap.
2. **LLM-as-a-Judge Evaluators:** You can use an LLM (like GPT-4 or Claude) to evaluate the output. This is useful for subjective criteria like "Is this tone polite?" or "Did the agent extract the correct entity?" LangSmith provides built-in evaluators for this (e.g., `LangChainStringEvaluator`).
3. **Reference-based Evaluators:** These compare the actual output against the `outputs` (ground truth) defined in your dataset example.

## 4. Running the Evaluation

To tie it all together, you use the `evaluate` function:

```python
experiment_results = evaluate(
    run_nodes, # 1. Your target function
    data=dataset_name, # 2. Your dataset
    evaluators=[one_handyman_evaluator, appliance_fixing_evaluator], # 3. Your evaluators
    experiment_prefix="dishwasher-evaluation"
)
```

When you run this script (`python tests/test_langsmith.py`), LangSmith will:

1. Fetch the dataset.
2. Run `run_nodes` for every example in the dataset concurrently.
3. Run your evaluators on the outputs.
4. Upload all traces and scores to the LangSmith UI.

## How to View and Interpret Results

After running your tests, you should open the **LangSmith Dashboard** in your browser.

1. Navigate to the **Datasets & Testing** tab.
2. Click on your dataset (`Dishwasher_Test`).
3. You will see a list of **Experiments** (runs with the prefix `dishwasher-evaluation`).
4. Click on an experiment to see a table comparing the inputs, outputs, and the scores assigned by your evaluators.
5. If an example failed (scored 0), you can click on it to see the **Trace**, which will show you exactly what prompts were sent to the LLM and what the LLM responded with, allowing you to debug the failure.

> [!TIP]
> **Next Step:** I recommend adding a few more complex examples to your `test_langsmith.py` script to test how your system handles edge cases, such as "My house is flooded and the roof is leaking" (which should identify multiple handymen).
