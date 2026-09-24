import json
from openai import OpenAI
from backend.config import LM_STUDIO_URL, LM_STUDIO_API_KEY
from backend.v1.agents.base import GraphState, CategorizerDecisionLLMOutput
from backend.models import CategorizerDecisionClass
from backend.v1.eval import categorizer_judge

def categorizer_node(state: GraphState) -> dict:
    """Classifies whether the request needs a single trade or multiple trades.

    Args:
        state: The current graph state. Reads `state["messages"]` for the
            conversation so far.

    Returns:
        A dict with `CategorizerDecision` (the parsed single/multiple
        decision) and `next_agent` set to "ContractorCategorizer" for a
        single-trade job or "MultiTaskArchitect" for a multi-trade job. On
        an internal error, defaults to a "multiple" decision and routes to
        "InformationGatherer" rather than guessing a trade.
        
    Note:
        Any change to this node's decision logic must be reflected in
        `eval/categorizer_judge.py`'s SYSTEM_PROMPT -- the judge's
        definition of a correct decision is otherwise not the same as
        the node's, and its scores will silently drift out of sync.
    """

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

        # Fire the online judge with the node's real decision, not the error-fallback path.
        categorizer_judge.maybe_evaluate_async(state.get("messages", []), result.decision)

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
