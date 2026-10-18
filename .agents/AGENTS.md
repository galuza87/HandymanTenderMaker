# Project Level Rules
This file contains global rules for the DynamicPromptWizard project. Agents will read this automatically.

- Always ensure that code is well-commented and clean.
- Ensure that backend code goes to the `backend` directory and frontend code goes to the `frontend` directory.
- **CRITICAL:** For ANY code modification (including bug fixes, feature implementations, and refactoring), you MUST execute the sequential multi-agent orchestration workflow defined in `.agents/rules/multi-agent-orchestrator.md` (Test Builder -> Code Writer -> Code Critic).
