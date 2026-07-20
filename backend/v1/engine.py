from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Tuple, Literal
import os
import json
import logging
from openai import APIConnectionError
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent as create_agent
from langchain_core.tools import tool, StructuredTool
from langgraph.graph import StateGraph, END
from typing import TypedDict

# --- Internal imports             ---
from backend.v1.models import AgentState
from backend.v1.db.database import get_all_categories_with_subs, create_project, create_sub_task, log_test_sub_task, get_main_address_by_client_id
from backend.config import LM_STUDIO_URL, LM_STUDIO_API_KEY

# --- In-memory session store      ---
sessions: Dict[str, AgentState] = {}

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=LM_STUDIO_URL,
        api_key=LM_STUDIO_API_KEY,
        model_name="gpt-4o", # Spoof model name to force Langchain to allow json_schema
        temperature=0.7,
        # IMPORTANT: LM Studio models must support tool calling for this to work natively.
    )

# --- Define Tools ---
@tool
def fetch_available_categories() -> str:
    """Returns a formatted string of all available contractor categories from the database. Use this to see what trades are available."""
    try:
        categories = get_all_categories_with_subs()
        categories_str = ""
        for cat in categories:
            subs = ", ".join([f"{sub['name']}" for sub in cat["subcategories"]])
            categories_str += f"- ID: {cat['id']} | **{cat['name']}**: {subs}\n"
        return categories_str
    except Exception as e:
        return "- ID: 1 | General Handyman\n"



# --- LangGraph State Definition ---
class GraphState(TypedDict):
    messages: list
    identified_categories: list
    sub_tasks: list
    client_info: dict
    next_agent: str
    ip_address: str
    session_id: str
    user_id: Optional[int]
    CategorizerDecision: dict

# --- Agent Nodes ---
def categorizer_node(state: GraphState) -> dict:
    llm = get_llm()
    
    system_prompt = (
        "You are the Categorizer Agent. Analyze the user's request.\n"
        "Your ONLY job is to determine if the task requires a 'single' professional or 'multiple' professionals.\n"
        "If you cannot decide, return 'multiple' with a low confidence score.\n"
        "Output your decision and your confidence score."
    )
    
    class CategorizerDecisionOutput(BaseModel):
        decision: Literal["single", "multiple"] = Field(description="Return 'single' if only ONE trade or professional is mentioned (e.g. plumber). Return 'multiple' if MORE THAN ONE trade is needed (e.g. plumber and electrician).")
        confidence: float = Field(description="Confidence score between 0.0 and 1.0")
        
    try:
        structured_llm = llm.with_structured_output(CategorizerDecisionOutput, method="json_schema")
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        result = structured_llm.invoke(messages)
        
        decision_dict = {
            "decision": result.decision,
            "confidence": result.confidence
        }
        
        return {
            "CategorizerDecision": decision_dict,
            "next_agent": "Architect"
        }
    except Exception as e:
        print(f"Categorizer error: {e}")
        return {
            "CategorizerDecision": {"decision": "multiple", "confidence": 0.1},
            "next_agent": "Architect"
        }

def architect_node(state: GraphState) -> dict:
    llm = get_llm()
    system_prompt = (
        "You are the Project Architect. Analyze the user's request and break the project into actionable sub-tasks internally.\n"
        "You MUST keep your reasoning and the sub-tasks strictly internal by formatting your ENTIRE response as a JSON list of strings representing the tasks.\n"
        "Example: [\"Inspect power source\", \"Check control board\"]\n"
        "DO NOT output any other text, greetings, or explanations. ONLY output the JSON list."
    )
    
    # We create a tool-less agent for the architect
    agent = create_agent(model=llm, tools=[], prompt=system_prompt)
    
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        # Parse the JSON sub-tasks
        sub_tasks = list(state.get("sub_tasks", []))
        try:
            import json
            import re
            match = re.search(r'\[.*\]', content_str, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    for task_desc in parsed:
                        if isinstance(task_desc, str):
                            sub_tasks.append({"sub_task_id": len(sub_tasks) + 1, "description": task_desc})
        except Exception as e:
            print(f"Failed to parse sub-tasks: {e}")
            
        # Hide the architect's response from the chat history
        result["messages"].pop()
        
        return {
            "messages": result["messages"], 
            "sub_tasks": sub_tasks,
            "next_agent": "IntakeCoordinator"
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"Architect error: {e}"}]}

def intake_node(state: GraphState) -> dict:
    llm = get_llm()
    
    def _save_client_and_project(name: str, phone: str, address: str, general_description: str) -> str:
        """
        Saves the collected client info and project details into the database.
        """
        try:
            client_id = state.get("user_id")
            if not client_id:
                client_id = 1 # Fallback for anonymous users
            
            project_id = create_project(client_id=client_id, description=general_description, comments=f"Name: {name}, Phone: {phone}, Address: {address}")
            return "Project successfully saved to the database. Tell the user it has been submitted to contractors."
        except Exception as e:
            return f"Failed to save to database: {e}"

    save_tool = StructuredTool.from_function(
        func=_save_client_and_project,
        name="save_client_and_project",
        description="Saves the collected client info and project details into the database."
    )
    
    tools = [save_tool]
    
    client_info_str = f"{state.get('client_info', {})}"
    system_prompt = (
        "You are the Intake Coordinator. "
        f"CRITICAL INSTRUCTION: You already have the following client details pre-loaded from the database: {client_info_str}\n"
        "1. DO NOT ask the user for their Name or Phone Number if they are already present in the pre-loaded details above. Use the pre-loaded details.\n"
        "2. If an 'address' is present in the pre-loaded details above, YOU MUST NOT ask them to type their address from scratch. Instead, you MUST ask them to confirm it like this: 'Is this the correct address for the project: [insert address here]?'\n"
        "3. ONLY ask the user to provide Name, Phone, or Address IF they are completely missing from the pre-loaded details, OR if they tell you the pre-loaded address is wrong.\n"
        "Once you have confirmed or collected the final Name, Phone, and Address, YOU MUST use the save_client_and_project tool to save the project.\n"
        "After successfully saving the project via the tool, provide a brief summary of their request, tell the user 'Your tender has been created and you will receive quotes soon.', and append the exact word 'ALL_DONE' to your response."
    )
    
    agent = create_agent(model=llm, tools=tools, prompt=system_prompt)
    
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        if isinstance(content_str, str) and "ALL_DONE" in content_str:
            next_agent = "Categorizer"
            clean_content = content_str.replace("ALL_DONE", "").strip()
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
        else:
            next_agent = "IntakeCoordinator"
            
        return {
            "messages": result["messages"],
            "next_agent": next_agent
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"Intake error: {e}"}]}

# --- Routing logic ---
def route(state: GraphState) -> Literal["Categorizer", "Architect", "IntakeCoordinator", "__end__"]:
    next_agent = state.get("next_agent", "Categorizer")
    if next_agent == "Categorizer" or next_agent == "determine_number_of_subtasks":
        return "Categorizer"
    elif next_agent == "Architect" or next_agent == "determine_task_category" or next_agent == "confirm_multiple_subtasks":
        return "Architect"
    elif next_agent == "IntakeCoordinator" or next_agent == "collect_client_info":
        return "IntakeCoordinator"
    return "Categorizer"

def supervisor_node(state: GraphState) -> dict:
    # Pass-through node to map the previous regex next_step to our new LangGraph next_agent
    current = state.get("next_agent")
    if current in ["determine_number_of_subtasks", "Categorizer", None]:
        return {"next_agent": "Categorizer"}
    if current in ["confirm_multiple_subtasks", "determine_task_category", "Architect"]:
        return {"next_agent": "Architect"}
    if current in ["collect_client_info", "IntakeCoordinator"]:
        return {"next_agent": "IntakeCoordinator"}
    return {"next_agent": "Categorizer"}

# --- Build Graph ---
workflow = StateGraph(GraphState)
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Categorizer", categorizer_node)
workflow.add_node("Architect", architect_node)
workflow.add_node("IntakeCoordinator", intake_node)

def categorizer_edge(state: GraphState) -> str:
    if state.get("next_agent") == "Architect":
        return "Architect"
    return END

def architect_edge(state: GraphState) -> str:
    # Architect seamlessly transitions to IntakeCoordinator
    return "IntakeCoordinator"

def intake_edge(state: GraphState) -> str:
    return END

workflow.set_entry_point("Supervisor")
workflow.add_conditional_edges("Supervisor", route)

workflow.add_conditional_edges("Categorizer", categorizer_edge)
workflow.add_conditional_edges("Architect", architect_edge)
workflow.add_conditional_edges("IntakeCoordinator", intake_edge)

app = workflow.compile()

# --- Engine Wrapper ---
class Engine:
    """The Algorithm engine - Multi-Agent LangGraph version"""
    
    def __init__(self, llm=None):
        pass

    def process(self, state: AgentState) -> AgentState:
        # Convert Pydantic Dict messages to LangChain Messages
        lc_messages = []
        for msg in state.messages:
            if msg.get("role") == "user":
                lc_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                lc_messages.append(AIMessage(content=msg.get("content", "")))
            elif msg.get("role") == "system":
                lc_messages.append(SystemMessage(content=msg.get("content", "")))
            else:
                # Generic fallback if it has a content field
                lc_messages.append(HumanMessage(content=str(msg.get("content", ""))))
                
        input_state = {
            "messages": lc_messages,
            "identified_categories": state.identified_categories,
            "sub_tasks": state.sub_tasks,
            "client_info": state.client_info,
            "next_agent": state.next_step,
            "ip_address": state.ip_address,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "CategorizerDecision": state.CategorizerDecision if hasattr(state, 'CategorizerDecision') and state.CategorizerDecision else {}
        }
        
        # Add debugging logs BEFORE invoking
        logging.info(f"--- [Engine Process Start] next_step: {state.next_step} ---")
        
        # Invoke LangGraph
        final_state = app.invoke(input_state)
        
        # Add debugging logs AFTER invoking
        logging.info(f"--- [Engine Process End] returned next_agent: {final_state.get('next_agent')} ---")
        logging.info(f"Total messages after graph: {len(final_state['messages'])}")
        for idx, m in enumerate(final_state['messages']):
            content = m.content if hasattr(m, 'content') else (m.get('content', '') if isinstance(m, dict) else str(m))
            m_type = type(m)
            logging.info(f"Message {idx} type: {m_type} | content: {content}")
        
        # Map LangChain Messages back to plain dicts for the Pydantic State
        new_messages = []
        for msg in final_state["messages"]:
            if isinstance(msg, HumanMessage):
                new_messages.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                new_messages.append({"role": "assistant", "content": str(msg.content)})
            elif isinstance(msg, SystemMessage):
                new_messages.append({"role": "system", "content": str(msg.content)})
            elif isinstance(msg, ToolMessage):
                new_messages.append({"role": "tool", "content": str(msg.content)})
            else:
                new_messages.append({"role": msg.type if hasattr(msg, "type") else "unknown", "content": str(msg.content)})
        
        state.messages = new_messages
        state.next_step = final_state.get("next_agent", "Categorizer")
        if "sub_tasks" in final_state:
            state.sub_tasks = final_state["sub_tasks"]
        if "CategorizerDecision" in final_state:
            state.CategorizerDecision = final_state["CategorizerDecision"]
        
        return state
