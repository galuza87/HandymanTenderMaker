"""Online-evaluation package for HandymanDB's v1 LangGraph nodes.

Each node with a registered evaluator gets its own <node>_judge.py module
(data_validator_judge.py, categorizer_judge.py, ...), defining that node's
judge prompt, feedback key, queue IDs, and inline (live-traffic) trigger
function. All of them share the scoring/routing core in eval_core.py.

backfill.py scores historical runs for every registered node, via the
same shared core, so a run judged live and a run judged during backfill
are scored identically.

Deliberately no re-exports here -- importing a specific submodule
(e.g. `from backend.v1.eval import data_validator_judge`) is preferred
over `from backend.v1.eval import *`, so that importing the package
doesn't force every submodule's import-time side effects (eval_core.py
constructs an OpenAI client and a LangSmith client at import time) to
run just because one of them was needed.
"""