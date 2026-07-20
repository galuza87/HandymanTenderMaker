from backend.v1.engine import get_llm
from pydantic import BaseModel, Field
from typing import Literal

llm = get_llm()
llm.model_name = "gpt-4o"

class Out(BaseModel):
    decision: Literal['single', 'multiple', 'unknown'] = Field(description="Return 'single' if ONE trade is mentioned. Return 'multiple' if MORE THAN ONE trade is needed. Return 'unknown' if it's just a greeting or too vague to know.")
    confidence: float

prompt = """
You are the Categorizer Agent. Analyze the user's request.
Your ONLY job is to determine if the task requires a 'single' professional or 'multiple' professionals.
If you cannot decide, return 'multiple' with a low confidence score.
Output your decision and your confidence score.

User request: I need a plumber to fix a leak.
"""

print(llm.with_structured_output(Out, method='json_schema').invoke(prompt))
