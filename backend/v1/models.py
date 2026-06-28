from pydantic import BaseModel
from typing import List, Dict, Optional, Any

# --- Classes                      ---
class ChatRequest(BaseModel):
    message: str
    session_id: str
    image: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    selected_task: Optional[str] = None
    collected_details: Dict[str, str] = {}

# Graph State 
class AgentState(BaseModel):
    messages: List[Dict[str, Any]]
    selected_task: Optional[str] = None
    collected_details: Dict[str, str] = {}
    client_info: Dict[str, str] = {}
    next_step: str = "determine_task"
    ip_address: Optional[str] = None