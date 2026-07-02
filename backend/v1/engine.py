from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import os
import httpx
import json
import re
from openai import OpenAI, APIConnectionError
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import SecretStr
from typing import List, Tuple, Union, Dict, Any

# --- Internal imports             ---
from backend.v1.models import AgentState
from backend.v1.db.database import insert_prompt_log, get_all_categories_with_subs, create_project, create_sub_task, log_test_sub_task
from backend.config import LM_STUDIO_URL, LM_STUDIO_API_KEY

# --- In-memory session store      ---
sessions: Dict[str, AgentState] = {}

# --- LM Studio Connection & Setup ---
def get_llm() -> ChatOpenAI:
    """
    Returns a ChatOpenAI client configured for LM Studio.
    """
    return ChatOpenAI(
        base_url=LM_STUDIO_URL,
        api_key=SecretStr(LM_STUDIO_API_KEY),
        temperature=0.7,
    )


# --- The engine of version 1      ---
class Engine:
    """The Algorithm engine - version 1"""
    
    def __init__(self, llm=None):
        self.llm = llm if llm is not None else get_llm()

    # --- Class API methods               --  
    def determine_number_of_subtasks(self, state: AgentState) -> AgentState:
        return llm_determine_number_of_subtasks(self.llm, state)

    def confirm_multiple_subtasks(self, state: AgentState) -> AgentState:
        return llm_confirm_multiple_subtasks(self.llm, state)
    
    def determine_task_category(self, state: AgentState) -> AgentState:
        return llm_determine_task_category(self.llm, state)
    
    def collect_client_info(self, state: AgentState) -> AgentState:
        return llm_collect_client_info(self.llm, state)
    
    # --- Main workflow Router ---
    def process(self, state: AgentState) -> AgentState:
        """Main workflow - runs steps until it needs user input"""
        max_iterations = 3
        for _ in range(max_iterations):
            current_step = state.next_step
            
            if current_step == "determine_number_of_subtasks":
                state = self.determine_number_of_subtasks(state)
            elif current_step == "confirm_multiple_subtasks":
                state = self.confirm_multiple_subtasks(state)
            elif current_step == "determine_task_category":
                state = self.determine_task_category(state)
            elif current_step == "collect_client_info":
                state = self.collect_client_info(state)
            else:
                state = self.determine_number_of_subtasks(state)
                
            # If the step didn't advance, or it reached a stage that needs user input, break.
            if state.next_step == current_step or state.next_step in ["collect_client_info", "confirm_multiple_subtasks"]:
                break
                
        return state
    

# --- LLM Intelligent Implementations ---
def llm_determine_number_of_subtasks(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    user_img = state.messages[-1].get('image')
    
    # Dynamically inject database categories
    categories_str = ""
    try:
        categories = get_all_categories_with_subs()
        for cat in categories:
            subs = ", ".join([f"{sub['name']}" for sub in cat["subcategories"]])
            categories_str += f"- ID: {cat['id']} | **{cat['name']}**: {subs}\n"
    except Exception as e:
        categories_str = "- ID: 1 | General Handyman\n"

    prompt = (
        "You are BuildWizard AI, an intelligent project analyzer. Your goal is to understand how many different "
        "kinds of professionals (categories) are needed to complete the user's request.\n\n"
        "Here are the major categories available in our database:\n"
        f"{categories_str}\n"
        f"User message: '{user_msg}'\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'identified_categories': a list of objects, each containing:\n"
        "    - 'category_id': The ID of the matching major category\n"
        "    - 'name': The name of the category\n"
        "    - 'confidence_score': A float between 0.0 and 1.0 indicating your confidence.\n"
        "- 'reply': A conversational response acknowledging the professionals needed. IF MULTIPLE are needed, ask the user to confirm what specific subtasks they think they will need for the job.\n"
        "Example format:\n"
        '{"identified_categories": [{"category_id": 1, "name": "plumbing", "confidence_score": 0.95}], "reply": "Great, I see you need a plumber!"}'
    )

    messages_payload: List[Tuple[str, Any]] = [
    ("system", prompt),
    ]

    for msg in state.messages:
        m_role = msg["role"]
        m_content = msg.get("content", "")
        m_img = msg.get("image")
        if m_img and m_role == "user":
            messages_payload.append((m_role, [
                {"type": "text", "text": m_content},
                {"type": "image_url", "image_url": {"url": m_img}}
            ]))
        else:
            messages_payload.append((m_role, m_content))

    try:
        if state.ip_address:
            insert_prompt_log(state.ip_address, prompt)
        response = llm.invoke(messages_payload)
        content = response.content.strip() # type: ignore
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            cats = data.get("identified_categories", [])
            
            if cats:
                state.identified_categories = cats
                if len(cats) > 1:
                    state.next_step = "confirm_multiple_subtasks"
                else:
                    state.next_step = "determine_task_category"
                
                # Log to the testing AI log table
                if state.session_id:
                    for cat in cats:
                        log_test_sub_task(
                            session_id=state.session_id, 
                            category_id=cat.get("category_id"), 
                            confidence_score=cat.get("confidence_score", 0.0),
                            comments=f"Raw AI Output: {cat.get('name')}"
                        )
            
            state.messages.append({"role": "assistant", "content": data.get("reply", "Understood. Moving to the next step.")})
            return state
    except APIConnectionError as e:      
        print(f"API Connection Error: {e}")
        print(f"{e.__cause__}")
        state.messages.append({"role": "assistant", "content": "⚠️ **Error:** I'm having trouble connecting to the AI brain right now. Please verify LM Studio is running!"})
    except Exception as e:
        print(f"LLM node 1 failed: {e}")
        state.messages.append({"role": "assistant", "content": "⚠️ **Error:** I'm having trouble connecting to the AI brain right now. Please verify LM Studio is running!"})

    return state


def llm_confirm_multiple_subtasks(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    
    prompt = (
        "You are BuildWizard AI. We previously identified multiple professionals needed for the project:\n"
        f"{json.dumps(state.identified_categories)}\n\n"
        f"The user was asked to confirm the specific subtasks they think they will need.\n"
        f"User's response: '{user_msg}'\n\n"
        "Your goal is to parse their response and update the identified categories if they mentioned they don't need some of them, "
        "or just acknowledge their details and move to task categorization.\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'updated_categories': The final list of category objects (same structure as above) that we should proceed with.\n"
        "- 'reply': A short conversational acknowledgment before moving on.\n"
    )

    messages_payload: List[Tuple[str, Any]] = [
        ("system", prompt),
        ("user", "Process my response and finalize the categories.")
    ]

    try:
        if state.ip_address:
            insert_prompt_log(state.ip_address, prompt)
        response = llm.invoke(messages_payload)
        content = response.content.strip() # type: ignore
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            updated_cats = data.get("updated_categories", [])
            
            if updated_cats:
                state.identified_categories = updated_cats
                
            state.next_step = "determine_task_category"
            state.messages.append({"role": "assistant", "content": data.get("reply", "Got it. Let me break down the subtasks now.")})
            return state
    except Exception as e:
        print(f"LLM confirm multiple failed: {e}")
        state.messages.append({"role": "assistant", "content": "⚠️ **Error:** I couldn't process your confirmation. Let's try again!"})
        
    return state


def llm_determine_task_category(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    
    prompt = (
        "You are BuildWizard AI. We have identified the following categories needed for the project:\n"
        f"{json.dumps(state.identified_categories)}\n\n"
        f"Original User Request: '{state.messages[0].get('content', '')}'\n"
        "Your task is to break down the user's project into specific subtasks for each identified category.\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'sub_tasks': a list of objects, each containing:\n"
        "    - 'category_id': The ID of the category this subtask belongs to\n"
        "    - 'description': A detailed description of what needs to be done for this subtask\n"
        "    - 'confidence_score': A float between 0.0 and 1.0 indicating your confidence in this categorization.\n"
        "- 'reply': A professional response informing the user that we have categorized their subtasks, and asking for their contact details (Name, Phone, Address) to proceed.\n"
    )

    messages_payload: List[Tuple[str, Any]] = [
        ("system", prompt),
        ("user", "Please categorize the subtasks and prompt for contact info.")
    ]

    try:
        if state.ip_address:
            insert_prompt_log(state.ip_address, prompt)
        response = llm.invoke(messages_payload)
        content = response.content.strip() # type: ignore
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            tasks = data.get("sub_tasks", [])
            
            if tasks:
                state.sub_tasks = tasks
                
            state.next_step = "collect_client_info"
            state.messages.append({"role": "assistant", "content": data.get("reply")})
                
            return state
    except Exception as e:
        print(f"LLM node 2 failed: {e}")
        state.messages.append({"role": "assistant", "content": "⚠️ **Error:** I couldn't categorize the subtasks. Please try again!"})
        
    return state


def llm_collect_client_info(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    
    prompt = (
        f"Currently collected client info: {json.dumps(state.client_info)}\n"
        f"User's response: '{user_msg}'\n\n"
        "You are BuildWizard AI. The user's project has been split into subtasks, and we now need their contact details to save the request.\n"
        "The required fields are: 'name', 'phone', and 'address'.\n\n"
        "Your goal is to:\n"
        "1. Extract any new contact information from the user's response.\n"
        "2. If 'name', 'phone', or 'address' are still missing, ask the user for them politely.\n"
        "3. If all required contact details are gathered, return confirmed: true.\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'extracted_details': a dictionary of the newly extracted contact details (e.g. {'name': 'John', 'phone': '555-1234'}).\n"
        "- 'confirmed': true if we have name, phone, and address. false otherwise.\n"
        "- 'reply': your professional response / question to the user. If confirmed, give a warm closing message saying the project was saved and sent to contractors.\n"
    )
    
    messages_payload: List[Tuple[str, Any]] = [
        ("system", prompt),
        ("user", user_msg)
    ]

    try:
        if state.ip_address:
            insert_prompt_log(state.ip_address, prompt)
        response = llm.invoke(messages_payload)
        content = response.content.strip() # type: ignore
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            new_details = data.get("extracted_details", {})
            for k, v in new_details.items():
                if k in ["name", "phone", "address"]:
                    state.client_info[k] = str(v)
            
            has_all = all(k in state.client_info for k in ["name", "phone", "address"])
            
            if data.get("confirmed") or has_all:
                # Need a real client creation logic here, assuming Client ID 1 for now if we can't create one.
                # In a real app we'd save the Client, then Project, then Sub Tasks.
                desc = state.messages[0].get('content', 'General Project')
                project_id = create_project(client_id=1, description=desc, comments=str(state.client_info))
                if project_id:
                    for st in state.sub_tasks:
                        create_sub_task(project_id=project_id, category_id=st.get("category_id"), comments=st.get("description"))
                
                state.messages.append({"role": "assistant", "content": data.get("reply", "Perfect! Your request has been saved and sent to local contractors. We will be in touch shortly!")})
                state.identified_categories = []
                state.sub_tasks = []
                state.client_info = {}
                state.next_step = "determine_number_of_subtasks"
            else:
                state.messages.append({"role": "assistant", "content": data.get("reply")})

            return state
    except Exception as e:
        print(f"LLM client info gathering failed: {e}")
        state.messages.append({"role": "assistant", "content": "⚠️ **Error:** I couldn't process your contact info. Please try again!"})
        
    return state
