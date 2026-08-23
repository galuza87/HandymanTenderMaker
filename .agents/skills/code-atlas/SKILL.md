---
name: code-atlas-navigator
description: Use this skill to navigate the codebase efficiently by querying the Code Atlas instead of reading raw files, saving time and tokens.
---

# Code Atlas Navigator Skill

When tasked with finding where a specific API, function, or database model is defined or used in the `DynamicPromptWizard` project, you should use the **Code Atlas** before manually grepping or listing directories.

## How to use the Code Atlas

1. **Read the Index**:
   The `code_atlas.json` file in the root of the project contains a structural map of the entire backend. It lists:
   - `all_endpoints`: The FastAPI routes (method, path, file, args).
   - `all_models`: Database models (name, file, fields).
   - `files`: A mapping of every Python file to the functions, endpoints, and classes it contains.

2. **Locate your target**:
   Use `grep_search` on `code_atlas.json` for the function name, path, or model you are looking for. Because it is a structured JSON, you can quickly find the exact file and line number where something is defined.

   *Example*: If a user asks "Where is the tender creation logic?", you can search for "tender" in `code_atlas.json` to find the relevant endpoints and models, and then open those specific files.

## Maintenance Rule

**IMPORTANT**: If you add a new endpoint, modify a model, or change the signature of a core function, you MUST update the atlas by running the extractor script:
```powershell
python scripts/generate_code_atlas.py
```
This ensures the Code Atlas stays up to date for both you (the agent) and the visual Wiki web app used by the developers.
