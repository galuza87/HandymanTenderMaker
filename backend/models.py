from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Literal

# --- Classes                      ---
class CategorizerDecisionClass(BaseModel):
    decision: Literal["single", "multiple"]

class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: Optional[int] = None
    image: Optional[str] = None

class LoginRequest(BaseModel):
    phone: str

class RegisterRequest(BaseModel):
    phone: str
    name: str
    last_name: str
    email: str
    address: str
    additional_phone: Optional[str] = None

class UpdateClientRequest(BaseModel):
    name: str
    last_name: str
    email: str
    address: str
    additional_phone: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    identified_categories: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []
    collected_details: Dict[str, str] = {}

# Graph State 
class AgentState(BaseModel):
    messages: List[Dict[str, Any]]
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    identified_categories: List[Dict[str, Any]] = [] # e.g., [{"category_id": 1, "name": "plumbing"}]
    prompts: List[Dict[str, Any]] = [] # e.g., [{"id": 1, "category": "plumbing", "prompt_text": "fix pipe"}]
    collected_details: Dict[str, str] = {}
    client_info: Dict[str, str] = {}
    next_step: str = "determine_number_of_subtasks" # Start at determine_number_of_subtasks
    ip_address: Optional[str] = None
    CategorizerDecision: Optional[CategorizerDecisionClass] = None
    project_id: Optional[int] = None
    is_finished: bool = False