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

### 2026-06-28 — Yegor

**What was done:**
- Created ability to manage different versions of the harness simultaniosly
- Outsourced current code in Version 1
- Devided the source code to different subfolders and files 
- Added ability to run sanity tests

**Files changed:**
- `.env`, `config.py`: Connection strings at .env in order to ease testing and shorten the code
- `.env`: holds the version of the avtive harness
- Created subfolders: `v1`, `tests`, `v1/db`
- `__init__.py` files: needed for tidy imports in hierarchical package structure
- `engine.py`: contains the core logic and package interface of the harness
- `models.py`: contains the llm classes used by the harness
- `tasks.py`: contains RAG Database & Guidelines
- `fallback_engine.py`: contains the determenistic fallback engine
- `main.py`: has got much thinner, instanciates the engine of the active harness version
- `conftest.py`: contains the rooting information for the pytest
- `test-sanity.py`: performs two sanity checks, to see that the source code runs from the command line
- `test_api.py`: performs checks of the Rest endpoints

**Next for [Partner]:**
- [ ] Are init.py indeed needed?

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

