from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os 
import sys
# Add parent directory of 'backend' to python path so internal imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# --- Internal imports             --- #
from backend.v1.models import ChatRequest, ChatResponse, AgentState, LoginRequest, RegisterRequest, UpdateClientRequest
from backend.v1.engine import sessions
from backend.v1.db.database import get_all_categories_with_subs, get_all_contractors, search_categories_and_subs, insert_prompt_log, init_db, get_client_by_phone, create_client, get_projects_by_client_id, update_client
api_key = os.getenv("LANGSMITH_API_KEY")

# --- Harness algorithm version    --- #
ALGORITHM_VERSION = os.getenv('ALGORITHM_VERSION', 'v1') # Get the active version or default to v1
if ALGORITHM_VERSION == 'v1':
    from backend.v1.engine import Engine
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
    # see what this session is all about 
    if session_id not in sessions:
        sessions[session_id] = AgentState(messages=[], session_id=session_id, ip_address=client_ip)
        
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
        identified_categories=new_state.identified_categories,
        sub_tasks=new_state.sub_tasks,
        collected_details=new_state.collected_details
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
