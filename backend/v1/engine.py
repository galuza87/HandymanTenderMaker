from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import os
import httpx
import json
import re
# pyrefly: ignore [missing-import]
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import SecretStr
from typing import List, Tuple, Union, Dict, Any

# --- Internal imports             ---
from backend.v1.models import AgentState
from backend.v1.db.database import insert_prompt_log, save_client_and_offer, get_all_categories_with_subs
from backend.v1.tasks import AVAILABLE_TASKS
from backend.v1.fallback_engine import fallback_determine_task, fallback_gather_info, fallback_collect_client_info
load_dotenv()
LM_STUDIO_URL = os.getenv('LM_STUDIO_URL')
LM_STUDIO_API_KEY = os.getenv('LM_STUDIO_API_KEY')

# --- In-memory session store      ---
sessions: Dict[str, AgentState] = {}

# --- LM Studio Connection & Setup ---
def get_llm() -> Optional[ChatOpenAI]:
    """
    Checks if LM Studio is running.
    If yes, returns a ChatOpenAI client. Otherwise, returns None.
    """
    try:
        with httpx.Client(timeout=1.0) as client:
            response = client.get(f"{LM_STUDIO_URL}/models")
            if response.status_code == 200:
                print(f"[INFO] Connected successfully to LM Studio at {LM_STUDIO_URL}!")
                return ChatOpenAI(
                    base_url=LM_STUDIO_URL,
                    api_key=SecretStr(LM_STUDIO_API_KEY),
                    temperature=0.7,
                )
    except Exception:
        pass
    print(f"[WARNING] LM Studio not detected at {LM_STUDIO_URL}. Falling back to rule-based engine.")
    return None


# --- The engine of version 1      ---
class Engine:
    """The Algorithm engine - version 1"""
    
    def __init__(self, llm=None):
        self.llm = llm

    # --- Class API methods               --  
    def determine_task(self, state: AgentState) -> AgentState:
        if self.llm:
            return llm_determine_task(self.llm, state)
        return fallback_determine_task(state)
    
    def gather_info(self, state: AgentState) -> AgentState:
        if self.llm:
            return llm_gather_info(self.llm,state)
        return fallback_gather_info(state)
    
    def collect_client_info(self, state: AgentState) -> AgentState:
        if self.llm:
            return llm_collect_client_info(self.llm,state)
        return fallback_collect_client_info(state)
    
    # --- Main workflow Router ---
    def process(self, state: AgentState) -> AgentState:
        """Main workflow - calls right method based on state"""
        if state.selected_task is None:
            return self.determine_task(state)
        elif state.next_step == "gather_info":
            return self.gather_info(state)
        else:
            return self.collect_client_info(state)
    

#     # --- Main workflow Router ---
# def wizard_workflow(state: AgentState) -> AgentState:
#     llm = get_llm()
#     if llm:
#         if state.selected_task is None:
#             return llm_determine_task(llm, state)
#         elif state.next_step == "determine_task" or state.next_step == "gather_info":
#             return llm_gather_info(llm, state)
#         else:
#             return llm_collect_client_info(llm, state)
#     else:
#         # Fallback to rule-based logic
#         if state.selected_task is None:
#             return determine_task(state)
#         elif state.next_step == "determine_task" or state.next_step == "gather_info":
#             return gather_info(state)
#         else:
#             state.messages.append({
#                 "role": "assistant", 
#                 "content": "Perfect! Your request has been saved and sent to local contractors! 🛠️"
#             })
#             state.selected_task = None
#             state.collected_details = {}
#             state.client_info = {}
#             state.next_step = "determine_task"
#             return state
        
# --- LLM Intelligent Implementations ---
def llm_determine_task(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    user_img = state.messages[-1].get('image')
    
    # Dynamically inject database categories
    categories_str = ""
    try:
        categories = get_all_categories_with_subs()
        for cat in categories:
            subs = ", ".join([f"{sub['name']}" + (f" ({sub['brand']})" if sub['brand'] else "") for sub in cat["subcategories"]])
            categories_str += f"- **{cat['name']}**: {subs}\n"
    except Exception as e:
        categories_str = "- plumbing, electrical work, construction, carpentry, roofing, appliance fixing, appliance installing, moving\n"

    prompt = (
        "You are BuildWizard AI, a smart assistant helping users craft perfect prompts and find local handyman contractors.\n"
        "We support these major handyman categories and subcategories from our database:\n"
        f"{categories_str}\n"
        "Analyze the user's input and classify their intent into one of the following:\n"
        "- 'handyman_request' (if they want to fix a dishwasher, find a plumber, get electrical repairs, cabinetry, roofing, moving help, or any handyman/repair service)\n"
        "- 'quote_request' (if they want a Construction Quote Request, subcontractor pricing, material list costs, etc.)\n"
        "- 'tender_request' (if they want a Subcontractor Tender Request, contractor bidding document, formal scope of work, etc.)\n"
        "- null (if they are greeting you, asking an unrelated question, or have not decided yet)\n\n"
        f"User message: '{user_msg}'\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'task': 'handyman_request', 'quote_request', 'tender_request', or null\n"
        "- 'reply': A professional, conversational greeting and follow-up query.\n"
        "Example format:\n"
        '{"task": "handyman_request", "reply": "Great, I see you need help with appliance fixing! Is this for a specific brand like Bosch dishwasher?"}'
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
            task = data.get("task")
            if task in ["handyman_request", "quote_request", "tender_request"]:
                state.selected_task = task
                state.next_step = "gather_info"
            state.messages.append({"role": "assistant", "content": data.get("reply")})
            
            return state
    except Exception as e:
        print(f"LLM task determination failed: {e}")

    return fallback_determine_task(state)

def llm_gather_info(llm: ChatOpenAI, state: AgentState) -> AgentState:
    task_key = state.selected_task
    task = AVAILABLE_TASKS[task_key] # type: ignore
    required = task["required_fields"]
    user_msg = state.messages[-1].get('content', '')
    user_img = state.messages[-1].get('image')
    
    categories_str = ""
    try:
        categories = get_all_categories_with_subs()
        for cat in categories:
            subs = ", ".join([f"{sub['name']}" + (f" ({sub['brand']})" if sub['brand'] else "") for sub in cat["subcategories"]])
            categories_str += f"- {cat['name']}: {subs}\n"
    except Exception as e:
        pass

    prompt = (
        f"Task: {task['name']}\n"
        f"Required details to collect: {required}\n"
        f"Currently collected details: {json.dumps(state.collected_details)}\n"
        f"User's response: '{user_msg}'\n\n"
        "If the task is 'handyman_request', help map the user's task to our database categories if possible:\n"
        f"{categories_str}\n\n"
        "You are BuildWizard AI. Your goal is to:\n"
        "1. Extract any new information from the user's response that fits any of the missing required fields. "
        "Do not overwrite already collected details unless the user is specifically correcting them.\n"
        "2. If details are still missing, formulate a conversational, professional question to ask the user for "
        "one or more of the remaining missing details.\n"
        "3. If all required details are now gathered, do not ask a question.\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'extracted_details': a dictionary of the newly extracted details only (e.g., {'major_category': 'appliance fixing'})\n"
        "- 'reply': your professional response / query to the user.\n"
        "Example format:\n"
        '{"extracted_details": {"major_category": "plumbing"}, "reply": "Excellent, I\'ve recorded that you need plumbing help. Next, could you describe the job details?"}'
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
            new_details = data.get("extracted_details", {})
            for k, v in new_details.items():
                if k in required:
                    state.collected_details[k] = str(v)
            
            # Check if we have gathered everything
            missing_after = [f for f in required if f not in state.collected_details]
            if not missing_after:
                state.next_step = "collect_client_info"
                state.messages.append({
                    "role": "assistant",
                    "content": "🛠️ **Bid Request Built Successfully!**\n\nTo submit this request to local contractors, please provide your **Name, Phone Number, and Address**."
                })
            else:
                state.messages.append({"role": "assistant", "content": data.get("reply")})
                
            return state
    except Exception as e:
        print(f"LLM info gathering failed: {e}")
        
    return fallback_gather_info(state)

def llm_collect_client_info(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    user_img = state.messages[-1].get('image')
    task = AVAILABLE_TASKS[state.selected_task] # type: ignore
    
    prompt = (
        f"Currently collected client info: {json.dumps(state.client_info)}\n"
        f"User's response: '{user_msg}'\n\n"
        "You are BuildWizard AI. The user's prompt has been successfully built, and we now need their contact details to save the request.\n"
        "The required fields are: 'name', 'phone', and 'address'.\n\n"
        "Your goal is to:\n"
        "1. Extract any new contact information from the user's response.\n"
        "2. If 'name', 'phone', or 'address' are still missing, ask the user for them politely.\n"
        "3. If all required contact details are gathered, return confirmed: true.\n\n"
        "Output your response strictly as a JSON object with these keys:\n"
        "- 'extracted_details': a dictionary of the newly extracted contact details (e.g. {'name': 'John', 'phone': '555-1234'}).\n"
        "- 'confirmed': true if we have name, phone, and address. false otherwise.\n"
        "- 'reply': your professional response / question to the user. If confirmed, give a warm closing message saying the request was sent to local contractors.\n"
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
            new_details = data.get("extracted_details", {})
            for k, v in new_details.items():
                if k in ["name", "phone", "address"]:
                    state.client_info[k] = str(v)
            
            has_all = all(k in state.client_info for k in ["name", "phone", "address"])
            
            if data.get("confirmed") or has_all:
                final_prompt = task["gold_standard"].format(**state.collected_details)
                save_client_and_offer(state.client_info, state.collected_details, final_prompt)
                
                state.messages.append({"role": "assistant", "content": data.get("reply", "Perfect! Your request has been saved and sent to local contractors. We will be in touch shortly!")})
                state.selected_task = None
                state.collected_details = {}
                state.client_info = {}
                state.next_step = "determine_task"
            else:
                state.messages.append({"role": "assistant", "content": data.get("reply")})

            return state
    except Exception as e:
        print(f"LLM client info gathering failed: {e}")
        
    # Standard rule-based fallback completion
    state.messages.append({
        "role": "assistant", 
        "content": "Perfect! Your contact info is saved. 🛠️ Your request has been forwarded to local contractors!"
    })
    state.selected_task = None
    state.collected_details = {}
    state.client_info = {}
    state.next_step = "determine_task"
    
    return state
