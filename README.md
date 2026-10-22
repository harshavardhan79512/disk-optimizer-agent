# Disk Quota & Space Optimizer Agent

A Python MCP server for the Disk Quota & Space Optimizer specialist agent. It gives an MCP host safe disk tools to inspect space and candidate files. The larger Agentic Shell is responsible for routing the user's natural-language request to this specialist and for requesting approval before a deletion.

## How it works

```text
User request → Agentic Shell / LLM → MCP disk tools → Linux utilities → Results
                                      ↓
                               User approval → delete_files
```

## Tools exposed by this server

| Tool | Purpose |
| --- | --- |
| `get_disk_space` | Uses `df` to report total and available disk space. |
| `get_folder_usage` | Uses `du` to report the demo folder's total size. |
| `list_candidates` | Uses `du` to list files, apply age or extension filters, and calculate the combined size. |
| `get_file_details` | Uses `stat` to report a file's size, modification time, and permissions. |
| `delete_files` | Deletes selected files only when the MCP host passes `approved=true` after explicit user approval. |

## Safety limits

- File tools are restricted to `~/Downloads/disk_optimizer_demo` by default.
- Set `DISK_OPTIMIZER_ROOT` to choose a different dedicated demo folder.
- Absolute paths, paths outside the allowed folder, symbolic links, and directories are rejected for deletion.
- `delete_files` requires the MCP host to show the exact selected paths and obtain user approval first. The host must not set `approved=true` before that approval.
- The server runs fixed Linux utilities with argument lists; it does not execute arbitrary shell commands from the LLM.

## Requirements

- Linux (for `df`, `du`, and `stat`)
- Python 3.11 or newer
- The MCP Python SDK and CLI

## Install

From the project folder in Ubuntu:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p "$HOME/Downloads/disk_optimizer_demo"
```

To use another folder, set its path before starting the MCP host:

```bash
export DISK_OPTIMIZER_ROOT="$HOME/Downloads/disk_optimizer_demo"
```

## Connect to an MCP host

This is an MCP server, not a standalone interactive shell. Configure your MCP host to launch `disk_optimizer_server.py` with the Python interpreter from this project's `.venv`. The server communicates over standard input and output and normally waits quietly for the host; the host provides the LLM, routes requests, and displays tool results and approval prompts.

Example launch command from this folder:

```bash
./.venv/bin/python disk_optimizer_server.py
```

## Project scope

This repository contains the Disk Optimizer specialist MCP server. It is designed to connect to the larger Agentic Shell described in the project architecture; it does not implement the shell's full router for all 35 agents.
