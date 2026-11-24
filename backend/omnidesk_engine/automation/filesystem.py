from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omnidesk_engine.db import Database
from omnidesk_engine.security.journal import sha256_file
from omnidesk_engine.security.policy import validate_child_path, validate_scoped_directory

CATEGORY_MAP: dict[str, str] = {
    # Documents
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".txt": "Documents",
    ".md": "Documents",
    ".rtf": "Documents",
    ".odt": "Documents",
    ".pages": "Documents",
    # Spreadsheets
    ".xls": "Spreadsheets",
    ".xlsx": "Spreadsheets",
    ".csv": "Spreadsheets",
    ".tsv": "Spreadsheets",
    ".ods": "Spreadsheets",
    ".numbers": "Spreadsheets",
    # Presentations
    ".ppt": "Presentations",
    ".pptx": "Presentations",
    ".key": "Presentations",
    # Images
    ".png": "Images",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".webp": "Images",
    ".gif": "Images",
    ".svg": "Images",
    ".heic": "Images",
    ".tiff": "Images",
    # Audio & Video
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".m4a": "Audio",
    ".mp4": "Video",
    ".mov": "Video",
    ".mkv": "Video",
    ".webm": "Video",
    # Archives
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".tgz": "Archives",
    ".7z": "Archives",
    ".rar": "Archives",
    # Installers
    ".dmg": "Installers",
    ".pkg": "Installers",
    ".msi": "Installers",
    ".exe": "Installers",
    ".deb": "Installers",
    ".rpm": "Installers",
    ".appimage": "Installers",
    # Code & Data
    ".py": "Code",
    ".ts": "Code",
    ".tsx": "Code",
    ".js": "Code",
    ".rs": "Code",
    ".json": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".toml": "Code",
    ".html": "Code",
    ".css": "Code",
    ".sql": "Code",
}

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".ts", ".js", ".log", ".html"}


def classify_extension(path: Path) -> str:
    return CATEGORY_MAP.get(path.suffix.lower(), "Other")


def inspect_directory(
    directory: str | Path,
    allowed_roots: list[str] | None = None,
    include_subdirectories: bool = False,
) -> dict[str, Any]:
    root = validate_scoped_directory(directory, allowed_roots=allowed_roots)
    files: list[dict[str, Any]] = []
    size_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)

    iterator = root.rglob("*") if include_subdirectories else root.iterdir()
    for item in sorted(iterator):
        if item.name.startswith(".") or not item.is_file() or item.is_symlink():
            continue
        stat = item.stat()
        rec = {
            "name": item.name,
            "path": str(item.resolve()),
            "relative_path": str(item.relative_to(root)),
            "extension": item.suffix.lower() or "(none)",
            "category": classify_extension(item),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "sha256": None,
        }
        files.append(rec)
        size_buckets[stat.st_size].append(rec)

    # Two-stage duplicate verification: hash only files sharing identical byte size.
    hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for size_val, group in size_buckets.items():
        if len(group) < 2:
            continue
        for rec in group:
            digest = sha256_file(Path(rec["path"]))
            rec["sha256"] = digest
            hash_groups[digest].append(rec)

    duplicate_groups: list[dict[str, Any]] = []
    for digest, members in hash_groups.items():
        if len(members) >= 2:
            duplicate_groups.append(
                {
                    "sha256": digest,
                    "size_bytes": members[0]["size_bytes"],
                    "count": len(members),
                    "files": [m["name"] for m in members],
                    "paths": [m["path"] for m in members],
                }
            )

    category_counts: dict[str, int] = defaultdict(int)
    total_bytes = 0
    for f in files:
        category_counts[f["category"]] += 1
        total_bytes += f["size_bytes"]

    return {
        "directory": str(root),
        "total_files": len(files),
        "total_bytes": total_bytes,
        "categories": dict(sorted(category_counts.items())),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_file_count": sum(g["count"] for g in duplicate_groups),
        "duplicates": duplicate_groups,
        "files": files,
    }


def plan_organization(
    directory: str | Path,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    inspection = inspect_directory(directory, allowed_roots=allowed_roots, include_subdirectories=False)
    root = Path(inspection["directory"])
    moves: list[dict[str, Any]] = []
    planned_targets: set[Path] = set()

    for rec in inspection["files"]:
        src = Path(rec["path"])
        # Keep generated OmniDesk reports at the root of the folder for visibility.
        if src.name.startswith("OmniDesk_") and src.suffix.lower() == ".xlsx":
            continue
        category = rec["category"]
        target_dir = validate_child_path(root, root / category)
        candidate = target_dir / src.name
        counter = 1
        while candidate.exists() or candidate in planned_targets:
            candidate = target_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1
        planned_targets.add(candidate)
        moves.append(
            {
                "file_name": src.name,
                "category": category,
                "source_path": str(src),
                "dest_path": str(candidate),
                "size_bytes": rec["size_bytes"],
            }
        )

    return {
        "directory": str(root),
        "planned_move_count": len(moves),
        "deletions_count": 0,
        "categories": inspection["categories"],
        "duplicate_groups": inspection["duplicates"],
        "moves": moves,
        "inspection": inspection,
    }


def apply_organization(
    db: Database,
    task_id: str,
    step_id: str,
    directory: str | Path,
    planned_moves: list[dict[str, Any]],
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    root = validate_scoped_directory(directory, allowed_roots=allowed_roots)
    moved: list[dict[str, Any]] = []
    created_dirs: set[str] = set()
    skipped: list[str] = []

    for item in planned_moves:
        src = validate_child_path(root, Path(item["source_path"]))
        dst = validate_child_path(root, Path(item["dest_path"]))
        if not src.exists():
            skipped.append(f"Missing source: {src.name}")
            continue
        if dst.exists():
            skipped.append(f"Destination already exists: {dst.name}")
            continue

        digest = sha256_file(src)
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if str(dst.parent) not in created_dirs:
                created_dirs.add(str(dst.parent))
                db.record_journal(task_id, step_id, "mkdir", str(dst.parent), str(dst.parent))

        shutil.move(str(src), str(dst))
        # Verify destination integrity after moving.
        verified_digest = sha256_file(dst)
        if verified_digest != digest:
            raise RuntimeError(f"Checksum mismatch after moving '{src.name}'.")

        db.record_journal(task_id, step_id, "move", str(src), str(dst), sha256=verified_digest)
        moved.append(
            {
                "file_name": src.name,
                "category": item.get("category", classify_extension(dst)),
                "source_path": str(src),
                "dest_path": str(dst),
                "size_bytes": dst.stat().st_size,
                "sha256": verified_digest,
            }
        )

    return {
        "directory": str(root),
        "moved_count": len(moved),
        "skipped_count": len(skipped),
        "deletions_count": 0,
        "moved": moved,
        "skipped": skipped,
        "verified": True,
    }


def create_directory(
    db: Database,
    task_id: str,
    step_id: str,
    parent_dir: str | Path,
    folder_name: str,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    root = validate_scoped_directory(parent_dir, allowed_roots=allowed_roots)
    target = validate_child_path(root, root / folder_name.strip())
    existed = target.exists()
    target.mkdir(parents=True, exist_ok=True)
    if not existed:
        db.record_journal(task_id, step_id, "mkdir", str(target), str(target))
    return {"created": not existed, "path": str(target)}


def rename_file(
    db: Database,
    task_id: str,
    step_id: str,
    directory: str | Path,
    old_name: str,
    new_name: str,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    root = validate_scoped_directory(directory, allowed_roots=allowed_roots)
    src = validate_child_path(root, root / old_name)
    dst = validate_child_path(root, root / new_name)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src.name}")
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst.name}")
    digest = sha256_file(src)
    shutil.move(str(src), str(dst))
    db.record_journal(task_id, step_id, "rename", str(src), str(dst), sha256=digest)
    return {"old_path": str(src), "new_path": str(dst), "sha256": digest}


def search_documents(
    directory: str | Path,
    query: str,
    allowed_roots: list[str] | None = None,
    max_results: int = 40,
) -> dict[str, Any]:
    root = validate_scoped_directory(directory, allowed_roots=allowed_roots)
    needle = query.strip().lower()
    matches: list[dict[str, Any]] = []
    scanned = 0

    for item in sorted(root.rglob("*")):
        if not item.is_file() or item.name.startswith(".") or item.is_symlink():
            continue
        scanned += 1
        name_hit = needle in item.name.lower()
        snippet: str | None = None

        if item.suffix.lower() in TEXT_EXTENSIONS and item.stat().st_size <= 512_000:
            try:
                text = item.read_text(encoding="utf-8", errors="ignore")
                idx = text.lower().find(needle)
                if idx != -1:
                    start = max(0, idx - 60)
                    end = min(len(text), idx + len(needle) + 100)
                    snippet = text[start:end].replace("\n", " ").strip()
            except OSError:
                pass

        if name_hit or snippet is not None:
            matches.append(
                {
                    "name": item.name,
                    "path": str(item.resolve()),
                    "category": classify_extension(item),
                    "size_bytes": item.stat().st_size,
                    "match_type": "content" if snippet else "filename",
                    "snippet": snippet,
                }
            )
            if len(matches) >= max_results:
                break

    return {
        "directory": str(root),
        "query": query,
        "scanned_files": scanned,
        "match_count": len(matches),
        "matches": matches,
    }
