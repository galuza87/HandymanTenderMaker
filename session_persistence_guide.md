# 💾 Guide to Persistent User Sessions

Currently, in your `engine.py`, sessions are stored in an in-memory Python dictionary (`sessions: Dict[str, AgentState] = {}`). This means if the user closes their browser, reloads the page, or if your backend server restarts, the entire conversation history and project state are instantly destroyed.

To allow users to jump back into an old session seamlessly, you need to implement **Session Persistence**. Here is exactly what objects you need to store and how to save them so no data is ever lost.

---

## 1. What Data Needs to be Saved?

To perfectly reconstruct a conversation exactly where the user left off, you must save the entire `AgentState`. 

Here are the critical objects to persist:
* **`session_id`**: (UUID/String) The unique identifier for this specific conversation.
* **`messages`**: (List of Dicts) The full conversation history. This gives the LLM its memory. *Note: For images, you should save URLs rather than raw Base64 strings to save database space.*
* **`next_step`**: (String) Extremely critical! This tells the `engine.py` exactly which node (e.g., `collect_client_info`) the user was parked at when they left.
* **`identified_categories` & `sub_tasks`**: (Lists) The workflow progress up to the point of abandonment.
* **`client_info`**: (Dict) Any partial data collected (e.g., they gave their name but closed the browser before giving their phone number).

---

## 2. How to Save It in the Backend (Database)

Because the `AgentState` is deeply nested (lists of dicts, strings, etc.), you have two main architectural choices.

### Option A: The "JSON Dump" Method (Fastest & Easiest)
Since you are using Pydantic for `AgentState`, you can easily convert the entire state into a single JSON string and save it in one database column.

**Database Table (`active_sessions`):**
* `session_id` (Primary Key, String)
* `state_json` (JSON or Text)
* `last_updated` (Timestamp)

**Workflow:**
1. User sends a message. The engine processes the nodes.
2. Before returning the HTTP response to the frontend, you do:
   `db.execute("UPDATE active_sessions SET state_json = ? WHERE session_id = ?", [state.json(), session_id])`
3. Next time the user connects, you do:
   `raw_json = db.fetch(...)` -> `state = AgentState.parse_raw(raw_json)`

### Option B: The Relational Method (Best for Analytics & Search)
If you want to be able to query things like *"How many users abandoned the chat at the phone number step?"*, you should split the data into relational tables.

**Tables:**
1. `sessions` (`id`, `next_step`, `client_info_json`, `created_at`)
2. `session_messages` (`id`, `session_id`, `role`, `content`, `image_url`, `timestamp`)
3. `session_categories` (`id`, `session_id`, `category_id`, `confidence_score`)

---

## 3. How to Save It on the Frontend (Surviving Browser Close)

The backend cannot track a user who closed their browser unless the browser remembers who it is. You must store the `session_id` persistently in the user's browser.

### The `localStorage` Approach
In your React application, use `localStorage`. Unlike `sessionStorage` (which deletes when the tab closes), `localStorage` survives browser restarts.

```javascript
// 1. When a new chat starts, save the generated ID
localStorage.setItem("wizard_session_id", "123e4567-e89b-12d3-a456-426614174000");

// 2. When the React app loads (e.g., in a useEffect on the Dashboard)
useEffect(() => {
    const savedSessionId = localStorage.getItem("wizard_session_id");
    
    if (savedSessionId) {
        // Ping your backend: GET /api/session/{savedSessionId}
        // If it exists, populate the chat window with the returned messages!
        fetchSessionHistory(savedSessionId);
    } else {
        // Start a brand new blank session
        startNewSession();
    }
}, []);
```

---

## 4. The "Rehydration" Process (Bringing the Session Back to Life)

When a user comes back 3 days later and types a new message, here is how the data flows:

1. **React App:** Sends the new message along with the old `session_id` from `localStorage`.
2. **FastAPI Endpoint:** Receives the request. Looks up `session_id` in the database.
3. **Rehydration:** The database returns the saved JSON state. You parse it back into the `AgentState` Python object.
4. **Append:** You append the user's *new* message to `state.messages`.
5. **Execution:** You pass the rehydrated state to `engine.process(state)`. Because `state.next_step` was saved, the engine bypasses nodes that were already completed and jumps right back to where it needs to be!
6. **Save:** Once `engine.process()` returns, you overwrite the database with the new, updated state.
