from pydantic import BaseModel, Field
from typing import Optional, Literal
from typing import TypedDict
from backend.models import CategorizerDecisionClass

# --- LangGraph State Definition ---
class DataValidatorOutput(BaseModel):
    status: Literal["enough_information", "not_enough_information"] = Field(description="Return 'enough_information' if the request contains enough information to determine if one or multiple types of contractors are needed (e.g., 'I need a plumber to fix a leak' is enough). Return 'not_enough_information' otherwise.")
    missing_context: Optional[str] = Field(description="If status is 'not_enough_information', specify what context is missing to ask the user.")

class CategorizerDecisionLLMOutput(BaseModel):
    decision: Literal["single", "multiple"] = Field(description="Return 'single' if ONE trade is mentioned. Return 'multiple' if MORE THAN ONE trade is needed.")

class GraphState(TypedDict, total=False):
    messages: list
    identified_categories: list
    client_info: dict
    next_agent: str
    ip_address: str
    session_id: str
    user_id: Optional[int]
    CategorizerDecision: CategorizerDecisionClass
    project_id: Optional[int]
    is_finished: bool
