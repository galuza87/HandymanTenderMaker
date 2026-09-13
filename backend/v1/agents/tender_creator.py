from backend.llm import get_llm
from backend.v1.agents.base import GraphState
from backend.db import get_all_categories, create_project_prompt
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent as create_agent

def tender_creator_node(state: GraphState) -> dict:
    llm = get_llm()
    project_id = state.get("project_id")
    prompts = state.get("prompts", [])
    
    if not project_id:
        return {"messages": state["messages"] + [{"role": "assistant", "content": "TenderCreator error: Missing project_id."}], "next_agent": "Categorizer"}
        
    system_prompt = (
        "You are the Tender Creator. Based on the conversation history, write a clear, professional Tender prompt (job description) that will be shown to contractors.\n"
        "Do not include greetings. Just output the tender text."
    )
    
    new_messages = list(state["messages"])
    
    if len(prompts) == 0:
        agent = create_agent(model=llm, tools=[], prompt=system_prompt)
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        tender_text = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        cat_id = None
        try:
            categories = get_all_categories()
            if categories:
                cat_id = categories[0]['id']
        except Exception:
            cat_id = 1
            
        if state.get("identified_categories") and len(state.get("identified_categories")) > 0:
            cat_id = state.get("identified_categories")[0].get("category_id", cat_id)
            
        create_project_prompt(project_id=project_id, category_id=cat_id, prompt_text=tender_text)
        new_messages.append(AIMessage(content="Your tender has been created and sent to contractors."))
    else:
        new_messages.append(AIMessage(content="Creating multiple tenders for your project..."))
        for task in prompts:
            prompt = system_prompt + f"\nSpecifically, write the tender for this prompt: {task.get('prompt_text')}"
            agent = create_agent(model=llm, tools=[], prompt=prompt)
            result = agent.invoke({"messages": state["messages"]})
            last_message = result["messages"][-1]
            tender_text = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
            
            cat_id = task.get('category_id')
            if not cat_id:
                try:
                    categories = get_all_categories()
                    if categories:
                        cat_id = categories[0]['id']
                except Exception:
                    cat_id = 1
            create_project_prompt(project_id=project_id, category_id=cat_id, prompt_text=tender_text)
            
        new_messages.append(AIMessage(content="All tenders have been created and sent to the respective contractors."))
        
    return {
        "messages": new_messages,
        "next_agent": "Categorizer",
        "is_finished": True
    }
