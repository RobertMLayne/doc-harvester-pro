from pathlib import Path

exclude_dir = Path(".venv").resolve()

for path in sorted(Path(".").rglob("*")):
    try:
        # Skip anything inside .venv
        if exclude_dir in path.resolve().parents or path.resolve() == exclude_dir:
            continue
    except Exception:
        continue  # In case of permission errors, skip

    if path.is_file():
        print(f"\n--- {path} ---")
        try:
            content = path.read_text(encoding='utf-8').strip()
            print(content)
        except Exception:
            print("[binary or unreadable]")
