"""MCP tools for a safe, demo-folder-only Linux disk optimizer."""

from __future__ import annotations

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


def _check_root() -> str | None:
    if not ROOT.is_dir():
        return f"The allowed demo folder does not exist: {ROOT}"
    return None


def _safe_file(relative_path: str) -> Path:
    """Resolve one regular file while rejecting traversal and symlinks."""
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Provide a relative file path inside the allowed folder.")

    candidate = ROOT
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Symbolic links are not allowed.")

    resolved = candidate.resolve(strict=True)
    resolved.relative_to(ROOT)
    if not resolved.is_file():
        raise ValueError("The selected path is not a regular file.")
    return resolved


@SERVER.tool()
def get_disk_space() -> str:
    """Check total and available disk space for the allowed demo folder using df."""
    problem = _check_root()
    if problem:
        return problem
    result = subprocess.run(
        ["df", "-h", "--", str(ROOT)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@SERVER.tool()
def get_folder_usage() -> str:
    """Check the total size of the allowed demo folder using du."""
    problem = _check_root()
    if problem:
        return problem
    result = subprocess.run(
        ["du", "-sh", "--", str(ROOT)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@SERVER.tool()
def list_candidates(
    extension: str = "",
    older_than_days: int = 0,
    largest_first: bool = True,
    limit: int = 30,
) -> str:
    """List files in the demo folder, optionally filtering by extension or age.

    File sizes are measured with du. Returned paths are relative to the demo folder.
    """
    problem = _check_root()
    if problem:
        return problem
    if older_than_days < 0:
        return "older_than_days must be zero or greater."

    extension = extension.strip().lower()
    if extension and not extension.startswith("."):
        extension = "." + extension
    maximum = max(1, min(limit, 100))
    cutoff = time.time() - older_than_days * 86400
    candidates: list[tuple[int, str]] = []

    for folder, directories, filenames in os.walk(ROOT, followlinks=False):
        current = Path(folder)
        directories[:] = [
            name for name in directories if not (current / name).is_symlink()
        ]

        for filename in filenames:
            path = current / filename
            if path.is_symlink() or (extension and path.suffix.lower() != extension):
                continue

            try:
                if older_than_days and path.stat().st_mtime > cutoff:
                    continue
                size_result = subprocess.run(
                    ["du", "-b", "--", str(path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                size_bytes = int(size_result.stdout.split(maxsplit=1)[0])
                relative = path.relative_to(ROOT).as_posix()
                candidates.append((size_bytes, relative))
            except (OSError, ValueError, subprocess.CalledProcessError):
                continue

    candidates.sort(key=lambda item: item[0], reverse=largest_first)
    candidates = candidates[:maximum]
    if not candidates:
        return "No matching files were found in the allowed demo folder."

    total_bytes = sum(size for size, _ in candidates)
    lines = [f"Candidates (combined size: {total_bytes:,} bytes):"]
    lines.extend(f"{size:,} bytes | {name}" for size, name in candidates)
    return "\n".join(lines)


@SERVER.tool()
def get_file_details(relative_path: str) -> str:
    """Show file metadata with stat for a relative path in the allowed folder."""
    try:
        path = _safe_file(relative_path)
    except (ValueError, OSError) as error:
        return f"Could not inspect file: {error}"

    result = subprocess.run(
        ["stat", "--format=Name: %n\nSize: %s bytes\nModified: %y\nPermissions: %A", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@SERVER.tool()
def delete_files(relative_paths: list[str], approved: bool = False) -> str:
    """Delete selected files only after the MCP host has obtained user approval.

    The MCP host must show the exact paths to the user and set approved=true only
    after the user explicitly confirms. Only regular files inside the demo folder
    can be removed; directories and symbolic links are rejected.
    """
    problem = _check_root()
    if problem:
        return problem
    if not approved:
        return (
            "No files were deleted. Show the exact paths to the user and obtain "
            "explicit approval before calling again with approved=true."
        )
    if not relative_paths:
        return "No files were selected."
    if len(relative_paths) > 20:
        return "Select no more than 20 files per deletion request."

    try:
        paths = [_safe_file(name) for name in dict.fromkeys(relative_paths)]
    except (ValueError, OSError) as error:
        return f"No files were deleted: {error}"

    deleted: list[str] = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        path.unlink()
        deleted.append(relative)
    return "Deleted after user approval: " + ", ".join(deleted)


if __name__ == "__main__":
    # MCP local servers use stdio. The MCP host launches this process.
    SERVER.run(transport="stdio")
