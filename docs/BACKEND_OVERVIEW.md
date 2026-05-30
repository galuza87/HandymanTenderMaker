# HandymanTenderMaker Backend Overview

## 🎯 Simple Explanation (Non-Technical)

This is the **brain** of an AI chatbot called **BuildWizard AI** that helps people request handyman services, construction quotes, or contractor bids. It:

1. **Talks to users** via a chat interface
2. **Asks smart questions** to understand what they need (e.g., "Is this a plumbing issue?")
3. **Collects their contact info** (name, phone, address)
4. **Saves their request** and sends it to local contractors
5. **Uses AI** (LM Studio) to have intelligent conversations, with a backup rule-based system if AI isn't available

---

## 🏗️ Technical Breakdown: Objects & Procedures

### **Core Objects:**

| Object | Purpose |
|--------|---------|
| **AgentState** | Stores conversation data: messages, selected task, collected details, client info |
| **ChatRequest** | What the user sends: message + optional image |
| **ChatResponse** | What the bot replies with: response text + task type + collected details |
| **AVAILABLE_TASKS** | Dictionary of 3 task types: Quote Request, Tender Request, Handyman Request |

### **Main Procedures (Functions):**

| Function | What It Does |
|----------|-------------|
| `get_llm()` | Checks if LM Studio AI is running; if yes, returns AI client |
| `determine_task()` | Rule-based: reads keywords to guess what user wants |
| `llm_determine_task()` | AI version: uses LLM to classify user intent |
| `gather_info()` | Rule-based: asks questions to fill in missing details |
| `llm_gather_info()` | AI version: intelligently extracts info from user responses |
| `llm_collect_client_info()` | AI version: extracts name, phone, address |
| `get_matching_contractors_text()` | Searches DB for contractors matching the job |
| `wizard_workflow()` | Main router: decides which step to run next |
| **REST API endpoints** | `/api/categories`, `/api/contractors`, `/chat` |

---

## 📊 Flow Diagram

```mermaid
graph TD
    A["👤 USER SENDS MESSAGE<br/>(via /chat endpoint)"] --> B{Check if LM Studio<br/>AI available?}
    
    B -->|Yes| C["Use AI/LLM<br/>for intelligence"]
    B -->|No| D["Use Rule-Based<br/>Logic"]
    
    C --> E{Task selected?<br/>handyman/quote/tender}
    D --> E
    
    E -->|No - Step 1| F["🎯 DETERMINE TASK<br/>Classify user intent<br/>Ask what they need"]
    E -->|Yes - Step 2| G["📝 GATHER DETAILS<br/>Ask for:<br/>- Project type<br/>- Scope/Materials<br/>- Deadline"]
    
    F --> H{All required<br/>details<br/>collected?}
    G --> H
    
    H -->|No| I["❓ Ask more questions"]
    I --> H
    
    H -->|Yes - Step 3| J["👤 COLLECT CLIENT INFO<br/>Ask for:<br/>- Name<br/>- Phone<br/>- Address"]
    
    J --> K{All contact info<br/>collected?}
    
    K -->|No| L["❓ Ask missing details"]
    L --> K
    
    K -->|Yes| M["💾 SAVE & SEND<br/>- Save to Database<br/>- Send to Contractors<br/>- Reset Session"]
    
    M --> N["🔄 Back to Step 1<br/>Ready for new task"]
    N --> E
    
    style A fill:#e1f5ff
    style M fill:#c8e6c9
    style F fill:#fff9c4
    style G fill:#fff9c4
    style J fill:#fff9c4
```

---

## 📝 Appendix: Libraries Used

| Library | Purpose |
|---------|---------|
| **FastAPI** | Web framework for creating REST APIs |
| **Pydantic** | Data validation & type checking (BaseModel classes) |
| **CORSMiddleware** | Allows frontend (different domain) to call backend |
| **httpx** | Makes HTTP requests (checks if LM Studio is running) |
| **langchain_openai** | AI client to communicate with LM Studio LLM |
| **json** | Parse/format JSON responses from LM |
| **re** | Regular expressions (extract JSON from LM responses) |
| **python-dotenv** | Load environment variables from `.env` file |
| **pyodbc/ODBC** | Connect to MS SQL Server database |
| **uvicorn** | ASGI server to run FastAPI app |

---

## 🔌 Database Connection
The app connects to **Microsoft SQL Server** with two connection methods:
- **SQL Server Authentication** (username/password)
- **Windows Authentication** (trusted connection)

Default database: `HandymanDB`
