from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Tuple, Literal
import os
import json
import logging
from openai import APIConnectionError, OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent as create_agent
from langchain_core.tools import tool, StructuredTool
from langgraph.graph import StateGraph, END
from typing import TypedDict

# --- Internal imports             ---
from backend.v1.models import AgentState, CategorizerDecisionClass
from backend.v1.db.database import get_all_categories_with_subs, create_project, create_sub_task, log_test_sub_task, get_main_address_by_client_id
from backend.config import LM_STUDIO_URL, LM_STUDIO_API_KEY

# --- In-memory session store removed  ---
# State is now persisted via DB in main.py

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=LM_STUDIO_URL,
        api_key=LM_STUDIO_API_KEY,
        model_name="gpt-4o", # Spoof model name to force Langchain to allow json_schema
        temperature=0.7
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
class DataValidatorOutput(BaseModel):
    status: Literal["enough_information", "not_enough_information"] = Field(description="Return 'enough_information' if the request contains enough information to determine if one or multiple types of contractors are needed (e.g., 'I need a plumber to fix a leak' is enough). Return 'not_enough_information' otherwise.")
    missing_context: Optional[str] = Field(description="If status is 'not_enough_information', specify what context is missing to ask the user.")

class CategorizerDecisionLLMOutput(BaseModel):
    decision: Literal["single", "multiple"] = Field(description="Return 'single' if ONE trade is mentioned. Return 'multiple' if MORE THAN ONE trade is needed.")

class GraphState(TypedDict, total=False):
    messages: list
    identified_categories: list
    sub_tasks: list
    client_info: dict
    next_agent: str
    ip_address: str
    session_id: str
    user_id: Optional[int]
    CategorizerDecision: CategorizerDecisionClass
    project_id: Optional[int]
    is_finished: bool

# --- Agent Nodes ---
def data_validator_node(state: GraphState) -> dict:
    llm = get_llm().with_structured_output(DataValidatorOutput)
    
    system_prompt = (
        "You are the Data Validator. Review the client request. "
        "Your goal is to determine if the request has enough information to cleanly identify all required contractor types (single or multiple). "
        "1. If the user request is just a greeting (like 'hello'), or too vague to know, it does NOT have enough information. "
        "2. If the client describes a complex problem that clearly involves multiple trades (e.g., plumbing and tiling) but only asks for ONE trade (e.g., 'I need a tiler'), "
        "it does NOT have enough information. You must flag this discrepancy and use 'missing_context' to explain that another trade (like a plumber) might also be needed, asking for clarification. "
        "If the request is clear and straightforward (e.g., 'I need a plumber to fix a leak' or 'I need a plumber and an electrician'), it has enough information."
    )
    try:
        messages = [{"role": "system", "content": system_prompt}] + state.get("messages", [])
        parsed = llm.invoke(messages)
        
        has_enough_data = parsed.status == "enough_information"
        missing_context = parsed.missing_context or "Could you provide more details about the scope of work and the area involved?"
        
        if not has_enough_data:
            from langchain_core.messages import AIMessage
            new_messages = state.get("messages", []) + [AIMessage(content=missing_context)]
            return {
                "messages": new_messages,
                "next_agent": "DataValidator" # We will route to END in edge
            }
        else:
            return {
                "next_agent": "Categorizer"
            }
    except Exception as e:
        print(f"DataValidator error: {e}")
        return {
            "next_agent": "Categorizer"
        }

def categorizer_node(state: GraphState) -> dict:
    client = OpenAI(base_url=LM_STUDIO_URL, api_key=LM_STUDIO_API_KEY)
    
    system_prompt = (
        "You are the Categorizer Agent. Analyze the user's request.\n"
        "Your ONLY job is to determine if the task requires a 'single' professional or 'multiple' professionals."
    )
    try:
        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in state.get("messages", []):
            if isinstance(msg, dict):
                oai_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            elif hasattr(msg, "type"):
                role = msg.type if msg.type in ["user", "assistant", "system"] else "user"
                if role == "human": role = "user"
                if role == "ai": role = "assistant"
                oai_messages.append({"role": role, "content": getattr(msg, "content", "")})
            else:
                oai_messages.append({"role": "user", "content": str(msg)})

        schema = CategorizerDecisionLLMOutput.model_json_schema()
        # Remove title which sometimes causes issues with structured outputs
        if "title" in schema:
            del schema["title"]

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=oai_messages,
            temperature=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "CategorizerDecisionLLMOutput",
                    "schema": schema,
                    "strict": True
                }
            }
        )
        
        content = completion.choices[0].message.content
        parsed = json.loads(content)
        decision = parsed.get("decision", "multiple")
        
        result = CategorizerDecisionClass(decision=decision)
        
        if result.decision == "single":
            next_agent = "ContractorCategorizer"
        else:
            next_agent = "MultiTaskArchitect"
            
        return {
            "CategorizerDecision": result,
            "next_agent": next_agent
        }
    except Exception as e:
        print(f"Categorizer error: {e}")
        return {
            "CategorizerDecision": CategorizerDecisionClass(decision="multiple"),
            "next_agent": "InformationGatherer"
        }

def information_gatherer_node(state: GraphState) -> dict:
    llm = get_llm()
    system_prompt = (
        "You are the Information Gatherer. The user's request is too vague for us to categorize.\n"
        "Ask ONE clarifying question to understand exactly what they need fixed or built.\n"
        "DO NOT attempt to assign trades, just ask the question. End your response with ALL_DONE."
    )
    
    agent = create_agent(model=llm, tools=[], prompt=system_prompt)
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        if isinstance(content_str, str) and "ALL_DONE" in content_str:
            clean_content = content_str.replace("ALL_DONE", "").strip()
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
                
        return {
            "messages": result["messages"], 
            "next_agent": "Categorizer" # Next loop should start at categorizer again
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"InformationGatherer error: {e}"}]}

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

def multi_task_architect_node(state: GraphState) -> dict:
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
        
        sub_tasks = list(state.get("sub_tasks", []))
        
        if isinstance(content_str, str) and "ALL_DONE" in content_str:
            clean_content = content_str.replace("ALL_DONE", "").strip()
            import re
            match = re.search(r'\[.*\]', clean_content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        for task_desc in parsed:
                            if isinstance(task_desc, dict) and 'description' in task_desc and 'category_id' in task_desc:
                                sub_tasks.append({
                                    "sub_task_id": len(sub_tasks) + 1, 
                                    "description": task_desc['description'],
                                    "category_id": task_desc['category_id']
                                })
                    clean_content = re.sub(r'\[.*\]', '', clean_content, flags=re.DOTALL).strip()
                except Exception as e:
                    print(f"Failed to parse sub-tasks: {e}")
                    
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
                
            next_agent = "IntakeCoordinator"
        else:
            next_agent = "MultiTaskArchitect"
            
        return {
            "messages": result["messages"], 
            "sub_tasks": sub_tasks,
            "next_agent": next_agent
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"MultiTaskArchitect error: {e}"}]}

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

def tender_creator_node(state: GraphState) -> dict:
    llm = get_llm()
    project_id = state.get("project_id")
    sub_tasks = state.get("sub_tasks", [])
    
    if not project_id:
        return {"messages": state["messages"] + [{"role": "assistant", "content": "TenderCreator error: Missing project_id."}], "next_agent": "Categorizer"}
        
    system_prompt = (
        "You are the Tender Creator. Based on the conversation history, write a clear, professional Tender prompt (job description) that will be shown to contractors.\n"
        "Do not include greetings. Just output the tender text."
    )
    
    new_messages = list(state["messages"])
    
    if len(sub_tasks) == 0:
        agent = create_agent(model=llm, tools=[], prompt=system_prompt)
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        tender_text = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        cat_id = None
        try:
            categories = get_all_categories_with_subs()
            if categories:
                cat_id = categories[0]['id']
        except Exception:
            cat_id = 1
            
        if state.get("identified_categories") and len(state.get("identified_categories")) > 0:
            cat_id = state.get("identified_categories")[0].get("category_id", cat_id)
            
        create_sub_task(project_id=project_id, category_id=cat_id, comments=tender_text)
        new_messages.append(AIMessage(content="Your tender has been created and sent to contractors."))
    else:
        new_messages.append(AIMessage(content="Creating multiple tenders for your project..."))
        for task in sub_tasks:
            prompt = system_prompt + f"\nSpecifically, write the tender for this sub-task: {task.get('description')}"
            agent = create_agent(model=llm, tools=[], prompt=prompt)
            result = agent.invoke({"messages": state["messages"]})
            last_message = result["messages"][-1]
            tender_text = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
            
            cat_id = task.get('category_id')
            if not cat_id:
                try:
                    categories = get_all_categories_with_subs()
                    if categories:
                        cat_id = categories[0]['id']
                except Exception:
                    cat_id = 1
            create_sub_task(project_id=project_id, category_id=cat_id, comments=tender_text)
            
        new_messages.append(AIMessage(content="All tenders have been created and sent to the respective contractors."))
        
    return {
        "messages": new_messages,
        "next_agent": "Categorizer",
        "is_finished": True
    }

# --- Routing logic ---
def route(state: GraphState) -> str:
    return state.get("next_agent", "Categorizer")

def supervisor_node(state: GraphState) -> dict:
    next_agent = state.get("next_agent")
    if not next_agent or next_agent == "determine_number_of_subtasks" or next_agent == "Categorizer" and not state.get("CategorizerDecision"):
        # If it was Categorizer but we haven't done DataValidator yet, maybe we should start at DataValidator
        return {"next_agent": "DataValidator"}
    return {"next_agent": next_agent}

# --- Build Graph ---
workflow = StateGraph(GraphState)
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("DataValidator", data_validator_node)
workflow.add_node("Categorizer", categorizer_node)
workflow.add_node("InformationGatherer", information_gatherer_node)
workflow.add_node("ContractorCategorizer", contractor_categorizer_node)
workflow.add_node("MultiTaskArchitect", multi_task_architect_node)
workflow.add_node("IntakeCoordinator", intake_node)
workflow.add_node("TenderCreator", tender_creator_node)

def data_validator_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "DataValidator":
        return END # Pause to wait for user reply (missing_context)
    return next_agent

def categorizer_edge(state: GraphState) -> str:
    return state.get("next_agent", "Categorizer")

def contractor_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "ContractorCategorizer":
        return END # Pause to wait for user reply
    return next_agent

def architect_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "MultiTaskArchitect":
        return END # Pause to wait for user reply
    return next_agent

def intake_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "IntakeCoordinator":
        return END # Pause to wait for user reply
    return next_agent

workflow.set_entry_point("Supervisor")
workflow.add_conditional_edges(
    "Supervisor", 
    route,
    ["DataValidator", "Categorizer", "InformationGatherer", "ContractorCategorizer", "MultiTaskArchitect", "IntakeCoordinator", "TenderCreator"]
)

workflow.add_conditional_edges(
    "DataValidator",
    data_validator_edge,
    ["Categorizer", END]
)

workflow.add_conditional_edges(
    "Categorizer", 
    categorizer_edge,
    ["InformationGatherer", "ContractorCategorizer", "MultiTaskArchitect", "Categorizer"]
)
workflow.add_edge("InformationGatherer", END)
workflow.add_conditional_edges(
    "ContractorCategorizer", 
    contractor_edge,
    ["IntakeCoordinator", END]
)
workflow.add_conditional_edges(
    "MultiTaskArchitect", 
    architect_edge,
    ["IntakeCoordinator", END]
)
workflow.add_conditional_edges(
    "IntakeCoordinator", 
    intake_edge,
    ["TenderCreator", END]
)
workflow.add_edge("TenderCreator", END)

app = workflow.compile()

# --- Engine Wrapper ---
class Engine:
    """The Algorithm engine - Multi-Agent LangGraph version"""
    
    def __init__(self, llm=None):
        pass

    def process(self, state: AgentState) -> AgentState:
        lc_messages = []
        for msg in state.messages:
            if msg.get("role") == "user":
                lc_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                kwargs = {"content": msg.get("content", "")}
                if "tool_calls" in msg:
                    kwargs["tool_calls"] = msg["tool_calls"]
                lc_messages.append(AIMessage(**kwargs))
            elif msg.get("role") == "system":
                lc_messages.append(SystemMessage(content=msg.get("content", "")))
            elif msg.get("role") == "tool":
                lc_messages.append(ToolMessage(content=msg.get("content", ""), tool_call_id=msg.get("tool_call_id", "unknown")))
            else:
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
            "CategorizerDecision": state.CategorizerDecision if hasattr(state, 'CategorizerDecision') and state.CategorizerDecision else None,
            "project_id": state.project_id,
            "is_finished": getattr(state, "is_finished", False)
        }
        
        logging.info(f"--- [Engine Process Start] next_step: {state.next_step} ---")
        
        final_state = app.invoke(input_state)
        
        logging.info(f"--- [Engine Process End] returned next_agent: {final_state.get('next_agent')} ---")
        # todo andrew need to handle it properly 
        new_messages = []
        for msg in final_state["messages"]:
            if isinstance(msg, HumanMessage):
                new_messages.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                d = {"role": "assistant", "content": str(msg.content)}
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    d["tool_calls"] = msg.tool_calls
                new_messages.append(d)
            elif isinstance(msg, SystemMessage):
                new_messages.append({"role": "system", "content": str(msg.content)})
            elif isinstance(msg, ToolMessage):
                new_messages.append({"role": "tool", "content": str(msg.content), "tool_call_id": getattr(msg, "tool_call_id", "unknown")})
            else:
                if isinstance(msg, dict):
                    new_messages.append({"role": msg.get("role", "unknown"), "content": str(msg.get("content", ""))})
                else:
                    new_messages.append({"role": msg.type if hasattr(msg, "type") else "unknown", "content": str(getattr(msg, "content", ""))})
        
        state.messages = new_messages
        state.next_step = final_state.get("next_agent", "DataValidator")
        
        if "sub_tasks" in final_state:
            state.sub_tasks = final_state["sub_tasks"]
        if "CategorizerDecision" in final_state and final_state["CategorizerDecision"]:
            state.CategorizerDecision = final_state["CategorizerDecision"]
        else:
            state.CategorizerDecision = None
            
        if "project_id" in final_state and final_state["project_id"]:
            state.project_id = final_state["project_id"]
        else:
            state.project_id = None
            
        if "is_finished" in final_state:
            state.is_finished = final_state["is_finished"]
        
        return state
