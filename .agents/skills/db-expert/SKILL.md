---
name: db-expert
description: Use this skill whenever a change to the database is needed (e.g., schema migrations, data backfills). It ensures database scripts are properly named and tracked.
---

# DB Expert Guidelines

Whenever you are tasked with making a change to the database, you must act as the DB Expert and strictly follow these rules:

## 1. Script Creation
- Any change to the database must be executed via a dedicated script. 
- You must always create this script in the `scripts` folder in the project root.

## 2. File Naming Convention
- The script filename must exactly be the Jira ticket ID (e.g., `KAN-1`) followed by an underscore and a timestamp. If the user does not provide a ticket ID, you must ask them for it before creating the script.
- The filename MUST NOT contain any descriptive text. The explanation of what the script does belongs exclusively in the first commented line of the script.
- Format example: `scripts/KAN-1_YYYYMMDD_HHMMSS.sql` (or `.py` if it's a Python script).

## 3. Script Structure
- The very first line of the script **must** be a comment that provides a clear description of what the script does.
- Example for SQL:
  ```sql
  -- Description: This script adds the new status column to the user table.
  ```
- Example for Python:
  ```python
  # Description: This script migrates old user records to the new authentication schema.
  ```
