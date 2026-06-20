# Progress Log

**Single working log.** Read latest entries before you start. Add an entry after each session (5 min, use template below). This is your collaboration backbone—tech decisions, blockers, what's next, all in one place.

---

## Session Template

```
### [Date] — [Time spent] — [Your Name]

**What was done:**
- [Brief description of completed work]
- [Another task]

**Files changed:**
- `src/rag_chain.py`: [1-line summary of what changed]
- `main.py`: [1-line summary]

**Next for [Partner]:**
- [ ] [Task they should do next]
- [ ] [If there's a blocker, note it here]

**Decisions / Experiments:**
- [If you tried X vs Y, note the outcome and why you chose one]
- [Or: tried embedding model Z, found it uses 400MB RAM (too much)]

**Blockers:**
- [If stuck, describe it; partner can help]

**Notes:**
- [Anything else: learning, gotcha, workaround, etc.]
```

---

## Example Sessions (Real-ish examples)

### 2025-01-15 — 2.5 hours — Yegor

**What was done:**
- Set up conda `llm` environment (Python 3.11)
- Installed FastAPI, LangChain, ChromaDB, sentence-transformers
- Downloaded Mistral 7B GGUF, configured 12 GPU layers in LM Studio
- Verified inference works: 15 tokens/sec, 3.8GB VRAM

**Files changed:**
- `.condarc`: Redirected `envs_dirs` to D: drive
- Created `test_inference.py`: Quick script to verify LM Studio API connection

**Next for [Partner]:**
- [ ] Pick document domain (Wikipedia articles, PDFs, custom text?) and prepare 10-20 sample docs
- [ ] Start FastAPI skeleton: `/health`, `/query`, `/docs` endpoints (no RAG logic yet)

**Decisions / Experiments:**
- Chose **Mistral 7B** over Llama 2: Mistral is ~1.5x faster on our VRAM + better instruction-following
- Tested CUDA detection: `torch.cuda.is_available()` returns True, `nvidia-smi` shows GTX 1050 Ti

**Blockers:**
- None yet

**Notes:**
- LM Studio API works perfectly with `openai` library (point base_url at localhost:1234)
- Run `nvidia-smi dmon -s u` in parallel terminal to watch VRAM during inference
- Environment is reproducible—partner should get identical results running same commands

---

### 2025-01-16 — 3 hours — [Partner]

**What was done:**
- Scaffolded FastAPI app with `/health`, `/query`, `/documents/upload` endpoints
- Created `data/raw/` folder with 15 Wikipedia articles on climate science (test corpus)
- Set up logging + error handling in FastAPI

**Files changed:**
- `main.py`: Basic FastAPI app with health check + placeholder endpoints
- `data/raw/`: Added 15 `.txt` files (climate science articles)
- `documents.json`: Metadata for each document (title, source, retrieval date)

**Next for Yegor:**
- [ ] Start embedding integration: choose all-MiniLM or all-MiniLM-L12 (test memory footprint)
- [ ] Create `src/embedding_service.py` module
- I'll start `src/database_service.py` (ChromaDB setup) in parallel

**Decisions / Experiments:**
- Used `.txt` + `.json` metadata instead of embedding filenames: cleaner, easier to chunk later
- Tested FastAPI `/docs` endpoint: auto-generated Swagger UI is beautiful (great for resume screenshots)
- Verified app startup time: ~0.5 seconds (very responsive)

**Blockers:**
- None yet

**Notes:**
- FastAPI auto-docs at `http://localhost:8000/docs` is a huge plus
- Remember to test the app together once we wire up the first RAG task

---

### 2025-01-18 — 2 hours — Yegor

**What was done:**
- Created `src/embedding_service.py` with sentence-transformers integration
- Tested all-MiniLM-L6-v2: ~90MB model size, 50ms embedding time per document
- Verified VRAM usage during inference: embedding + LLM inference together = 4.2GB peak (safe margin)

**Files changed:**
- `src/embedding_service.py`: EmbeddingService class with lazy model loading
- `test_embedding.py`: Quick test script (10 sample sentences, benchmark timing)

**Next for [Partner]:**
- [ ] Set up ChromaDB in `src/database_service.py`
- [ ] Ingest the 15 climate docs, embed them, test retrieval with sample queries
- [ ] Then we sync before wiring into FastAPI

**Decisions / Experiments:**
- Tested all-MiniLM-L6-v2 vs all-MiniLM-L12-v2: L6 is 2x faster, same quality for semantic search, saves VRAM
- Decided: use L6 (all-MiniLM-L6-v2)
- Lazy loading: model only loads on first call, no memory waste on startup

**Blockers:**
- None yet (pretty smooth!)

**Notes:**
- Embeddings are deterministic: running twice on same input produces identical vectors
- Sentence-transformers is battle-tested for this task; don't reinvent

---

### 2025-01-20 — 1.5 hours — [Partner]

**What was done:**
- Set up ChromaDB in `src/database_service.py`
- Loaded & embedded all 15 climate docs using embedding_service
- Tested retrieval: sample query "What is climate change?" returns top 5 relevant docs + similarity scores

**Files changed:**
- `src/database_service.py`: DocumentDB class wrapping ChromaDB
- `scripts/ingest_documents.py`: One-off script to load docs from `data/raw/` and index them

**Next for Yegor:**
- [ ] Build the RAG chain in `src/rag_chain.py`: retrieval + prompt building + LLM call
- [ ] Wire it into FastAPI `/query` endpoint
- I'll start writing tests for embedding + retrieval in parallel

**Decisions / Experiments:**
- ChromaDB works great: no setup hassle, embeddings + retrieval in one place
- Tested retrieval quality manually: top results are clearly relevant (good sign for Phase 2)
- Chunk strategy: using full documents for now (will experiment with splitting later if needed)

**Blockers:**
- None yet

**Notes:**
- ChromaDB persists to `./data/chroma_db/` automatically (don't commit this, it's in .gitignore)
- Query time: ~30ms for vector search on 15 docs (very fast)
- Next: wire up LLM generation and we have a working RAG system

---

### [Date] — [Time] — [Your Name]

**What was done:**
- 

**Files changed:**
- 

**Next for [Partner]:**
- [ ] 

**Decisions / Experiments:**
- 

**Blockers:**
- 

**Notes:**
- 

---

## Backlog (What's Left)

- **LangChain RAG chain:** Build full pipeline (retrieval → prompt → LLM → response)
- **FastAPI integration:** Wire RAG chain into `/query` endpoint
- **Answer evaluation:** Test quality of generated answers manually
- **Latency optimization:** Benchmark end-to-end query time, optimize if needed
- **Testing:** Unit tests for embeddings, retrieval, API endpoints
- **Reranking:** Experiment with cross-encoder reranking if retrieval plateaus
- **Multi-turn:** Add conversation history to context window (future)
- **Web UI:** Streamlit or React frontend (future)
- **Deployment:** Docker container, cloud options (future)

---

## How to Use This File

1. **Before you start work:** Read the latest 1-2 sessions (3 min) to understand current state
2. **During work:** Make notes about decisions + blockers as you go
3. **After work:** Add a new session entry (use template above, takes 5 min)
4. **Partner checking in:** They skim your session, see "Next for [you]", and know what to do
5. **Weeks later when you return:** Read last few sessions, understand the arc, jump in

**Golden rule:** 5 minutes of notes now = 30 minutes of clarity for your partner (or future you)

---

## Quick Reference: Recent Decisions

| Decision | Outcome | Notes |
|----------|---------|-------|
| LLM model | Mistral 7B | 15 tok/s, good instruction-following |
| Embedding model | all-MiniLM-L6-v2 | 90MB, 50ms/doc, fits VRAM |
| Vector DB | ChromaDB | Simple, works great, no hassle |
| Chunking strategy | Full documents (for now) | Will experiment with splitting later if needed |

