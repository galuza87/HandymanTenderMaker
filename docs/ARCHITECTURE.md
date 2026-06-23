# Agentic Tender Wizard: System Architecture

**System design document.** Read this to understand how the system is designed, the flow of tender creation, pricing evaluation, and the architectural choices made.

---

## 1. High-Level Overview

This system is an AI-powered agent designed to make private client tenders seamless, highly consistent, and efficient. It manages the entire lifecycle of a tender request across four primary steps:

1. **Step 1: Tender Creation Conversation**: The agent conducts an interactive conversation with the client to extract required details. It uses this information to draft a formal tender document based on a predefined **"Gold Standard"** template (e.g., handyman request, construction quote request, or subcontractor tender).
2. **Step 2: Similar Tender Matching & Gap Analysis**: Once the tender document is drafted, the system embeds it into a vector. It then searches previous tenders stored in the database using a **dedicated vector column**. Because historical tenders contain critical requirement data that past contractors needed, the agent performs a gap analysis on the current document to verify that the client is not missing these exact same requirements.
3. **Step 3: Contractor Pricing, Evaluation, & Error Loops**: The verified draft tender is dispatched to relevant contractors. During this stage, contractors evaluate the project and provide their pricing and any additional logistical details. If a tender is fundamentally inaccurate and cannot be priced, the contractor flags the critical missing input. This routes the tender back through the server to the client's conversation loop to gather the missing data before proceeding.
4. **Step 4: Bid Compilation & Delivery**: The agent aggregates the tender's job description alongside the bids (prices and provided details) and profiles of each participating contractor. This is formatted into a unified, easy-to-read report that is sent directly back to the client for final evaluation and selection.

---

## 2. System Architecture Diagram

```text
┌────────────────┐                                       ┌───────────────┐
│                │      (1) User Input / Answers         │               │
│                │──────────────────────────────────────▶│  LangGraph /  │
│                │                                       │   LangChain   │
│                │◀──────────────────────────────────────│ Orchestrator  │
│                │      (2) Clarification Questions      │    & LLM      │
│     Client     │                                       └───────┬───────┘
│                │◀────────────────┐                             │
│                │ (5) Ask client  │                             │ (3) Draft Tender Created
│                │ for missing data│                             │
│                │                 │                             ▼
│                │    ┏━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│                │    ┃             TENDER GAP ANALYSIS (EMPHASIS)          ┃
│                │    ┃ 1. Embed current draft tender.                      ┃
│                │    ┃ 2. Query Relational DB (Vector Column).             ┃
│                │    ┃ 3. Retrieve closest past tenders.                   ┃
│                │    ┃ 4. Cross-reference past contractor requirements.    ┃
│                │    ┃ 5. Identify data missing in the current draft.      ┃
│                │    ┗━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
│                │                            │
│                │                            │ (6) Verified Draft Tender
│                │                            ▼
│                │           ┌──────────────────────────────────┐
│                │           │          Central Server          │◀────────┐
│                │◀──────────│       (Tender Compilation)       │         │
│ (10) Send      │           └───────┬───────────────────▲──────┘         │ (9) Cannot Price?
│ Compiled       │                   │                   │                │ Flag Critical
│ Tender Back    │                   │ (7) Dispatch      │ (8) Submit     │ Missing Input
│                │                   │     Tender        │     Pricing &  │ (Routes to Client)
│                │                   │                   │     Missing    │
│                │                   │                   │     Data       │
└────────────────┘                   ▼                   │                │
                             ┌───────────────────────────────────┴────────┐ │
                             │             Multiple Contractors           │ │
                             │          (Review, Pricing, Data Input)     ├─┘
                             └────────────────────────────────────────────┘
```

---

## 3. Harness Engineering: Agent Steering (LangGraph & LangChain)

Creating a tender document requires extracting structured, precise information from a non-technical user. To achieve this consistently and with minimal friction:

- **State Management**: We utilize **LangGraph** to build a conversation state machine that guides the LLM through distinct phases (Intent Determination $\rightarrow$ Detail Extraction $\rightarrow$ Client Info Collection $\rightarrow$ Vector Verification).
- **Steered Extraction**: **LangChain** is used to steer the LLM by utilizing structured prompt techniques. The agent matches user answers against specific required fields (e.g., `project_type`, `deadline`, `materials_or_scope`) without repeating confirmation questions.
- **Minimum Confirmation Questions**: Rather than asking *"Did you mean X?"* or *"Do you confirm Y?"* for every detail, the agent infers information implicitly from context and updates the active state (`AgentState.collected_details`). It only asks open-ended clarification questions when a required field is completely missing or highly ambiguous.

---

## 4. Components

### 4.1 FastAPI Server
**Module:** [main.py](file:///c:/Users/User/React/Projects/DynamicPromptWizard/backend/main.py)

- **Purpose**: Exposes API endpoints for chat interactions, contractor list retrievals, category searches, and saving tender offers.
- **Endpoints**:
  - `POST /chat` → Receives messages, updates session state using `wizard_workflow`, and queries the LLM/fallback engine.
  - `GET /api/categories` → Fetches categories and subcategories from SQL Server to help align user intent with system records.
  - `GET /api/contractors` → Lists registered contractors and descriptions.

### 4.2 Embedding & Search Service
- **Purpose**: Generates vector representations of drafted tenders and queries the database for historic matches.
- **Vector Column Integration**: 
  - Instead of deploying an external vector database (like ChromaDB or Pinecone) which adds architectural complexity and infrastructure overhead, the system uses a **dedicated vector column** directly inside the relational database table (`Offer_requests`).
  - Embeddings are computed (e.g., via a lightweight HuggingFace transformer model or LM Studio embedding API) and stored as serialized vector data (or native vector types depending on SQL Server configuration).
  - **Similarity Search**: When a new tender is created in Step 2, its vector is compared against existing tender vectors in the database (either using DB-native vector matching or by loading historical vectors for similarity computation in Python) to extract the most relevant historical contracts.

### 4.3 Database Layer
**Module:** [database.py](file:///c:/Users/User/React/Projects/DynamicPromptWizard/backend/database.py) / [init_db.py](file:///c:/Users/User/React/Projects/DynamicPromptWizard/backend/init_db.py)

> [!NOTE]
> **Database Migration Strategy:** We should start the initial implementation using **SQLite** (with a vector column extension) for simplicity and fast prototyping. As the dataset grows and we require more robust performance, we will test it against **PostgreSQL** (using `pgvector`) and migrate accordingly.

- **Database Engine**: MS SQL Server (`HandymanDB`) *(Pending refactor to SQLite)*.
- **Primary Tables**:
  - `major_category` & `sub_category`: Store categories (e.g., plumbing, electrical) used to match tenders.
  - `contractor`: Stores contractor details, descriptions, and contact info.
  - `Clients`: Stores client contact info collected in Step 3.
  - `Offer_requests` / `Tenders`: Holds the draft text, category labels, deadline, and the **vector column** representing the document embedding.

### 4.4 LLM Inference
**Configuration:** [config.py](file:///c:/Users/User/React/Projects/DynamicPromptWizard/backend/config.py)

- **Local Inference (LM Studio)**: Uses local Mistral-7B GGUF model served on `http://localhost:1234/v1` for full privacy and zero API costs.
- **Fallback Engine**: If LM Studio is not active, the backend defaults to a robust rule-based parser to ensure the application remains functional.

---

## 5. Key Design Decisions & Trade-offs

| Decision | Trade-off | Rationale |
|---|---|---|
| **Vector Column vs. Vector DB** | Less specialized indexing performance vs. significantly lower infrastructure overhead and absolute simplicity | Storing embeddings in a table column avoids running a second database (e.g. ChromaDB) and keeps all transaction data atomic and simple. |
| **LangGraph Orchestration** | Setup overhead of graphs and state vs. deterministic control over LLM conversation | A standard LLM chat easily gets sidetracked. LangGraph ensures the agent sticks to collecting the required parameters for the tender consistently. |
| **Implicit Detail Extraction** | Risk of misinterpreting user input vs. low friction conversation | By extracting parameters in the background rather than checking each one with a confirmation question, we keep the user engaged. |

---

## 6. Request Lifecycle (Steps 1–4)

```
[Client]                      [FastAPI Backend]                 [Database (SQL Server)]           [Contractors]
   │                                  │                                    │                            │
   │ 1. Conversational Chat           │                                    │                            │
   ├─────────────────────────────────>│                                    │                            │
   │                                  │──┐ Extract details &               │                            │
   │                                  │  │ draft tender against            │                            │
   │                                  │  │ Gold Standard template          │                            │
   │                                  │<─┘                                 │                            │
   │                                  │                                    │                            │
   │                                  │ 2. Embed Tender & Search Vectors   │                            │
   │                                  ├───────────────────────────────────>│                            │
   │                                  │<───────────────────────────────────│                            │
   │                                  │ (Retrieve similar past tenders)    │                            │
   │                                  │                                    │                            │
   │                                  │──┐ Run Gap Analysis on             │                            │
   │                                  │  │ missing requirements            │                            │
   │                                  │<─┘                                 │                            │
   │                                  │                                    │                            │
   │                                  │ 3. Dispatch Tender to Contractors  │                            │
   │                                  ├────────────────────────────────────────────────────────────────>│
   │                                  │                                    │                            │
   │                                  │                                    │ 4. Contractor Fills Data   │
   │                                  │                                    │    & Submits Price Bid     │
   │                                  │<────────────────────────────────────────────────────────────────┤
   │                                  │                                    │                            │
   │ 5. Deliver Compiled Bid Summary  │                                    │                            │
   │<─────────────────────────────────│                                    │                            │
```
