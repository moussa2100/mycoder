"""Pre-edit snapshot management for rollback."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Snapshot:
    id: str
    created_at: str
    paths: list[str]
    root: str


class SnapshotManager:
    def __init__(self, session_dir: Path):
        self._snaps_dir = session_dir / "snapshots"
        self._snaps_dir.mkdir(parents=True, exist_ok=True)

    def _make_id(self, paths: list[Path]) -> str:
        import time
        hasher = hashlib.sha256()
        for p in sorted(str(p) for p in paths):
            hasher.update(p.encode())
        # Add timestamp with microseconds to ensure uniqueness
        ts = time.time()
        return f"snap-{ts:.6f}-{hasher.hexdigest()[:8]}"

    def save(self, paths: list[Path], root: Path | None = None) -> str:
        """Save copies of files. Returns snapshot ID."""
        snap_id = self._make_id(paths)
        snap_dir = self._snaps_dir / snap_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        for p in paths:
            if p.exists():
                dest = snap_dir / p.name
                shutil.copy2(p, dest)

        meta = Snapshot(
            id=snap_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            paths=[str(p) for p in paths],
            root=str(root) if root else ".",
        )
        meta_path = snap_dir / "snapshot.meta.json"
        meta_path.write_text(json.dumps(meta.__dict__, indent=2))

        return snap_id

    def restore(self, snap_id: str) -> list[Path]:
        """Restore files from snapshot to original paths. Returns list of restored paths."""
        snap_dir = self._snaps_dir / snap_id
        meta_path = snap_dir / "snapshot.meta.json"
        if not meta_path.exists():
            return []
        data = json.loads(meta_path.read_text())
        restored = []
        for p_str in data.get("paths", []):
            original = Path(p_str)
            backup = snap_dir / original.name
            if backup.exists():
                shutil.copy2(backup, original)
                restored.append(original)
        return restored

    def delete(self, snap_id: str) -> None:
        snap_dir = self._snaps_dir / snap_id
        if snap_dir.exists():
            shutil.rmtree(snap_dir)

    def list_snapshots(self) -> list[Snapshot]:
        snaps = []
        for meta_path in self._snaps_dir.glob("*/snapshot.meta.json"):
            data = json.loads(meta_path.read_text())
            snaps.append(Snapshot(**data))
        return snaps