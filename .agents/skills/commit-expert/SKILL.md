---
name: commit-expert
description: Use this skill to format git commit messages, branch names, and PR descriptions cleanly.
---

# Git Commit Expert Guidelines

Whenever you are tasked with writing a commit message, naming a branch, or summarizing changes for version control, follow these rules.

## Rules
1. **Conventional Commits:** Use the standard format: `<type>[optional scope]: <description>`.
   - Valid Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`.
   - Example: `feat(auth): added JWT token validation`
2. **Descriptive Body:** If the change is complex, include a blank line after the description and provide a detailed body that explains the *why* and *how* behind the changes.
3. **Atomic Changes:** Encourage keeping commits atomic. Each commit should represent a single logical change or bug fix.
