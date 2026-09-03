import re
from backend.v1.llm import get_llm
from backend.v1.agents.base import GraphState
from backend.v1.db.database import create_project
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent as create_agent

def intake_node(state: GraphState) -> dict:
    llm = get_llm()
    
    def _save_client_and_project(name: str, phone: str, address: str, general_description: str) -> str:
        try:
            client_id = state.get("user_id")
            if not client_id:
                client_id = 1 
            project_id = create_project(client_id=client_id, description=general_description, comments=f"Name: {name}, Phone: {phone}, Address: {address}")
            return f"PROJECT_ID_{project_id}"
        except Exception as e:
            return f"Failed to save to database: {e}"

    save_tool = StructuredTool.from_function(
        func=_save_client_and_project,
        name="save_client_and_project",
        description="Saves the collected client info and project details into the database."
    )
    
    client_info_str = f"{state.get('client_info', {})}"
    system_prompt = (
        "You are the Intake Coordinator. "
        f"CRITICAL INSTRUCTION: You have these client details pre-loaded: {client_info_str}\n"
        "1. DO NOT ask for Name or Phone if they are already present.\n"
        "2. If an 'address' is present, YOU MUST ask them to confirm it: 'Is this the correct address: [address]?'\n"
        "3. ONLY ask for info if it is missing or if they say the pre-loaded info is wrong.\n"
        "Once you have confirmed/collected Name, Phone, and Address, YOU MUST use save_client_and_project to save the project.\n"
        "After saving, if the tool returned PROJECT_ID_123, output ALL_DONE_PROJECT_123."
    )
    
    agent = create_agent(model=llm, tools=[save_tool], prompt=system_prompt)
    
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        project_id = state.get("project_id")
        next_agent = "IntakeCoordinator"
        
        if isinstance(content_str, str) and "ALL_DONE_PROJECT_" in content_str:
            import re
            match = re.search(r'ALL_DONE_PROJECT_(\d+)', content_str)
            if match:
                project_id = int(match.group(1))
            
            clean_content = re.sub(r'ALL_DONE_PROJECT_\d+', '', content_str).strip()
            if not clean_content:
                clean_content = "Your project details have been saved. I'm preparing the tenders for the contractors now."
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
                
            next_agent = "TenderCreator"
        else:
            next_agent = "IntakeCoordinator"
            
        return {
            "messages": result["messages"],
            "next_agent": next_agent,
            "project_id": project_id
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"Intake error: {e}"}]}
