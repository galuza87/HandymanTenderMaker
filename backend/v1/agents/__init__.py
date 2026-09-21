"""LangGraph node functions for HandymanDB's v1 agent pipeline.
 
Each module here (data_validator.py, categorizer.py, ...) defines one
node function with the signature `(state: GraphState) -> dict`, matching
what `workflow.add_node(...)` in graph.py expects. `base.py` holds the
shared `GraphState` TypedDict and the structured-output models
(`DataValidatorOutput`, `CategorizerDecisionLLMOutput`, ...) that
individual nodes build on.
 
Three conventions repeat across node files but are not enforced by any
shared base class or type -- worth knowing before adding a new node or
touching an existing one, since nothing will fail loudly if they're
broken:
 
1. ALL_DONE completion sentinel. Nodes that wrap an LLM in a
   `create_react_agent` loop (contractor_categorizer, information_gatherer,
   intake_coordinator, multi_task_architect) have their system prompt
   instruct the model to append the literal string "ALL_DONE" (or a
   variant like "ALL_DONE_CATEGORY_12") once it's finished, as the signal
   to stop looping and advance `next_agent`. Every such node is
   responsible for stripping that marker out of the final message before
   it's stored back into `state["messages"]` -- forgetting the strip
   leaks the sentinel into what the user actually sees.
 
2. Errors are caught and returned, not raised. Every node wraps its body
   in try/except and, on failure, returns a normal state-update dict
   (usually appending an error string as an assistant message) rather
   than letting the exception propagate into LangGraph's own execution.
   This keeps a single node's failure from crashing the whole graph
   invocation, but it also means an exception inside a node is only
   visible if something reads the message it produced -- there is no
   separate error channel. (The online evaluators in `backend/v1/eval/`
   follow the same swallow-and-log convention for the same reason -- see
   `judge_and_route` in `eval_core.py`.)
 
3. Routing lives in the returned `next_agent` string, not in a return
   value LangGraph itself inspects. Every node decides the next node by
   name and puts it in its returned dict; the conditional-edge functions
   in graph.py (`data_validator_edge`, `categorizer_edge`, ...) just read
   `state["next_agent"]` back out. A node that forgets to set it, or sets
   an unrecognized name, fails at the graph's routing step rather than
   inside the node itself -- worth checking `next_agent` first when a new
   node's runs aren't advancing as expected.
"""

from backend.v1.agents.data_validator import data_validator_node
from backend.v1.agents.categorizer import categorizer_node
from backend.v1.agents.information_gatherer import information_gatherer_node
from backend.v1.agents.contractor_categorizer import contractor_categorizer_node
from backend.v1.agents.multi_task_architect import multi_task_architect_node
from backend.v1.agents.intake_coordinator import intake_node
from backend.v1.agents.tender_creator import tender_creator_node

__all__ = [
    "data_validator_node",
    "categorizer_node",
    "information_gatherer_node",
    "contractor_categorizer_node",
    "multi_task_architect_node",
    "intake_node",
    "tender_creator_node",
]
