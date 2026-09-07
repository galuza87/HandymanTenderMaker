from backend.llm import get_llm
from backend.v1.agents.base import GraphState, DataValidatorOutput
from langchain_core.messages import AIMessage

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
