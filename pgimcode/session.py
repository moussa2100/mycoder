"""Session model, storage, and XDG management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_config_dir

from pgimcode.config import Settings
from pgimcode.events import Event

from ulid import ULID


def _new_ulid() -> str:
    return f"pgim-{ULID()}"


@dataclass
class Session:
    """A single coding session."""

    id: str
    task: str
    mode: str = "build"
    status: str = "running"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    step_count: int = 0


def _session_dir(root: Path) -> Path:
    d = root / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


class SessionStore:
    """Create, save, load, and list sessions on disk."""

    def __init__(self, tmp_root: Path | None = None):
        if tmp_root:
            self._root = tmp_root
        else:
            self._root = Path(user_config_dir(Settings().app_name))
        self._session_dir = _session_dir(self._root)

    def create(self, task: str, mode: str = "build") -> Session:
        return Session(id=_new_ulid(), task=task, mode=mode)

    def save(self, session: Session) -> None:
        meta = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in asdict(session).items()}
        meta_path = self._session_dir / f"{session.id}.meta.json"
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def get(self, session_id: str) -> Session | None:
        meta_path = self._session_dir / f"{session_id}.meta.json"
        if not meta_path.exists():
            return None
        with meta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return Session(**data)

    def list_sessions(self) -> list[Session]:
        sessions = []
        for meta_path in self._session_dir.glob("*.meta.json"):
            session_id = meta_path.name.removesuffix(".meta.json")
            s = self.get(session_id)
            if s:
                sessions.append(s)
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def jsonl_path(self, session_id: str) -> Path:
        return self._session_dir / f"{session_id}.jsonl"

    def append_event(self, session_id: str, event: Event) -> Path:
        path = self.jsonl_path(session_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
        return path

    def update(self, session: Session) -> None:
        self.save(session)