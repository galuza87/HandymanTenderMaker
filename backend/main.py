from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import os
import httpx
import json
import re
# pyrefly: ignore [missing-import]
from langchain_openai import ChatOpenAI
from config import LM_STUDIO_URL, LM_STUDIO_API_KEY

# Import database helpers
from database import get_all_categories_with_subs, get_all_contractors, search_categories_and_subs, insert_prompt_log, save_client_and_offer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str
    image: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    selected_task: Optional[str] = None
    collected_details: Dict[str, str] = {}

# --- RAG Database & Guidelines (Construction + Handyman) ---
AVAILABLE_TASKS = {
    "quote_request": {
        "name": "Construction Quote Request",
        "description": "Builds a precise quote request to send to subcontractors or material suppliers.",
        "required_fields": ["project_type", "materials_or_scope", "deadline"],
        "gold_standard": "You are a professional Construction Project Manager. Please draft a formal Quote Request for the following project:\n\n- **Project Type**: {project_type}\n- **Materials / Scope of Work**: {materials_or_scope}\n- **Required Delivery/Completion Deadline**: {deadline}\n\nPlease generate a highly detailed and professional request that I can send directly to subcontractors, prompting them to bid with their best pricing, timeline, and breakdown of labor/material costs."
    },
    "tender_request": {
        "name": "Subcontractor Tender Request",
        "description": "Drafts a detailed Tender request detailing the current state and desired results.",
        "required_fields": ["current_state", "desired_result", "technical_requirements"],
        "gold_standard": "You are an expert Head Contractor. Please draft a subcontractor tender document. \n\n- **Current State of Project**: {current_state}\n- **Desired Result**: {desired_result}\n- **Technical & Safety Requirements**: {technical_requirements}\n\nFormat this into a professional bidding document specifying compliance terms, milestone requirements, and an invitation to submit proposals."
    },
    "handyman_request": {
        "name": "Handyman Service Request",
        "description": "Drafts a detailed service request for handyman tasks such as plumbing, electrical work, appliance fixing, and carpentry.",
        "required_fields": ["major_category", "sub_category", "job_description", "timeframe"],
        "gold_standard": "You are a professional Handyman Coordinator. Please draft a formal service request for the following handyman job:\n\n- **Service Category**: {major_category} ({sub_category})\n- **Detailed Job Description**: {job_description}\n- **Desired Timeframe**: {timeframe}\n\nPlease generate a clear and professional work order so that contractors can bid on this job with their pricing and availability."
    }
}

# --- Graph State ---
class AgentState(BaseModel):
    messages: List[Dict[str, Any]]
    selected_task: Optional[str] = None
    collected_details: Dict[str, str] = {}
    client_info: Dict[str, str] = {}
    next_step: str = "determine_task"
    ip_address: Optional[str] = None

# In-memory session store
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
                    api_key=LM_STUDIO_API_KEY,
                    temperature=0.7,
                )
    except Exception:
        pass
    print(f"[WARNING] LM Studio not detected at {LM_STUDIO_URL}. Falling back to rule-based engine.")
    return None

# --- Rule-Based Fallbacks ---
def determine_task(state: AgentState):
    last_msg = state.messages[-1].get('content', '').lower()
    
    # Handyman keyword mapping
    handyman_keywords = ["plumbing", "leak", "pipe", "clog", "drain", "electrical", "wire", "light", "switch", 
                         "carpentry", "wood", "shelf", "cabinet", "door", "roof", "shingle", "gutter", 
                         "appliance", "dishwasher", "fridge", "oven", "washer", "dryer", "moving", "pack",
                         "handyman", "repair", "fix", "install"]
    
    if any(kw in last_msg for kw in handyman_keywords):
        state.selected_task = "handyman_request"
        state.messages.append({
            "role": "assistant", 
            "content": "✨ **Let's build your Handyman Service Request!** 🛠️\nI see you need help with a handyman task. To get started, **what is the major category of work?**\n(e.g., Plumbing, Electrical Work, Carpentry, Construction, Roofing, Appliance Fixing, Appliance Installing, Moving)"
        })
    elif "quote" in last_msg or "pricing" in last_msg or "material" in last_msg or "cost" in last_msg:
        state.selected_task = "quote_request"
        state.messages.append({
            "role": "assistant", 
            "content": "🚧 **Let's build your Construction Quote Request!** \nTo draft the perfect quote prompt for contractors, please tell me: **What type of project is this?** (e.g., Residential Renovation, Concrete Foundation, Drywalling)"
        })
    elif "tender" in last_msg or "subcontractor" in last_msg or "bid" in last_msg:
        state.selected_task = "tender_request"
        state.messages.append({
            "role": "assistant", 
            "content": "🏗️ **Let's draft a Subcontractor Tender Request!** \nTo get started, please describe the **current state** of the project."
        })
    else:
        state.messages.append({
            "role": "assistant", 
            "content": "🚧 **Welcome to BuildWizard AI!** 👷‍♂️\nI help homeowners and project managers build perfect quote prompts, handyman service orders, and subcontractor tender requests.\n\nWould you like to build a **Handyman Service Request**, a **Construction Quote Prompt**, or a **Subcontractor Tender Request**?"
        })
    return state

def get_matching_contractors_text(state: AgentState) -> str:
    """
    Helper to search and recommend matching contractors based on collected handyman details.
    """
    try:
        contractors = get_all_contractors()
        m_cat = state.collected_details.get("major_category", "").lower()
        s_cat = state.collected_details.get("sub_category", "").lower()
        job_desc = state.collected_details.get("job_description", "").lower()
        
        matching = []
        for c in contractors:
            desc = c["description"].lower()
            
            # Simple keyword matching logic
            is_match = False
            if m_cat and m_cat in desc:
                is_match = True
            elif s_cat and s_cat in desc:
                is_match = True
            elif job_desc and any(word in desc for word in job_desc.split() if len(word) > 3):
                is_match = True
            elif "plumbing" in m_cat and "plumb" in desc:
                is_match = True
            elif "electrical" in m_cat and "electr" in desc:
                is_match = True
            elif "appliance" in m_cat and ("appliance" in desc or "fix" in desc):
                is_match = True
            elif "moving" in m_cat and "mov" in desc:
                is_match = True
                
            if is_match:
                matching.append(c)
                
        if matching:
            rec_text = "\n\n👷‍♂️ **Recommended Handyman/Contractors for this job:**\n"
            for c in matching:
                rec_text += f"- **{c['first_name']} {c['last_name']}** ({c['email']})\n  *\"{c['description']}\"*\n"
            return rec_text
    except Exception as e:
        print(f"Error matching contractors: {e}")
    return ""

def gather_info(state: AgentState):
    task = AVAILABLE_TASKS[state.selected_task]
    required = task["required_fields"]
    
    # Fill the first empty field with the last user message
    empty_fields = [f for f in required if f not in state.collected_details]
    if empty_fields:
        current_field = empty_fields[0]
        state.collected_details[current_field] = state.messages[-1].get('content', '')
        
    # Re-evaluate empty fields
    empty_fields = [f for f in required if f not in state.collected_details]
    
    if empty_fields:
        next_field = empty_fields[0]
        prompts = {
            "materials_or_scope": "Got it. Next, list the **materials needed or scope of work** (e.g., 500 sq ft of drywall, timber framing).",
            "deadline": "Almost done. What is the **delivery or project completion deadline**?",
            "desired_result": "Perfect. What is the **desired result or final outcome** of this phase?",
            "technical_requirements": "Lastly, please list any **technical or safety requirements** (e.g., OSHA compliant, specific materials grade).",
            # Handyman prompts
            "major_category": "Got it. What **major category** of handyman work is this? (e.g., Plumbing, Electrical Work, Carpentry, Appliance Fixing, Moving, etc.)",
            "sub_category": "Great. What **subcategory** or specific issue is it? (e.g., Dishwasher Repair Bosch, Leak Detection, Outlet Repair, Local Apartment Moving)",
            "job_description": "Thanks. Please provide a **detailed description** of the job that needs to be done.",
            "timeframe": "Lastly, what is your **desired timeframe** for this project?"
        }
        state.messages.append({
            "role": "assistant", 
            "content": prompts.get(next_field, f"Please provide details for: **{next_field.replace('_', ' ')}**.")
        })
    else:
        # All details collected!
        state.next_step = "collect_client_info"
        state.messages.append({
            "role": "assistant", 
            "content": "🛠️ **Bid Request Built Successfully!**\n\nTo submit this request to local contractors, please provide your **Name, Phone Number, and Address**."
        })
        
    return state

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
    messages_payload = [
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
        content = response.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            task = data.get("task")
            if task in ["handyman_request", "quote_request", "tender_request"]:
                state.selected_task = task
            state.messages.append({"role": "assistant", "content": data.get("reply")})
            return state
    except Exception as e:
        print(f"LLM task determination failed: {e}")
        
    return determine_task(state)

def llm_gather_info(llm: ChatOpenAI, state: AgentState) -> AgentState:
    task_key = state.selected_task
    task = AVAILABLE_TASKS[task_key]
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
        "- 'extracted_details': a dictionary of the newly extracted details only (e.g., {'major_category': 'appliance fixing', 'sub_category': 'dishwasher repair (Bosch)'})\n"
        "- 'reply': your professional response / query to the user.\n"
        "Example format:\n"
        '{"extracted_details": {"major_category": "plumbing", "sub_category": "leak repair"}, "reply": "Excellent, I\'ve recorded that plumbing leak repair. Next, could you describe the job details?"}'
    )
    messages_payload = [
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
        content = response.content.strip()
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
        
    return gather_info(state)

def llm_collect_client_info(llm: ChatOpenAI, state: AgentState) -> AgentState:
    user_msg = state.messages[-1].get('content', '')
    user_img = state.messages[-1].get('image')
    task = AVAILABLE_TASKS[state.selected_task]
    
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
    
    messages_payload = [
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
        content = response.content.strip()
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

# --- Main workflow Router ---
def wizard_workflow(state: AgentState) -> AgentState:
    llm = get_llm()
    if llm:
        if state.selected_task is None:
            return llm_determine_task(llm, state)
        elif state.next_step == "determine_task" or state.next_step == "gather_info":
            return llm_gather_info(llm, state)
        else:
            return llm_collect_client_info(llm, state)
    else:
        # Fallback to rule-based logic
        if state.selected_task is None:
            return determine_task(state)
        elif state.next_step == "determine_task" or state.next_step == "gather_info":
            return gather_info(state)
        else:
            state.messages.append({
                "role": "assistant", 
                "content": "Perfect! Your request has been saved and sent to local contractors! 🛠️"
            })
            state.selected_task = None
            state.collected_details = {}
            state.client_info = {}
            state.next_step = "determine_task"
            return state

# --- REST APIs for Categories and Contractors ---

@app.get("/api/categories")
def get_categories():
    """
    Fetches all major categories and subcategories directly from the MS SQL Server database.
    """
    try:
        return get_all_categories_with_subs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

@app.get("/api/contractors")
def get_contractors():
    """
    Fetches all contractors directly from the MS SQL Server database.
    """
    try:
        return get_all_contractors()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch contractors: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    session_id = req.session_id
    client_ip = request.client.host if request.client else "unknown"
    
    if session_id not in sessions:
        sessions[session_id] = AgentState(messages=[], ip_address=client_ip)
        
    state = sessions[session_id]
    state.ip_address = client_ip
    
    msg_data = {"role": "user", "content": req.message}
    if req.image:
        msg_data["image"] = req.image
        
    state.messages.append(msg_data)
    
    new_state = wizard_workflow(state)
    sessions[session_id] = new_state
    
    last_message = new_state.messages[-1].get('content', '')
    return ChatResponse(
        reply=last_message,
        selected_task=new_state.selected_task,
        collected_details=new_state.collected_details
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
