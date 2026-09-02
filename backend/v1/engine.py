import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# --- Internal imports             ---
from backend.v1.models import AgentState
from backend.v1.graph import app

# --- Engine Wrapper ---
class Engine:
    """The Algorithm engine - Multi-Agent LangGraph version"""
    
    def __init__(self, llm=None):
        pass

    def process(self, state: AgentState) -> AgentState:
        lc_messages = []
        for msg in state.messages:
            if msg.get("role") == "user":
                lc_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                kwargs = {"content": msg.get("content", "")}
                if "tool_calls" in msg:
                    kwargs["tool_calls"] = msg["tool_calls"]
                lc_messages.append(AIMessage(**kwargs))
            elif msg.get("role") == "system":
                lc_messages.append(SystemMessage(content=msg.get("content", "")))
            elif msg.get("role") == "tool":
                lc_messages.append(ToolMessage(content=msg.get("content", ""), tool_call_id=msg.get("tool_call_id", "unknown")))
            else:
                lc_messages.append(HumanMessage(content=str(msg.get("content", ""))))
                
        input_state = {
            "messages": lc_messages,
            "identified_categories": state.identified_categories,
            "sub_tasks": state.sub_tasks,
            "client_info": state.client_info,
            "next_agent": state.next_step,
            "ip_address": state.ip_address,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "CategorizerDecision": state.CategorizerDecision if hasattr(state, 'CategorizerDecision') and state.CategorizerDecision else None,
            "project_id": state.project_id,
            "is_finished": getattr(state, "is_finished", False)
        }
        
        logging.info(f"--- [Engine Process Start] next_step: {state.next_step} ---")
        
        final_state = app.invoke(input_state)  # type: ignore
        
        logging.info(f"--- [Engine Process End] returned next_agent: {final_state.get('next_agent')} ---")
        # todo andrew need to handle it properly 
        new_messages = []
        for msg in final_state["messages"]:
            if isinstance(msg, HumanMessage):
                new_messages.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                d = {"role": "assistant", "content": str(msg.content)}
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    d["tool_calls"] = msg.tool_calls  # type: ignore
                new_messages.append(d)
            elif isinstance(msg, SystemMessage):
                new_messages.append({"role": "system", "content": str(msg.content)})
            elif isinstance(msg, ToolMessage):
                new_messages.append({"role": "tool", "content": str(msg.content), "tool_call_id": getattr(msg, "tool_call_id", "unknown")})
            else:
                if isinstance(msg, dict):
                    new_messages.append({"role": msg.get("role", "unknown"), "content": str(msg.get("content", ""))})
                else:
                    new_messages.append({"role": msg.type if hasattr(msg, "type") else "unknown", "content": str(getattr(msg, "content", ""))})
        
        state.messages = new_messages
        state.next_step = final_state.get("next_agent", "DataValidator")
        
        if "sub_tasks" in final_state:
            state.sub_tasks = final_state["sub_tasks"]
        if "CategorizerDecision" in final_state and final_state["CategorizerDecision"]:
            state.CategorizerDecision = final_state["CategorizerDecision"]
        else:
            state.CategorizerDecision = None
            
        if "project_id" in final_state and final_state["project_id"]:
            state.project_id = final_state["project_id"]
        else:
            state.project_id = None
            
        if "is_finished" in final_state:
            state.is_finished = final_state["is_finished"]
        
        return state
