from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os 
import os
from dotenv import load_dotenv
load_dotenv()

# --- Internal imports             --- #
from backend.v1.models import ChatRequest, ChatResponse, AgentState
from backend.v1.engine import sessions
from backend.v1.db.database import get_all_categories_with_subs, get_all_contractors, search_categories_and_subs, insert_prompt_log, save_client_and_offer
api_key = os.getenv("LANGSMITH_API_KEY")

# --- Harness algorithm version    --- #
ALGORITHM_VERSION = os.getenv('ALGORITHM_VERSION', 'v1') # Get the active version or default to v1
if ALGORITHM_VERSION == 'v1':
    from backend.v1.engine import Engine
else:
    raise ValueError(f"Unknown version: {ALGORITHM_VERSION}")

engine = Engine()

# --- APP                          --- #
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REST APIs for Categories and Contractors --- #
@app.get("/api/categories")
def get_categories():
    """
    Fetches all major categories and subcategories directly from the MS SQL Server database.
    """
    try:
        return get_all_categories_with_subs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

@app.get("/api/contractors")
def get_contractors():
    """
    Fetches all contractors directly from the MS SQL Server database.
    """
    try:
        return get_all_contractors()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch contractors: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    session_id = req.session_id
    client_ip = request.client.host if request.client else "unknown"
    
    if session_id not in sessions:
        sessions[session_id] = AgentState(messages=[], ip_address=client_ip)
        
    state = sessions[session_id]
    state.ip_address = client_ip
    
    msg_data = {"role": "user", "content": req.message}
    if req.image:
        msg_data["image"] = req.image
        
    state.messages.append(msg_data)
    
    new_state = engine.process(state)
    sessions[session_id] = new_state
    
    last_message = new_state.messages[-1].get('content', '')
    return ChatResponse(
        reply=last_message,
        selected_task=new_state.selected_task,
        collected_details=new_state.collected_details
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
