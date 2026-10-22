from pathlib import Path
import os
import subprocess
import time

DEMO = (Path.home() / "Downloads" / "disk_optimizer_demo").resolve()
DEMO.mkdir(parents=True, exist_ok=True)

def run(command):
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout

def get_disk_stats():
    print(run(["df", "-h", "--", str(Path.home())]))

def get_directory_usage():
    print(run(["du", "-ah", "--", str(DEMO)]))

def safe_file(name):
    path = Path(name)
    if not path.is_absolute():
        path = DEMO / path
    if path.is_symlink():
        raise ValueError("Symbolic links are not allowed.")
    path = path.resolve(strict=True)
    if DEMO not in path.parents or not path.is_file():
        raise ValueError("Choose a file inside the demo folder.")
    return path

def get_file_metadata(name):
    path = safe_file(name)
    print(run(["stat", "--format=Name: %n | Size: %s bytes | Modified: %y",
               "--", str(path)]))

def delete_file(name):
    path = safe_file(name)
    get_file_metadata(name)
    if input("Type DELETE to remove this demo file: ") == "DELETE":
        path.unlink()
        print(f"Deleted {path.name}")
    else:
        print("Cancelled; file was kept.")

old = DEMO / "old_sample.txt"
if not old.exists():
    old.write_text("Disposable demo file\n")
    old_time = time.time() - 120 * 24 * 60 * 60
    os.utime(old, (old_time, old_time))

keep = DEMO / "keep_me.txt"
if not keep.exists():
    keep.write_text("Keep this demo file\n")

while True:
    print("\nDisk Optimizer CLI Demo")
    print("1. Check disk space (df)")
    print("2. List demo folder sizes (du)")
    print("3. Show old_sample.txt details (stat)")
    print("4. Delete old_sample.txt")
    print("0. Exit")
    choice = input("Choose: ")

    if choice == "1":
        get_disk_stats()
    elif choice == "2":
        get_directory_usage()
    elif choice == "3":
        get_file_metadata("old_sample.txt")
    elif choice == "4":
        delete_file("old_sample.txt")
    elif choice == "0":
        break
    else:
        print("Choose 0, 1, 2, 3, or 4.")

