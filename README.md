# Disk Quota & Space Optimizer Agent

A Python demonstration of the Disk Optimizer specialist in an Agentic Shell. An Ollama model receives a natural-language request, chooses from the MCP tools, and uses their results to find matching files. Before deletion, the host displays the exact files and asks the user to type `DELETE`.

## Request flow

```text
Natural-language request
        ↓
Ollama model selects an MCP tool
        ↓
MCP server runs df, du, or stat
        ↓
LLM selects matching files and totals their sizes
        ↓
Host shows the exact selection and asks for approval
        ↓
MCP delete_files removes approved files and the host verifies
```

## MCP tools

| Tool | Linux utility | Purpose |
| --- | --- | --- |
| `get_disk_stats` | `df` | Reports filesystem capacity and available space. |
| `get_directory_usage` | `du` | Lists file paths and byte sizes for the allowed demo folder. |
| `get_file_metadata` | `stat` | Reports file size, modification time, and type. |
| `delete_files` | Python file operation | Removes selected files after the host obtains user approval. |

The LLM uses disk usage and metadata results to apply the user's age, size, and location constraints and calculate the candidate total.

## Safety

- By default, files are limited to `~/Downloads/disk_optimizer_demo`.
- Set `DISK_OPTIMIZER_ROOT` to use another dedicated demo folder.
- Paths outside the configured folder, symbolic links, and non-files are rejected.
- The LLM cannot approve its own deletion. `agentic_shell.py` displays the selected paths and sizes, then requires the user to type `DELETE` before it calls `delete_files`.
- The MCP server revalidates every path before removal and runs fixed Linux utilities without passing user text to a shell.

## Requirements

- Linux with `df`, `du`, and `stat`
- Python 3.11 or newer
- Ollama with the `qwen3:0.6b` model

## Install and prepare the demo

From the project folder in Ubuntu:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull qwen3:0.6b
mkdir -p "$HOME/Downloads/disk_optimizer_demo"
python3 agentic_shell.py --setup-demo
```

If Ollama is not already running, start it in a separate terminal with `ollama serve`.

## Run

```bash
source .venv/bin/activate
python3 agentic_shell.py
```

Try these requests:

```text
Find text files older than 30 days and show their total size. Do not delete anything.
Delete old_notes.txt from the demo folder.
```

For the second request, the host shows the exact file and size. Type `DELETE` to approve or anything else to cancel.

## Project scope

`agentic_shell.py` demonstrates the LLM-to-MCP flow for this one specialist agent. The full class Agentic Shell router for all 35 agents is outside this repository. `diskopti_cli.py` is an earlier standalone CLI demo and does not use the LLM-to-MCP flow.
