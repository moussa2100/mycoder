"""Shared dataclasses for evidence and task tracking."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class EvidenceItem:
    id: str
    claim: str
    source: str
    file_path: str | None = None
    confidence: float = 0.5
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskBoardItem:
    key: str
    label: str
    status: str = "pending"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CandidateFile:
    path: str
    score: float
    reason: str
    related_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
