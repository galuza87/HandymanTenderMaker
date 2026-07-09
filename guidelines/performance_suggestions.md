# 🚀 Suggestions to Improve LLM Processing Time

Since adding multiple workflow nodes (like subtask determination, confirmation, categorization, and client info collection) increases the total number of LLM inference requests, the total processing time naturally goes up. 

Here are several actionable ways to improve performance **without** removing any of the existing nodes in your `engine.py` workflow:

---

## 1. Optimize Message History (Context Window)
Currently, `state.messages` is being injected in full into the LLM on every node. The larger the context, the longer it takes the LLM to process and return the first token.

* **Prune History:** Send only the last few relevant messages instead of the entire conversation history.
* **Handle Images Efficiently:** If users upload images, the base64 string or image URL is re-sent in every node that loops through `state.messages`. 
  > **Fix:** Process the image in the very first node and replace the image in the message history with a text summary. Subsequent nodes won't have to re-process heavy image data.

---

## 2. Use Native Tool Calling or JSON Mode
Currently, you are prompting the LLM to output a JSON block and then using a regex (`re.search(r'\{.*\}', content, re.DOTALL)`) to parse it. 

* **Native Tools/JSON Mode:** If supported by your LM Studio model, using native Tool/Function Calling or strict JSON Mode can significantly reduce generation time. 
* **Why it works:** The LLM focuses solely on generating the structured data without conversational padding, reducing the total output token count and speeding up the response.

---

## 3. Switch to a Smaller/Faster Model
If you are running models locally via LM Studio, your model choice drastically impacts speed.

* **Quantization:** Ensure you are using highly optimized quantized models (e.g., 4-bit or 8-bit GGUF files) which run much faster.
* **Model Size:** Consider using a smaller, highly capable model specifically for routing/categorization tasks (e.g., `Llama-3-8B`, `Qwen-2`, or `Phi-3`). Smaller models process requests and generate tokens exponentially faster than larger, general-purpose models.

---

## 4. Cache Database Queries
In `llm_determine_number_of_subtasks`, `get_all_categories_with_subs()` is called synchronously on every single execution. 

* **In-Memory Caching:** Fetch this data once when the application starts or cache it in-memory with a TTL (Time to Live). 
* **Why it works:** Preventing synchronous database read delays before every LLM request will shave off latency.

---

## 5. Implement Streaming Responses
While this doesn't reduce the *absolute* processing time, it drastically improves **perceived performance** for the user.

* Instead of waiting for the entire node graph to finish before showing a response, stream the LLM tokens directly to the frontend as they are generated. This keeps the user engaged while the backend seamlessly transitions between nodes.

---

## 6. Semantic Caching
If users frequently ask for the same types of jobs (e.g., *"I need a plumber to fix a leak"*), you can use a semantic caching layer (like `GPTCache`). 

* If the vector embedding of a new user request closely matches a previous one, you can return the cached categories instantly, completely bypassing the LLM step for those nodes.

---

## 7. Asynchronous Parallelization
Right now, your core nodes are sequential. However, if you ever add nodes that do not strictly depend on the output of the previous node (e.g., running a spam check, language detection, and category determination simultaneously), you should update the engine to run them concurrently.

* **Fix:** Use `asyncio.gather()` to run independent tasks in parallel, preventing further compounding delays.
