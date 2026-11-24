from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from omnidesk_engine.db import Database


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rollback_task_operations(db: Database, task_id: str) -> dict[str, Any]:
    """Reverts recorded reversible operations in reverse chronological order.

    Verifies SHA-256 digests before moving files back so post-task edits are never silently overwritten.
    """
    entries = db.get_journal_entries(task_id, include_reverted=False)
    if not entries:
        return {
            "task_id": task_id,
            "reverted_count": 0,
            "skipped_count": 0,
            "errors": ["No reversible operations remain for this task."],
        }

    reverted = 0
    skipped = 0
    errors: list[str] = []
    created_dirs: list[Path] = []

    for entry in entries:
        op_type = entry["op_type"]
        src = Path(entry["source_path"])
        dst = Path(entry["dest_path"])
        expected_hash = entry.get("sha256")

        if op_type == "mkdir":
            created_dirs.append(dst)
            db.mark_journal_reverted(entry["id"])
            continue

        if op_type in ("move", "rename"):
            if not dst.exists():
                skipped += 1
                errors.append(f"Skipped '{dst.name}': file no longer exists at destination.")
                continue
            if expected_hash and sha256_file(dst) != expected_hash:
                skipped += 1
                errors.append(f"Skipped '{dst.name}': file content changed after task completed.")
                continue
            if src.exists():
                skipped += 1
                errors.append(f"Skipped '{dst.name}': original path '{src}' is already occupied.")
                continue
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))
            db.mark_journal_reverted(entry["id"])
            reverted += 1

        elif op_type == "create_file":
            if dst.exists():
                if expected_hash and sha256_file(dst) != expected_hash:
                    skipped += 1
                    errors.append(f"Kept generated report '{dst.name}': modified after creation.")
                    continue
                dst.unlink()
                db.mark_journal_reverted(entry["id"])
                reverted += 1

    # Remove directories created by the task only if they are now empty.
    for folder in created_dirs:
        try:
            if folder.exists() and folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            pass

    task = db.get_task(task_id)
    if task and reverted > 0 and skipped == 0:
        task.undone = True
        task.can_undo = False
        db.save_task(task)

    db.add_audit(
        category="recovery",
        action="rollback_task",
        detail=f"Reverted {reverted} operation(s), skipped {skipped} for task {task_id}.",
        task_id=task_id,
    )
    return {
        "task_id": task_id,
        "reverted_count": reverted,
        "skipped_count": skipped,
        "errors": errors,
    }
