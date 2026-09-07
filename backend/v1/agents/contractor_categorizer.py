import re
from backend.llm import get_llm
from backend.v1.agents.base import GraphState
from backend.v1.tools import fetch_available_categories
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent as create_agent

def contractor_categorizer_node(state: GraphState) -> dict:
    llm = get_llm()
    system_prompt = (
        "You are the Contractor Categorizer. The project only needs ONE professional.\n"
        "Use the fetch_available_categories tool to see the available trades.\n"
        "Identify the EXACT category ID that matches the user's request.\n"
        "If you are unsure, ask the user a clarifying question (do NOT append ALL_DONE).\n"
        "If you have identified the category ID, output it in the format: ALL_DONE_CATEGORY_<ID> (e.g. ALL_DONE_CATEGORY_12)"
    )
    
    agent = create_agent(model=llm, tools=[fetch_available_categories], prompt=system_prompt)
    
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        if isinstance(content_str, str) and "ALL_DONE" in content_str:
            import re
            match = re.search(r'ALL_DONE_CATEGORY_(\d+)', content_str)
            identified_categories = list(state.get("identified_categories") or [])
            if match:
                cat_id = int(match.group(1))
                identified_categories.append({"category_id": cat_id, "name": "Categorized by AI"})
            
            clean_content = re.sub(r'ALL_DONE_CATEGORY_\d+', '', content_str)
            clean_content = clean_content.replace("ALL_DONE", "").strip()
            
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
            next_agent = "IntakeCoordinator"
            
            return {
                "messages": result["messages"],
                "identified_categories": identified_categories,
                "next_agent": next_agent
            }
        else:
            next_agent = "ContractorCategorizer"
            
            return {
                "messages": result["messages"],
                "next_agent": next_agent
            }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"ContractorCategorizer error: {e}"}]}
