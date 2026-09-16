from backend.v1.agents.base import GraphState
from backend.db import get_all_categories, create_project_prompt
from langchain_core.messages import AIMessage

# Try to import sentence-transformers, fail gracefully if not ready yet
try:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    embedder = None

def tender_creator_node(state: GraphState) -> dict:
    project_id = state.get("project_id")
    confirmed_job_description = state.get("confirmed_job_description")
    
    if not project_id:
        return {"messages": state["messages"] + [{"role": "assistant", "content": "TenderCreator error: Missing project_id."}], "next_agent": "Categorizer"}
    
    if not confirmed_job_description:
        return {"messages": state["messages"] + [{"role": "assistant", "content": "TenderCreator error: Missing confirmed job description."}], "next_agent": "Categorizer"}
        
    new_messages = list(state["messages"])
    
    # Generate embedding for the confirmed document
    embedding = None
    if embedder:
        try:
            embedding = embedder.encode(confirmed_job_description).tolist()
        except Exception as e:
            print(f"Error generating embedding: {e}")
            
    # TODO: In the future, fetch a "gold standard" document by major_category_id from the DB
    # and pass it to an LLM if we want to do further enhancement. For now, the confirmed
    # document IS the final tender.
            
    identified_categories = state.get("identified_categories", [])
    if not identified_categories:
        cat_id = 1
        try:
            categories = get_all_categories()
            if categories:
                cat_id = categories[0]['id']
        except Exception:
            pass
        identified_categories = [{"category_id": cat_id}]
        
    for cat in identified_categories:
        cat_id = cat.get("category_id")
        create_project_prompt(
            project_id=project_id, 
            category_id=cat_id, 
            prompt_text=confirmed_job_description,
            embedding=embedding
        )
        
    new_messages.append(AIMessage(content=f"Tenders have been finalized and saved for {len(identified_categories)} categories!"))
    
    return {
        "messages": new_messages,
        "next_agent": "Categorizer",
        "is_finished": True
    }
