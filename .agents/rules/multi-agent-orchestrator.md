---
trigger: always_on
---

# Multi-Agent Coding Orchestration

When you are asked to implement a new feature, write any code, fix a bug, or perform refactoring, you MUST adopt the following sequential multi-agent workflow. You will act as the orchestrator and adopt each persona in order. This applies to ANY code you write.

**Phase 1: Test Builder**
- Activate the `test-builder` skill.
- Analyze the requirements and write the necessary tests. 
- Do not proceed to Phase 2 until tests are defined.

**Phase 2: Code Writer**
- Activate the `code-writer` skill.
- Write the implementation code required to satisfy the feature and pass the tests.

**Phase 3: Code Critic**
- Activate the `code-critic` skill.
- Review the code written in Phase 2 against the rules defined in `coding_conventions.md`. 
- If issues are found, act as the Code Critic to provide feedback, then loop back to Phase 2 (Code Writer) to fix them.
- If no issues are found, the task is complete.
