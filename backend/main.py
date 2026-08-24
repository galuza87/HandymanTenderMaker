from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os 
import sys
# Add parent directory of 'backend' to python path so internal imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)

# --- Internal imports             --- #
from backend.v1.models import ChatRequest, ChatResponse, AgentState, LoginRequest, RegisterRequest, UpdateClientRequest
from backend.v1.db.database import get_all_categories_with_subs, get_all_contractors, search_categories_and_subs, insert_prompt_log, init_db, get_client_by_phone, create_client, get_projects_by_client_id, update_client, get_client_by_id, get_conversation, save_conversation, get_conversations_by_client_id
api_key = os.getenv("LANGSMITH_API_KEY")

# --- Harness algorithm version    --- #
ALGORITHM_VERSION = os.getenv('ALGORITHM_VERSION', 'v2') # Get the active version or default to v2
if ALGORITHM_VERSION == 'v1':
    from backend.v1.engine import Engine
elif ALGORITHM_VERSION == 'v2':
    from backend.v2.engine import Engine
else:
    raise ValueError(f"Unknown version: {ALGORITHM_VERSION}")
# why do we need init db ?
engine = Engine()
init_db()

# --- APP                          --- #
app = FastAPI()

# --- Include Routers              --- #
from backend.v1.routes.testing import router as testing_router
app.include_router(testing_router, prefix="/api/v1/tests", tags=["Testing"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REST APIs for Auth --- #
@app.post("/api/login")
def login(req: LoginRequest):
    client = get_client_by_phone(req.phone)
    if not client:
        raise HTTPException(status_code=404, detail="Phone number not found")
    return {"message": "Login successful", "client": client}

@app.post("/api/register")
def register(req: RegisterRequest):
    # Check if already exists
    existing = get_client_by_phone(req.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
        
    client_id = create_client(
        name=req.name,
        last_name=req.last_name,
        phone=req.phone,
        additional_phone=req.additional_phone,
        email=req.email,
        address=req.address
    )
    
    if not client_id:
        raise HTTPException(status_code=500, detail="Failed to create user")
        
    client = get_client_by_phone(req.phone)
    return {"message": "Registration successful", "client": client}

@app.get("/api/client/{client_id}/projects")
def get_client_projects(client_id: int):
    try:
        return get_projects_by_client_id(client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/client/{client_id}/conversations")
def get_client_conversations(client_id: int):
    try:
        return get_conversations_by_client_id(client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{session_id}")
def get_conversation_endpoint(session_id: str):
    state_json = get_conversation(session_id)
    if not state_json:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return state_json

@app.put("/api/client/{client_id}")
def update_client_endpoint(client_id: int, req: UpdateClientRequest):
    success = update_client(
        client_id=client_id,
        name=req.name,
        last_name=req.last_name,
        additional_phone=req.additional_phone,
        email=req.email,
        address=req.address
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user")
    return {"message": "Update successful"}

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
    
    # Load session state from DB
    state_dict = get_conversation(session_id)
    if not state_dict:
        state = AgentState(messages=[], session_id=session_id, ip_address=client_ip)
    else:
        if state_dict.get("CategorizerDecision") == {}:
            state_dict["CategorizerDecision"] = None
        state = AgentState(**state_dict)
        
    state.ip_address = client_ip
    if req.user_id is not None:
        state.user_id = req.user_id
        
    if state.user_id is not None and not state.client_info:
        client = get_client_by_id(state.user_id)
        if client:
            state.client_info = {
                "name": f"{client.get('name', '')} {client.get('last_name', '')}".strip(),
                "phone": client.get('phone', ''),
                "address": client.get('address', '') or ''
            }
    
    msg_data = {"role": "user", "content": req.message}
    if req.image:
        msg_data["image"] = req.image
        
    state.messages.append(msg_data)
    old_msg_count = len(state.messages)
    
    new_state = engine.process(state)
    
    # Save session state to DB
    save_conversation(
        session_id=session_id, 
        client_id=new_state.user_id if new_state.user_id else 0, 
        state_json=new_state.model_dump_json(), 
        is_finished=new_state.is_finished
    )
    
    # Gather all non-empty assistant messages generated in this turn
    new_ai_messages = [
        msg.get("content", "") 
        for msg in new_state.messages[old_msg_count:] 
        if msg.get("role") == "assistant" and msg.get("content", "").strip() != ""
    ]
    
    if new_ai_messages:
        reply_text = "\n\n".join(new_ai_messages)
    else:
        # Fallback just in case
        reply_text = new_state.messages[-1].get('content', '') if new_state.messages else ''
        
    return ChatResponse(
        reply=reply_text,
        identified_categories=new_state.identified_categories,
        sub_tasks=new_state.sub_tasks,
        collected_details=new_state.collected_details
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
