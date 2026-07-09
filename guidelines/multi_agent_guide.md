# Multi-Agent Orchestration & Sub-Agents Guide

As your AI application grows, relying on a single complex prompt to handle everything from routing to database lookups to conversational responses becomes slow, error-prone, and difficult to manage. This is where **Multi-Agent Orchestration** and **Sub-Agents** come in.

---

## 1. What are Sub-Agents and Multi-Agent Orchestration?

**Sub-Agents** are specialized, narrow-scope LLM instances. Instead of one "God Agent" trying to do everything, you create a team of specialized AI workers. Each worker has a specific persona, a focused prompt, and a clear goal.

**Multi-Agent Orchestration** is the framework that manages how these sub-agents work together. It involves a "Supervisor" or "Router" that delegates tasks to the appropriate sub-agent, passes information (state) between them, and decides when the overall task is complete.

---

## 2. Tooling: Do Sub-Agents Share the Same Tools?

**No. Every single sub-agent can and *should* have its own specific set of tools.**

This concept is called **Tool Scoping**. It is one of the biggest advantages of a multi-agent system.

When you give a single LLM 20 different tools, it has to spend processing power reading the descriptions for all 20 tools on every turn, and it increases the risk of the LLM "hallucinating" and using the wrong tool. 

In a multi-agent system:
- **Intake Agent:** Only has access to `validate_phone_number` and `save_client_details`. It doesn't even know the database lookup tools exist.
- **Category Specialist:** Only has access to `fetch_categories` and `search_database`. It cannot save client details.
- **Support Agent:** Only has access to `lookup_project_status`.

By giving each sub-agent only the tools required for its specific job, you drastically improve speed, reliability, and security.

---

## 3. How Multi-Agent Orchestration Fits Your Project

Looking at your `engine.py`, you currently have a state machine (`AgentState`) that linearly routes between functions:
1. `determine_number_of_subtasks`
2. `confirm_multiple_subtasks`
3. `determine_task_category`
4. `collect_client_info`

This is already a fantastic foundation! You can easily upgrade this into a true multi-agent system (using frameworks like **LangGraph** or **CrewAI**, or by enhancing your existing `process()` loop). 

Here is how your system would look as a Multi-Agent Orchestration:

### The Supervisor Agent (The Orchestrator)
Replaces your current hardcoded `process()` routing loop. 
- **Role:** Reads the user's latest message and the `AgentState`. Decides which Sub-Agent to call next, or if it needs to return a response to the user.
- **Tools:** None. Its only job is routing.

### Sub-Agent 1: The Categorizer
Replaces `llm_determine_number_of_subtasks` and `llm_confirm_multiple_subtasks`.
- **Role:** Analyzes the user's project request and figures out what trades are needed (Plumber, Electrician, etc.).
- **Tools:** `fetch_available_categories()`
- **Model:** Can use a very fast, small model (like Llama-3-8B) because categorization is a relatively simple task.

### Sub-Agent 2: The Project Architect
Replaces `llm_determine_task_category`.
- **Role:** Takes the categories found by Agent 1 and breaks the user's request down into highly detailed, actionable sub-tasks for the contractors.
- **Tools:** None (or maybe a `search_building_codes()` tool if needed later).
- **Model:** Might use a larger, smarter model (like GPT-4o or Llama-3-70B) because generating complex project breakdowns requires deep reasoning.

### Sub-Agent 3: The Intake Coordinator
Replaces `llm_collect_client_info`.
- **Role:** A highly conversational agent that politely asks the user for their Name, Phone, and Address. 
- **Tools:** `save_client_project()`, `validate_address()`
- **Model:** Fast model tuned for conversational empathy.

---

## 4. Key Benefits for `DynamicPromptWizard`

1. **Model Optimization:** As shown above, you can use smaller, faster local models for simple tasks (Intake) and reserve heavy compute for complex tasks (Architect). This drastically reduces overall processing time.
2. **Easier Debugging:** If the AI categorizes something wrong, you only have to fix the prompt for the *Categorizer Agent*. You don't have to worry about accidentally breaking the *Intake Agent's* prompt.
3. **Infinite Scalability:** Want to add a new feature where users can ask for pricing estimates? You don't need to rewrite your core prompt. You just create a new **Estimator Agent**, give it a `fetch_prices` tool, and tell the Supervisor Agent that it exists.

---

## 5. Current Architecture Recommendation

If you just want to get this working and test the core logic, **hold off** on a multi-agent framework like LangGraph or CrewAI for now. Keep it as a simple state machine.

However, I highly recommend upgrading your current system to use **native function calling/tool calling** instead of trying to extract JSON strings with Regex. That will give you a massive reliability boost without needing to change your overall architecture.

---

## 6. Code Examples

### Example 1: Defining a Sub-Agent with Scoped Tools

Here is a conceptual example of how you might define the **Categorizer Agent** with its own specific tools and prompt. Notice how this agent only has access to the tools it needs:

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
# Using ChatOpenAI as a placeholder for any LLM interface
from langchain_openai import ChatOpenAI

# 1. Define the specific tools for this Sub-Agent
def fetch_available_categories() -> list:
    """Returns a list of available contractor categories."""
    return ["Plumber", "Electrician", "Carpenter", "Roofer"]

tools = [fetch_available_categories]

# 2. Define a focused persona/prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are the Categorizer Agent. Your only job is to analyze the user's request and use the `fetch_available_categories` tool to determine required trades."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 3. Create the Sub-Agent (using a fast, small model for simple tasks)
llm = ChatOpenAI(model="llama-3-8b", temperature=0)
agent = create_tool_calling_agent(llm, tools, prompt)

categorizer_executor = AgentExecutor(agent=agent, tools=tools)

# Example usage:
# result = categorizer_executor.invoke({"input": "I need someone to fix my leaking pipe."})
```

### Example 2: The Supervisor (Router) Pattern

Here is a conceptual example using **LangGraph** to route between sub-agents based on the current state. The Supervisor determines who should act next, and the graph orchestrates the flow.

```python
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END

# 1. Define the shared state passed between agents
class AgentState(TypedDict):
    messages: list
    next_agent: str
    categories: list

# 2. Define the Supervisor Node
def supervisor_node(state: AgentState) -> dict:
    # Logic to decide the next step (could be an LLM call or simple rules)
    # For this example, we use simple logic based on missing state data
    if not state.get("categories"):
        return {"next_agent": "Categorizer"}
    elif "intake_complete" not in state.get("messages", [])[-1]:
        return {"next_agent": "IntakeCoordinator"}
    else:
        return {"next_agent": "END"}

# 3. Define the Sub-Agent Nodes
def categorizer_node(state: AgentState) -> dict:
    # Here you would call the categorizer_executor from Example 1
    # Return the updated state
    return {"categories": ["Plumber"]}

def intake_node(state: AgentState) -> dict:
    # Here you would call an Intake Agent
    return {"messages": state["messages"] + ["intake_complete"]}

# 4. Define the Routing Logic
def route(state: AgentState) -> Literal["Categorizer", "IntakeCoordinator", "__end__"]:
    next_step = state.get("next_agent")
    if next_step == "Categorizer":
        return "Categorizer"
    elif next_step == "IntakeCoordinator":
        return "IntakeCoordinator"
    return "__end__"

# 5. Build the Orchestration Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Categorizer", categorizer_node)
workflow.add_node("IntakeCoordinator", intake_node)

# Add Edges
workflow.set_entry_point("Supervisor")

# The Supervisor decides where to go next
workflow.add_conditional_edges("Supervisor", route)

# Sub-agents always report back to the Supervisor when finished
workflow.add_edge("Categorizer", "Supervisor") 
workflow.add_edge("IntakeCoordinator", "Supervisor")

app = workflow.compile()
```
