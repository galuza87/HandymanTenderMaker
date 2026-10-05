from backend.llm import get_llm
from backend.v1.agents.base import GraphState, DataValidatorOutput
from langchain_core.messages import AIMessage
from backend.v1.eval import data_validator_judge

def data_validator_node(state: GraphState) -> dict:
    """Determines whether the incoming request has enough information to proceed.

    Args:
        state: The current graph state. Reads `state["messages"]` for the
            conversation so far.

    Returns:
        A dict with `next_agent` set to "DataValidator" (pause, awaiting the
        user's reply) if more information is needed, or "Categorizer" if the
        request is clear enough to proceed. When looping back, also includes
        an updated `messages` list with the clarifying question appended. On
        an internal error, defaults to advancing to "Categorizer" rather than
        blocking the conversation.

    Note:
        Any change to this node's decision logic must be reflected in
        `eval/data_validator_judge.py`'s SYSTEM_PROMPT -- the judge's
        definition of a correct decision is otherwise not the same as
        the node's, and its scores will silently drift out of sync.
    """
    
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

        # Fire the online judge with the node's real decision.
        data_validator_judge.maybe_evaluate_async(state.get("messages", []), parsed.status, state.get("session_id"))

        has_enough_data = parsed.status == "enough_information"
        missing_context = parsed.missing_context or "Could you provide more details about the scope of work and the area involved?"
        
        if not has_enough_data:
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
