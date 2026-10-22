# 🧹 Disk Quota & Space Optimizer Agent

A Python agent for a natural-language Linux shell. The user describes a disk-space task, the LLM selects an approved disk tool, and the agent reports what it found. Deletion requires user confirmation.

## ✨ Features

- Checks available disk space with `df`
- Inspects folder and file sizes with `du`
- Reads file details with `stat`
- Finds files that match the user's constraints
- Shows deletion candidates before removing anything
- Requires confirmation before deleting selected files

## 🔄 How it works

```text
User request → Agentic Shell → LLM selects a tool → Python runs the tool → Results and confirmation
