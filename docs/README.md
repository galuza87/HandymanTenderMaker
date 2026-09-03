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

| Component | Choice | Why |
|-----------|--------|-----|
| **LLM** | Mistral 7B (local via LM Studio) | Fast (~15 tok/s), good instruction-following, fits 4GB VRAM |
| **LLM** | Gemma 4 E2B-it-GGUF (local via LM Studio) | fits 4GB VRAM |
| **Vector DB** | SQL Server 2025 | Simple |
| **Framework v1** | LangChain + LangGraph | Industry standard, integrates everything seamlessly |
| **Framework v2** | DeepAgents | Industry novelty, integrates everything even more seamlessly |
| **Backend** | FastAPI | Async, auto-generated docs, modern Python |

See **ARCHITECTURE.md** for detailed system design, data flow, and component interactions.

---

## Quick Start

### Prerequisites
- Windows 10
- Miniforge3 installed (with conda/mamba in PATH)
- CUDA 13.3 (or compatible NVIDIA driver)
- LM Studio installed and running

### 1. Clone / Set Up Repo
```bash
# If starting fresh
mkdir D:\RAG\rag-system
cd D:\RAG\rag-system
git init

# Or if cloning
git clone [your-repo-url]
cd rag-system
```

### 2. Create conda Environment
```bash
# Activate mamba (faster)
conda activate base

# Create Python 3.11 environment
mamba create -n llm python=3.11 -y

# Activate it
conda activate llm
```

### 3. Install Dependencies
```bash
# PyTorch (with CUDA)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# LangChain + LLM stack
pip install langchain langchain-core langchain-openai langgraph

# FastAPI
pip install fastapi uvicorn

# Vector DB + embeddings
pip install chromadb sentence-transformers

# Utilities
pip install pydantic python-dotenv requests
```

### 4. Set Up LM Studio
1. Open LM Studio
2. Download your chosen model 
3. Load it in the "Local Server" tab
4. Set **GPU layers: 12-15** (monitor with `nvidia-smi dmon -s u`)
5. Start server (default: `localhost:1234`)

### 5. Create `.env` File
```bash
cat > .env << EOF
# LM Studio
LLM_API_BASE_URL=http://localhost:1234/v1
LLM_MODEL=mistral-7b-instruct

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2

# FastAPI
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000

# ChromaDB
CHROMA_DB_PATH=./data/chroma_db
EOF
```

### 6. Run the Server
```bash
conda activate llm
cd D:\RAG\rag-system
uvicorn main:app --reload
```

**Navigate to:** `http://localhost:8000/docs` → Auto-generated Swagger UI

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

## Key Commands

| Task | Command |
|------|---------|
| Activate env | `conda activate llm` |
| Start server | `uvicorn main:app --reload` |
| Test API | `curl http://localhost:8000/docs` |
| Monitor GPU | `nvidia-smi dmon -s u` |
| Export dependencies | `pip freeze > requirements.txt` |
| Run tests | `python -m pytest` |

---

## Troubleshooting

**GPU not available?**
```bash
python -c "import torch; print(torch.cuda.is_available())"
```
Should return `True`. If False, check NVIDIA drivers: `nvidia-smi`

**LM Studio API returns 404?**
- Verify LM Studio is running
- Verify model is **loaded** (not just downloaded)
- Test: `curl http://localhost:1234/v1/models`

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

