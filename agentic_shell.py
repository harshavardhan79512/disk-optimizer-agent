"""Small Ollama host that routes natural-language prompts to MCP disk tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from mcp import Client, StdioServerParameters
from ollama import chat


PROJECT_DIR = Path(__file__).resolve().parent
SERVER_FILE = PROJECT_DIR / "disk_optimizer_server.py"
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
DEMO_FOLDER = Path(
    os.environ.get(
        "DISK_OPTIMIZER_ROOT",
        str(Path.home() / "Downloads" / "disk_optimizer_demo"),
    )
).expanduser().resolve()

SYSTEM_PROMPT = f"""You are the Disk Quota & Space Optimizer specialist inside an Agentic Shell.
The MCP server limits all file access to: {DEMO_FOLDER}
Use the registered MCP tools to inspect disk space and files. Never invent tool
results or execute shell commands. For cleanup requests, call get_directory_usage
with age and extension filters; it returns the matching paths and exact combined
size. Use get_file_metadata to inspect selected files. Only call delete_files when the user requested deletion;
the host will show the exact paths and ask for approval before executing it.
The allowed folder is fixed; do not pass directory paths to get_directory_usage.
Use only relative file paths returned by the tools when calling get_file_metadata
or delete_files. Do not pass the absolute allowed-folder path to any tool.
If the user declines, do not retry deletion. Report only results returned by tools.
"""


def setup_demo_files() -> None:
    """Create harmless examples in the configured demo folder."""
    DEMO_FOLDER.mkdir(parents=True, exist_ok=True)
    old_file = DEMO_FOLDER / "old_notes.txt"
    current_file = DEMO_FOLDER / "meeting_notes.txt"
    if not old_file.exists():
        old_file.write_text("Sample old file for the demo.\n" * 100, encoding="utf-8")
    # Reset the demo timestamp on every setup run so the age filter is repeatable.
    old_time = time.time() - (45 * 86400)
    os.utime(old_file, (old_time, old_time))
    if not current_file.exists():
        current_file.write_text("Sample current file for the demo.\n" * 40, encoding="utf-8")
    print(f"Created demo samples in: {DEMO_FOLDER}")


def _tool_schema(tool) -> dict:
    schema = getattr(tool, "input_schema", None)
    if schema is None:
        schema = getattr(tool, "inputSchema", None)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema or {"type": "object", "properties": {}},
        },
    }


def _result_text(result) -> str:
    parts = []
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    return json.dumps(getattr(result, "structured_content", None) or {})


def _requested_usage_filters(user_text: str) -> dict:
    """Extract simple explicit age/extension constraints to validate tool args."""
    filters = {}
    age = re.search(
        r"\b(?:older|more than|over)\s+(?:than\s+)?(\d+)\s+days?\b",
        user_text,
        flags=re.IGNORECASE,
    )
    if age:
        filters["older_than_days"] = int(age.group(1))

    extension = re.search(r"\.([a-zA-Z0-9]{1,8})\b", user_text)
    if extension:
        filters["extension"] = "." + extension.group(1).lower()
    elif re.search(r"\btext files?\b", user_text, flags=re.IGNORECASE):
        filters["extension"] = ".txt"
    return filters


async def _delete_after_host_approval(client: Client, arguments: dict) -> str:
    paths = arguments.get("paths", [])
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        return "Deletion cancelled: the model did not provide a valid file list."
    if len(paths) > 20:
        return "Deletion cancelled: select no more than 20 files at a time."

    previews = []
    for path in dict.fromkeys(paths):
        print(f"\n[MCP tool] get_file_metadata(relative_path={path!r})")
        result = await client.call_tool("get_file_metadata", {"relative_path": path})
        if getattr(result, "is_error", False):
            return f"Deletion cancelled: could not inspect {path}."
        try:
            metadata = json.loads(_result_text(result))
        except json.JSONDecodeError:
            return f"Deletion cancelled: metadata for {path} was invalid."
        if "error" in metadata:
            return f"Deletion cancelled: {metadata['error']}"
        previews.append(metadata)

    total = sum(int(item["size_bytes"]) for item in previews)
    print("\nDeletion preview:")
    for item in previews:
        print(f"  {item['path']} ({int(item['size_bytes']):,} bytes)")
    print(f"Total selected: {total:,} bytes")
    approval = input("Type DELETE to approve these exact files: ").strip()
    if approval != "DELETE":
        return "User declined. No files were deleted."

    print("\n[MCP tool] delete_files(paths=approved selection)")
    result = await client.call_tool(
        "delete_files", {"paths": [item["path"] for item in previews]}
    )
    deleted_text = _result_text(result)
    if getattr(result, "is_error", False):
        return f"Deletion tool reported an error: {deleted_text}"

    print("[MCP tool] get_directory_usage() - verify remaining files")
    verification = await client.call_tool(
        "get_directory_usage", {}
    )
    return (
        f"Deletion result: {deleted_text}\n"
        f"Remaining files after verification: {_result_text(verification)}"
    )


async def run_shell() -> None:
    if not SERVER_FILE.is_file():
        print(f"MCP server not found: {SERVER_FILE}")
        return
    if not DEMO_FOLDER.is_dir():
        print(f"Demo folder not found: {DEMO_FOLDER}")
        print("First run: python3 agentic_shell.py --setup-demo")
        return

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_FILE)],
        cwd=str(PROJECT_DIR),
        env={"DISK_OPTIMIZER_ROOT": str(DEMO_FOLDER)},
    )

    print("Disk Quota & Space Optimizer Agent")
    print(f"LLM model: {MODEL}")
    print(f"Allowed folder: {DEMO_FOLDER}")
    print("Type 'exit' to quit.\n")

    async with Client(server) as client:
        mcp_tools = await client.list_tools()
        ollama_tools = [_tool_schema(tool) for tool in mcp_tools.tools]
        tool_names = {tool.name for tool in mcp_tools.tools}
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        while True:
            user_text = input("You: ").strip()
            if user_text.lower() in {"exit", "quit"}:
                break
            if not user_text:
                continue
            messages.append({"role": "user", "content": user_text})

            try:
                for _ in range(8):
                    response = chat(model=MODEL, messages=messages, tools=ollama_tools)
                    assistant_message = response.message
                    messages.append(assistant_message)
                    calls = assistant_message.tool_calls or []
                    if not calls:
                        print(f"\nAgent: {assistant_message.content or ''}\n")
                        break

                    for call in calls:
                        name = call.function.name
                        arguments = dict(call.function.arguments or {})
                        print(
                            f"\n[LLM selected MCP tool] {name}"
                            f"({json.dumps(arguments, ensure_ascii=False)})"
                        )
                        if name not in tool_names:
                            tool_output = f"Tool is not available: {name}"
                        elif name == "delete_files":
                            tool_output = await _delete_after_host_approval(client, arguments)
                        else:
                            if name == "get_directory_usage":
                                arguments.update(_requested_usage_filters(user_text))
                                print(
                                    "[Host applied request filters] "
                                    f"{json.dumps(arguments, ensure_ascii=False)}"
                                )
                            result = await client.call_tool(name, arguments)
                            tool_output = _result_text(result)
                            print(f"[MCP result] {tool_output}")
                            if getattr(result, "is_error", False):
                                tool_output = f"MCP tool error: {tool_output}"

                        messages.append(
                            {"role": "tool", "tool_name": name, "content": tool_output}
                        )
                else:
                    print("Agent stopped after the tool-call limit for this request.\n")
            except Exception as error:
                print(f"\nCould not complete the request: {error}")
                print("Check that Ollama is running, the model is installed, and MCP dependencies are available.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ollama + MCP disk agent demo.")
    parser.add_argument(
        "--setup-demo",
        action="store_true",
        help="Create safe sample files inside the configured demo folder.",
    )
    args = parser.parse_args()
    if args.setup_demo:
        setup_demo_files()
        return
    asyncio.run(run_shell())


if __name__ == "__main__":
    main()
