from backend.llm import get_llm
from backend.v1.agents.base import GraphState
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent as create_agent

def information_gatherer_node(state: GraphState) -> dict:
    llm = get_llm()
    system_prompt = (
        "You are the Information Gatherer. The user's request is too vague for us to categorize.\n"
        "Ask ONE clarifying question to understand exactly what they need fixed or built.\n"
        "DO NOT attempt to assign trades, just ask the question. End your response with ALL_DONE."
    )
    
    agent = create_agent(model=llm, tools=[], prompt=system_prompt)
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        if isinstance(content_str, str) and "ALL_DONE" in content_str:
            clean_content = content_str.replace("ALL_DONE", "").strip()
            if hasattr(last_message, 'content'):
                result["messages"][-1] = AIMessage(content=clean_content)
            else:
                result["messages"][-1]["content"] = clean_content
                
        return {
            "messages": result["messages"], 
            "next_agent": "Categorizer" # Next loop should start at categorizer again
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"InformationGatherer error: {e}"}]}
