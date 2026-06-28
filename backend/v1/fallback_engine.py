# --- Internal imports             ---
from backend.v1.tasks import AVAILABLE_TASKS
from backend.v1.db.database import get_all_contractors
from backend.v1.models import AgentState

# --- Rule-Based Fallbacks ---
def fallback_determine_task(state: AgentState):
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

def fallback_get_matching_contractors_text(state: AgentState) -> str:
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

def fallback_gather_info(state: AgentState):
    task = AVAILABLE_TASKS[state.selected_task] # type: ignore
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

def fallback_collect_client_info(state: AgentState) -> AgentState:
    """Rule-based fallback for collecting contact info"""
    user_msg = state.messages[-1].get('content', '')
    
    # Simple extraction: look for patterns
    missing = []
    if 'name' not in state.client_info:
        missing.append('name')
    if 'phone' not in state.client_info:
        missing.append('phone')
    if 'address' not in state.client_info:
        missing.append('address')
    
    if not missing:
        state.messages.append({
            "role": "assistant",
            "content": "Perfect! Your request has been saved and sent to local contractors! 🛠️"
        })
        state.selected_task = None
        state.collected_details = {}
        state.client_info = {}
        state.next_step = "determine_task"
    else:
        state.messages.append({
            "role": "assistant",
            "content": f"Please provide your {', '.join(missing)}"
        })
    
    return state