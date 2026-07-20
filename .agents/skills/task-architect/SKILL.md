---
name: task-architect
description: To rigorously define, clarify, and architect a task before any code execution, file modification, or tool operations begin.
---

# Skill: Task Architect & Alignment Specialist

## Goal
To rigorously define, clarify, and architect a task before any code execution, file modification, or tool operations begin. This prevents the agent from diving into implementation based on assumptions.

## User Activation Command
/grill-me

## Instructions
When the user invokes this skill (via the `/grill-me` command, or asks to design/architect a task, e.g., "create a security agent"), you must **immediately halt any execution steps** and execute the following sequence:

### Phase 1: Clarification & Discovery
Analyze the user's request and ask **3 to 5 targeted, high-impact questions** to resolve ambiguity. Your questions should focus on:
1. **Scope & Objectives:** What is the primary problem we are trying to solve?
2. **Environment & Tech Stack:** What frameworks, databases, or environment constraints must we respect?
3. **Constraints:** Are there performance, security, or architectural boundaries?

### Phase 2: Architectural Options (Pros & Cons)
Identify **at least two distinct technical approaches** to solve the user's problem. For each approach, provide:
- **How it works:** A brief 1-2 sentence technical summary.
- **Benefits (Pros):** What makes this approach great? (e.g., speed, simplicity, scale, cost).
- **Drawbacks (Cons):** What are the hidden gotchas? (e.g., maintenance overhead, complexity, resource usage).

### Phase 3: The Wait State
Present your findings in a clear, scannable Markdown format. 

**STRICT RULE:** Under no circumstances should you generate implementation files, write code, or run terminal scripts during this turn. End your response with a clear call to action, waiting for the user to select an option or provide answers to your questions.
