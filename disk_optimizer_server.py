"""MCP tools for the Disk Quota & Space Optimizer specialist agent."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from mcp.server import MCPServer


SERVER = MCPServer("Disk Quota & Space Optimizer Agent")
ROOT = Path(
    os.environ.get(
        "DISK_OPTIMIZER_ROOT",
        str(Path.home() / "Downloads" / "disk_optimizer_demo"),
    )
).expanduser().resolve()


def _require_root() -> None:
    if not ROOT.is_dir():
        raise FileNotFoundError(f"Allowed demo folder does not exist: {ROOT}")


def _safe_path(relative_path: str, *, must_be_file: bool) -> Path:
    """Resolve a relative path while rejecting traversal and symbolic links."""
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Use a relative path inside the allowed demo folder.")

    candidate = ROOT
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Symbolic links are not allowed.")

    resolved = candidate.resolve(strict=True)
    resolved.relative_to(ROOT)
    if must_be_file and not resolved.is_file():
        raise ValueError("The selected path is not a regular file.")
    if not must_be_file and not resolved.is_dir():
        raise ValueError("The selected path is not a directory.")
    return resolved


@SERVER.tool()
def get_disk_stats() -> str:
    """Use df to report total, used, and available space for the demo filesystem."""
    _require_root()
    result = subprocess.run(
        ["df", "-P", "-B1", "--", str(ROOT)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@SERVER.tool()
def get_directory_usage(older_than_days: int = 0, extension: str = "") -> str:
    """Use du and stat to return files matching age and extension filters.

    Returns JSON with relative paths, exact byte sizes, ages, and a combined total.
    The allowed directory is fixed; do not pass an absolute path.
    """
    _require_root()
    if older_than_days < 0:
        return json.dumps({"error": "older_than_days must be zero or greater."})
    extension = extension.strip().lower()
    if extension and not extension.startswith("."):
        extension = "." + extension

    directory = ROOT

    result = subprocess.run(
        ["du", "-a", "-B1", "--null", "--", str(directory)],
        capture_output=True,
        text=True,
        check=True,
    )

    files = []
    now = time.time()
    for record in result.stdout.split("\0"):
        if not record:
            continue
        size_text, absolute_name = record.split("\t", 1)
        path = Path(absolute_name)
        if path.is_symlink() or not path.is_file():
            continue
        if extension and path.suffix.lower() != extension:
            continue
        stat_result = subprocess.run(
            ["stat", "--format=%Y", "--", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        modified_epoch = int(stat_result.stdout.strip())
        age_days = max(0, int((now - modified_epoch) // 86400))
        if older_than_days and age_days < older_than_days:
            continue
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": int(size_text),
                "age_days": age_days,
            }
        )

    files.sort(key=lambda item: item["size_bytes"], reverse=True)
    return json.dumps(
        {
            "filters": {"older_than_days": older_than_days, "extension": extension},
            "candidates": files,
            "total_bytes": sum(item["size_bytes"] for item in files),
        },
        indent=2,
    )


@SERVER.tool()
def get_file_metadata(relative_path: str) -> str:
    """Use stat to report a file's size, modification time, and type."""
    try:
        path = _safe_path(relative_path, must_be_file=True)
    except (ValueError, OSError) as error:
        return json.dumps({"error": str(error)})

    result = subprocess.run(
        ["stat", r"--printf=%n\0%s\0%Y\0%F\0", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    fields = result.stdout.split("\0")
    return json.dumps(
        {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": int(fields[1]),
            "modified_epoch": int(fields[2]),
            "file_type": fields[3],
        }
    )


@SERVER.tool()
def delete_files(paths: list[str]) -> str:
    """Delete only the relative file paths approved by the MCP host's user.

    The trusted host must show the exact paths and obtain user approval before
    calling this tool. The server independently restricts deletion to regular,
    non-symlink files inside the configured demo folder.
    """
    _require_root()
    if not paths:
        return json.dumps({"deleted": [], "message": "No files were selected."})
    if len(paths) > 20:
        return json.dumps({"error": "Select no more than 20 files at a time."})

    try:
        checked = [_safe_path(name, must_be_file=True) for name in dict.fromkeys(paths)]
    except (ValueError, OSError) as error:
        return json.dumps({"error": f"No files were deleted: {error}"})

    deleted = []
    for path in checked:
        deleted.append(path.relative_to(ROOT).as_posix())
        path.unlink()
    return json.dumps({"deleted": deleted})


if __name__ == "__main__":
    # Local MCP hosts launch the server over stdio.
    SERVER.run(transport="stdio")
