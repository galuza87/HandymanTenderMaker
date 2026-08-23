# Project Level Rules
This file contains global rules for the DynamicPromptWizard project. Agents will read this automatically.

- Always ensure that code is well-commented and clean.
- Ensure that backend code goes to the `backend` directory and frontend code goes to the `frontend` directory.
- Code Atlas Maintenance: Whenever you add a new function, API endpoint, or database model, you MUST run `python scripts/generate_code_atlas.py` to keep the visual wiki up to date.
