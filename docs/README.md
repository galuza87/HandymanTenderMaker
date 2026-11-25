# Agent baesed "Handyman Tender Maker" System

An agent based chat bot system for creation of tenders for house repairs.
The system proactively collects all the needed information from the customer and creates a tender document.
Contractors get notified when a suitable tender arrives to the system, and make their bids or ask for more information, eventualy accepting the tender.
The system implements a self healing mechanism:
each time a new tender is being created it reviews most similar successful tenders for missing information that the contractors needed.

# Team

Galuza Andrew [LinkedIn](https://www.linkedin.com/in/andrew-galuza-61a3a712a/)
Hudozhnik Yegor [LinkedIn](https://www.linkedin.com/in/yegor-hudozhnik/)

## Why This Project?

Regular chatbots implement mostly RAG, which insures stable data retrieving in a conversational manner. In this project we are aiming to solve the real world problem with advanced way, by introducing alive self healing model.
We try not only to diminish halusination, but also provide an approach to fit the uncertainty of real world tasks.

## How?

We would like to cover various modern technologies applicable for the problem.
Some of them are directly the way of implementation of the harness, like LangGraph and DeepAgents. And some of them are tools around it, like LangSmith, Kafka, Vector Databases, efficient use of coding using AI and exploring it's cons and pros.

We adhere to implementing maintainable and sustainable code with clear structure that allows quick overview, easy testing and comfortable version management.

All this will allow us eventualy to implement a scientific approach for measuring the differnt systems, to compare efficiency and relevancy of different components for the task. We will do this on hand regular metrics like token consumption and time efficiency as well as developing custom statistical metrics to measure the quality of produced contracts and conversations.

---

## Tech Stack

| Component              | Choice                                    | Why                                                          |
| ---------------------- | ----------------------------------------- | ------------------------------------------------------------ |
| **LLM**          | Mistral 7B (local via LM Studio)          | Fast (~15 tok/s), good instruction-following, fits 4GB VRAM  |
| **LLM**          | Gemma 4 E2B-it-GGUF (local via LM Studio) | fits 4GB VRAM                                                |
| **Vector DB**    | SQL Server 2025                           | Simple                                                       |
| **Framework v1** | LangChain + LangGraph                     | Industry standard, integrates everything seamlessly          |
| **Framework v2** | DeepAgents                                | Industry novelty, integrates everything even more seamlessly |
| **Backend**      | FastAPI                                   | Async, auto-generated docs, modern Python                    |

See **ARCHITECTURE.md** for detailed system design, data flow, and component interactions.

---

## Quick Start

### Prerequisites

- **Windows 10/11** (PowerShell)
- **Python environment** activated (e.g., `.venv` or your Conda `llm` environment) with project dependencies installed
- **Node.js & npm** (for the React frontend)
- **SQL Server** running and accessible
- **LM Studio** running locally on `http://localhost:1234` with a model loaded

### 1. Configure `.env`

Copy the template and update it with your local database and API settings:

```powershell
Copy-Item .env.example .env
```

### 2. Start the Server

Run all commands from the repository root (`DynamicPromptWizard`) in **PowerShell** with your Python environment active.

#### Option A: Start Backend + Frontend Together (Recommended)

`start_app.py` verifies that LM Studio has a loaded model, then starts both the FastAPI backend and the React frontend:

```powershell
python start_app.py
```

#### Option B: Start Backend and Frontend Separately

**Backend only (FastAPI):**

```powershell
python -m backend.main
```

**Frontend only (React + Vite):**

```powershell
Set-Location frontend
npm install   # first time only
npm run dev
```

### 3. Open the App

- **Frontend App:** `http://localhost:5173`
- **API Docs (Swagger UI):** `http://localhost:8000/docs`

---

## Project Structure

```
rag-system/
├── README.md              # This file
├── ARCHITECTURE.md        # System design (read for interviews)
├── PROGRESS.md            # Working log + backlog
├── main.py                # FastAPI entry point
├── requirements.txt       # Pinned dependencies (generate: pip freeze)
├── .env                   # Local config (git-ignored)
├── .env.example           # Template
├── .gitignore             # Ignore models, chroma_db, __pycache__
├── src/
│   ├── rag_chain.py       # LangChain RAG pipeline
│   ├── embedding_service.py
│   ├── database_service.py # ChromaDB wrapper
│   └── config.py          # Settings from .env
├── data/
│   ├── raw/               # Source documents (PDFs, TXT)
│   └── chroma_db/         # Vector DB (git-ignored)
└── tests/
    ├── test_api.py
    └── test_rag.py
```

---

## Key Commands (PowerShell)

| Task                     | Command                                 |
| ------------------------ | --------------------------------------- |
| Start backend + frontend | `python start_app.py`                 |
| Start backend only       | `python -m backend.main`              |
| Start frontend only      | `Set-Location frontend; npm run dev`  |
| Check API docs           | `curl.exe http://localhost:8000/docs` |
| Monitor GPU              | `nvidia-smi dmon -s u`                |
| Run tests                | `python -m pytest`                    |

---

## Troubleshooting

**GPU not available?**

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

Should return `True`. If False, check NVIDIA drivers: `nvidia-smi`

**LM Studio API returns 404?**

- Verify LM Studio is running
- Verify model is **loaded** (not just downloaded)
- Test: `curl.exe http://localhost:1234/v1/models`

**Out of memory during inference?**

- Reduce GPU layers in LM Studio (try 8-10 instead of 12-15)
- Monitor: `nvidia-smi dmon -s u`

---

## For More Details

- **System Design:** Read **ARCHITECTURE.md**
- **Tech Choices & Alternatives:** Check PROGRESS.md

---

## Quick Demo

Once running:

1. Navigate to `http://localhost:8000/docs`
2. Click **Try it out** on `/query` endpoint
3. Enter a question
4. Get back answer + source documents

---
