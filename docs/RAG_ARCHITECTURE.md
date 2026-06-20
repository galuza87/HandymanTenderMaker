# RAG System Architecture

**System design document.** Read this to understand how the system works and why we made each architectural choice. Good for interviews.

---

## 1. High-Level Overview

Our RAG system answers questions about documents by:

1. **Embedding** user documents into dense vectors (384-dimensional)
2. **Storing** embeddings in a vector database (ChromaDB)
3. **Retrieving** the top-K most similar documents when a question is asked
4. **Prompting** an LLM with the question + retrieved context
5. **Generating** a grounded answer

This solves the hallucination problem: the LLM only answers based on documents it has seen.

---

## 2. System Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│              User (HTTP Client)                  │
└────────────────┬────────────────────────────────┘
                 │ POST /query
                 │ GET  /docs
                 ▼
        ┌────────────────────┐
        │   FastAPI Server   │
        │  (localhost:8000)  │
        └────────┬───────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌─────────────────┐    ┌──────────────────┐
│  Embedding      │    │  RAG Chain       │
│  Service        │    │  (LangChain)     │
│                 │    │                  │
│ all-MiniLM-L6   │    │ ├─ Retriever    │
│ (384D vectors)  │    │ ├─ Prompt       │
└────────┬────────┘    │ └─ LLM Call     │
         │             └────────┬────────┘
         │                      │
         └────────────┬─────────┘
                      │
        ┌─────────────┴────────────────┐
        │                              │
        ▼                              ▼
   ┌──────────────┐          ┌─────────────────┐
   │  ChromaDB    │          │  LM Studio API  │
   │ (Vector DB)  │          │ (localhost:1234)│
   │              │          │                 │
   │ • Embeddings │          │ Mistral 7B      │
   │ • Metadata   │          │ ~15 tokens/sec  │
   │ • Search     │          │ 12-15 GPU layers│
   └──────────────┘          └─────────────────┘
```

---

## 3. Data Flow

### 3.1 Document Ingestion

```
Raw Documents (TXT, PDF, etc.)
        │
        ▼
    [Parse/Load]
        │
        ▼
   [Split into Chunks]  (optional; currently using full docs)
        │
        ▼
   [Embed Chunks]
   using all-MiniLM-L6-v2
        │
        ▼
   [Store in ChromaDB]
   embeddings + metadata
        │
        ▼
    Ready for Queries
```

### 3.2 Query/Answer Flow

```
User Question: "What is [topic]?"
        │
        ▼
  [Embed Question]
  using all-MiniLM-L6-v2
        │
        ▼
[Retrieve Top-K Docs]
   ChromaDB similarity search
   K=5, cosine similarity
        │
        ▼
[Build Prompt]
   "Based on:
    [DOC 1]
    [DOC 2]
    ...
    Answer: [QUESTION]"
        │
        ▼
[Call LLM]
   LM Studio Mistral 7B
   temperature=0.7 (tunable)
        │
        ▼
[Return Response]
   JSON:
   {
     "answer": "...",
     "sources": [
       {doc, chunk_id, similarity},
       ...
     ],
     "latency_ms": 2340
   }
```

---

## 4. Components

### 4.1 FastAPI Server

**Purpose:** HTTP interface to the RAG system

**Endpoints:**
- `GET /health` → Returns `{"status": "ok"}`
- `POST /query` → Main RAG endpoint
  - Input: `{"question": "...?", "top_k": 5}`
  - Output: `{"answer": "...", "sources": [...], "latency_ms": ...}`
- `POST /documents/upload` → Ingest documents
  - Input: File upload
  - Output: `{"status": "ok", "chunks_indexed": 12}`

**Why FastAPI?**
- Async request handling (efficient for I/O)
- Auto-generated Swagger UI at `/docs` (great for demos)
- Type hints for request validation
- Modern Python, widely used in AI/ML

---

### 4.2 Embedding Service

**Module:** `src/embedding_service.py`

**Model:** `all-MiniLM-L6-v2`
- Input: Any text string
- Output: 384-dimensional dense vector
- Speed: ~50ms per document on GPU
- Memory: ~100MB model + small buffer for batches

**Why this model?**
- Lightweight (90MB) — leaves room for LLM inference
- Fast — 2x faster than larger alternatives
- Quality — trained on 1B sentence pairs, good semantic matching
- Works on CPU if GPU unavailable (fallback)

**Alternative options considered:**
- `all-MiniLM-L12-v2`: Better quality but 2x slower, more VRAM
- `bge-small-en-v1.5`: Newer, slightly better, similar size
- `nomic-embed-text`: Longer context window, but overkill for RAG

---

### 4.3 Vector Database (ChromaDB)

**Module:** `src/database_service.py`

**Purpose:** Store embeddings and search for similar documents

**Why ChromaDB?**
- Zero infrastructure: SQLite + in-memory + persistent storage
- Embedding + search in one place (integrated)
- Clean Python API
- No external dependencies or servers to manage
- Good for prototyping; scalable later if needed

**How it works:**
- Stores embeddings as dense vectors
- Stores document text + metadata (source, chunk_id, etc.)
- Searches using cosine similarity (default)
- Returns top-K matches with similarity scores

**Scaling:** Works well up to ~50k documents. If you exceed that, consider Pinecone, Weaviate, or Milvus (revisit decision at that point).

---

### 4.4 RAG Chain (LangChain)

**Module:** `src/rag_chain.py`

**Purpose:** Orchestrate retrieval + LLM generation

**Pipeline (pseudo-code):**
```python
def answer_question(question):
    # 1. Embed the question
    q_vec = embedding_service.embed(question)
    
    # 2. Retrieve top-K docs
    docs = db.search(q_vec, k=5)
    
    # 3. Build prompt with context
    prompt = f"""Based on these documents:
    {format_docs(docs)}
    
    Answer this question: {question}"""
    
    # 4. Call LLM
    response = llm.generate(prompt, temp=0.7, max_tokens=500)
    
    # 5. Return answer + sources
    return {
        "answer": response,
        "sources": [{doc_id, similarity} for doc in docs]
    }
```

**Why LangChain?**
- Handles prompt templating elegantly
- Chains together embeddings → retrieval → LLM seamlessly
- LangGraph for future multi-step workflows (reranking, refinement, etc.)
- Large ecosystem; lots of examples online

---

### 4.5 LLM Inference (LM Studio)

**Setup:** Mistral 7B quantized to GGUF, running locally on GTX 1050 Ti

**Performance:**
- Speed: ~15 tokens/second
- VRAM: 3.8GB with 12-15 GPU layers configured
- API: OpenAI-compatible (`http://localhost:1234/v1`)

**Why local inference?**
- ✅ No API costs, full privacy, works offline
- ✅ Full control: can tune temperature, sampling, context window
- ❌ Slower than cloud APIs (but acceptable for this project)
- ❌ Limited to local VRAM (4GB practical limit)

**Why Mistral 7B?**
- Good instruction-following (important for Q&A tasks)
- Smaller than Llama 13B (fits in 4GB)
- Faster than Llama 2 on consumer hardware
- Good balance of speed + quality

**Trade-offs vs alternatives:**
| Option | Speed | Quality | Cost | Privacy |
|--------|-------|---------|------|---------|
| Mistral 7B (local) | 15 tok/s | Good | $0 | 100% |
| OpenAI GPT-4 | 50+ tok/s | Excellent | $$$ | No |
| Ollama | 12 tok/s | Good | $0 | 100% |
| Llama 13B (local) | 8 tok/s | Better | $0 | 100% |

---

## 5. Key Design Decisions & Trade-offs

| Decision | Trade-off | Future Revisit? |
|----------|-----------|-----------------|
| **Local LLM** (Mistral 7B) | Speed for privacy + cost | If latency becomes critical, consider cloud fallback |
| **ChromaDB** | Simplicity for scalability | If >50k docs needed, move to Pinecone/Weaviate |
| **Full document chunks** | Simplicity for retrieval precision | Will experiment with document splitting if quality degrades |
| **Cosine similarity** | Standard for speed/quality | Could try other metrics (L2, dot product) later |
| **No reranking yet** | Coverage for precision | Add cross-encoder reranking if top-5 relevance isn't good enough |

---

## 6. Performance Targets

| Metric | Target | How We'll Measure |
|--------|--------|------------------|
| Query latency | <5 sec | End-to-end timing in FastAPI |
| Embedding speed | <100ms | Per-document benchmark |
| Retrieval recall | >80% | Manual eval on test queries |
| LLM throughput | >10 tok/s | Already at 15 tok/s ✓ |

---

## 7. Known Limitations & Future Extensions

**Current limitations:**
- Single-threaded (one query at a time)
- No conversation history (each query is stateless)
- No answer quality metrics (manual eval only)
- No web UI (Swagger UI is the interface)

**Future extensions:**
- **Reranking:** Cross-encoder to re-rank retrieved docs before passing to LLM
- **Multi-turn:** Keep conversation history in prompt
- **Web UI:** Streamlit or React frontend
- **Deployment:** Docker, cloud (AWS Lambda, Railway, etc.)
- **Monitoring:** Log queries, answers, sources; track answer quality over time
- **Fine-tuning:** Fine-tune embedding model on domain-specific data
- **Document splitting:** Smart chunking if single documents are too long

---

## 8. Why This Architecture?

**Simplicity + Functionality:**
- Every component is lightweight and focused
- Can prototype and iterate fast (no complex infrastructure)
- Easy to understand (good for learning + resume)
- Scales to 50k+ documents before needing upgrades

**Resume Value:**
- You own the full stack: frontend → backend → vector search → LLM
- Tech choices are justified (not arbitrary)
- System is buildable in 2-3 weeks (realistic scope for a side project)
- Demonstrates understanding of RAG, embeddings, vector DBs, LLMs

---

## 9. Diagram: Full Request Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ User submits: "What is machine learning?"                   │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │ FastAPI /query endpoint │
    └────────────┬────────────┘
                 │
    ┌────────────▼──────────────────┐
    │ Embedding Service             │
    │ all-MiniLM-L6-v2              │
    │ → [0.234, 0.891, ..., 0.012]  │ (384D vector)
    └────────────┬──────────────────┘
                 │
    ┌────────────▼─────────────────────────┐
    │ ChromaDB Search                       │
    │ Cosine similarity on 384D vector      │
    │ → Top 5 documents + similarity scores │
    └────────────┬─────────────────────────┘
                 │
    ┌────────────▼──────────────────────────────┐
    │ Build Prompt                              │
    │ "Based on: [DOC1] [DOC2] ... Answer: ..." │
    └────────────┬──────────────────────────────┘
                 │
    ┌────────────▼─────────────────────────────────┐
    │ LM Studio API (Mistral 7B)                   │
    │ Generate response (15 tokens/sec)            │
    │ → "Machine learning is a subset of AI that..." │
    └────────────┬─────────────────────────────────┘
                 │
    ┌────────────▼──────────────────────┐
    │ Format Response JSON               │
    │ {answer, sources, latency_ms}     │
    └────────────┬──────────────────────┘
                 │
                 ▼
        Return to User (HTTP 200)
```

---

## 10. How to Update This Document

- Update when system design significantly changes
- Update performance targets when you measure real numbers
- Update "Known Limitations" when you find/fix issues
- Reference this in code comments when architectural decisions matter
- Bring to interviews! Interviewers love seeing you understand *why* you chose each piece.

