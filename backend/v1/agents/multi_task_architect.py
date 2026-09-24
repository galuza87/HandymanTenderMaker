import re
import json
from backend.llm import get_llm
from backend.v1.agents.base import GraphState
from backend.v1.tools import fetch_available_categories
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent as create_agent
from backend.v1.eval import multi_task_architect_judge

def multi_task_architect_node(state: GraphState) -> dict:
    """Breaks a multi-trade request into a list of category-tagged sub-tasks.

    Runs a tool-using agent (with `fetch_available_categories`) in a loop
    until it outputs a JSON list of sub-tasks (each with a description and
    category ID) or determines it needs to ask a clarifying question first.
    Completion is signaled the same way as `contractor_categorizer_node` --
    an "ALL_DONE" sentinel appended to the agent's own output, parsed out
    and stripped before the message reaches the user.

    Args:
        state: The current graph state. Reads `state["messages"]` and
            `state["sub_tasks"]`.

    Returns:
        A dict with updated `messages` and `sub_tasks` (appended to, not
        replaced). `next_agent` is set to "IntakeCoordinator" once the
        sub-task list has been parsed, or loops back to "MultiTaskArchitect"
        if the agent still needs more information.

    Note:
        Any change to this node's decision logic must be reflected in
        `eval/multi_task_architect_judge.py`, its SYSTEM_PROMPT must be
        kept in sync with any future change to this node's sub-task
        decomposition logic.
    """

    llm = get_llm()
    system_prompt = (
        "You are the Multi-Task Architect. The project requires multiple professionals.\n"
        "Use the fetch_available_categories tool to see the available trades.\n"
        "Break the project into a JSON list of sub-tasks. Each item should have a 'description' and a 'category_id'.\n"
        "Example: [{\"description\": \"Inspect power source\", \"category_id\": 2}]\n"
        "If you are unsure about the scope, ask the user a clarifying question (do not output JSON, do NOT append ALL_DONE).\n"
        "If you are finished and have output the JSON list, append ALL_DONE."
    )
    
    agent = create_agent(model=llm, tools=[fetch_available_categories], prompt=system_prompt)
    
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        if isinstance(content_str, str) and "ALL_DONE" in content_str:
            clean_content = content_str.replace("ALL_DONE", "").strip()
            import re
            match = re.search(r'\[.*\]', clean_content, re.DOTALL)
            if match:
                clean_content = re.sub(r'\[.*\]', '', clean_content, flags=re.DOTALL).strip()
                    
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
                
            next_agent = "IntakeCoordinator"
        else:
            next_agent = "MultiTaskArchitect"

        # Fire the online judge with the node's real decision, not the error-fallback path.
        multi_task_architect_judge.maybe_evaluate_async(state.get("messages", []), sub_tasks)

        return {
            "messages": result["messages"], 
            "next_agent": next_agent
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"MultiTaskArchitect error: {e}"}]}
