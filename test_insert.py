import sys
import os
sys.path.append(os.path.dirname(__file__))

from backend.db.prompts_repository import create_project_prompt
import json

embedding = [0.1] * 384

try:
    project_id = 1
    category_id = 1
    prompt_text = "Test prompt text"
    
    prompt_id = create_project_prompt(
        project_id=project_id, 
        category_id=category_id, 
        prompt_text=prompt_text, 
        embedding=embedding
    )
    
    print(f"Result: {prompt_id}")
except Exception as e:
    print(f"Fatal error: {e}")
