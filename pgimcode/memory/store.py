"""Persistent file-backed store for long-term agent memory.

Implements langgraph.store.base.BaseStore so it can be used directly
with ``create_deep_agent(store=...)`` and ``StoreBackend``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from langgraph.store.base import BaseStore, Item, SearchItem, Op, Result


class PersistentFileStore(BaseStore):
    """A file-system-backed store that persists each item as a JSON file.

    Structure on disk::

        <root>/
            <namespace[0]>/
                <namespace[1]>/
                    ...
                        <safe_key>.json

    Each JSON file is the ``Item.value`` dict directly.
    """

    supports_ttl: bool = False

    def __init__(self, root_dir: str | Path = ".pgim_memory") -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _item_path(self, namespace: tuple[str, ...], key: str) -> Path:
        """Resolve the JSON file path for a (namespace, key) pair."""
        safe_key = key.replace("\\", "/").strip("/").replace("/", "_")
        return self._root.joinpath(*namespace, f"{safe_key}.json")

    @staticmethod
    def _parse_ts(value: Any) -> datetime:
        """Parse a stored timestamp into a datetime (langgraph Items require it)."""
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)

    def _read_item(self, namespace: tuple[str, ...], key: str) -> Item | None:
        """Deserialise an Item from disk, or None."""
        p = self._item_path(namespace, key)
        if not p.exists():
            return None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        now = datetime.now(timezone.utc).isoformat()
        value = {
            "content": raw.get("content", ""),
            "encoding": raw.get("encoding", "utf-8"),
            "created_at": raw.get("created_at", now),
            "modified_at": raw.get("modified_at", now),
        }
        return Item(
            namespace=tuple(namespace),
            key=key,
            value=value,
            created_at=self._parse_ts(value["created_at"]),
            updated_at=self._parse_ts(value["modified_at"]),
        )

    def _write_item(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        """Serialise and persist a value dict."""
        p = self._item_path(namespace, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        wrapped = {
            "key": key,
            "content": value.get("content", ""),
            "encoding": value.get("encoding", "utf-8"),
            "created_at": value.get("created_at", now),
            "modified_at": value.get("modified_at", now),
        }
        p.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # BaseStore sync API
    # ------------------------------------------------------------------

    def get(self, namespace: tuple[str, ...], key: str, *, refresh_ttl: bool | None = None) -> Item | None:
        return self._read_item(namespace, key)

    def put(self, namespace: tuple[str, ...], key: str, value: dict[str, Any],
            index: bool | list[str] | None = None, *, ttl: float | None = None) -> None:
        self._write_item(namespace, key, value)

    def delete(self, namespace: tuple[str, ...], key: str) -> None:
        p = self._item_path(namespace, key)
        if p.exists():
            p.unlink()

    def search(self, namespace_prefix: tuple[str, ...], /, *,
               query: str | None = None,
               filter: dict[str, Any] | None = None,
               limit: int = 10,
               offset: int = 0,
               refresh_ttl: bool | None = None) -> list[SearchItem]:
        """List items under *namespace_prefix*, optionally filtered."""
        search_dir = self._root.joinpath(*namespace_prefix) if namespace_prefix else self._root
        if not search_dir.exists():
            return []

        items: list[SearchItem] = []
        for json_file in sorted(search_dir.rglob("*.json")):
            try:
                raw = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            # Original key (e.g. "/memories/AGENTS.md") is stored in the JSON;
            # fall back to the sanitized filename stem for legacy files.
            key = raw.get("key") or json_file.stem
            rel = json_file.relative_to(self._root)
            parts = rel.as_posix().rsplit("/", 1)[0].split("/")
            ns = tuple(parts) if parts != ("",) else namespace_prefix
            item = self._read_item(ns, key)
            if item is None:
                continue
            if query and query.lower() not in (item.value.get("content", "") or "").lower():
                continue
            items.append(SearchItem(
                namespace=ns,
                key=key,
                value=item.value,
                created_at=item.created_at,
                updated_at=item.updated_at,
                score=1.0,
            ))

        return items[offset:offset + limit]

    def list_namespaces(self, *, prefix: tuple[str, ...] | None = None,
                        suffix: tuple[str, ...] | None = None,
                        max_depth: int | None = None,
                        limit: int = 100,
                        offset: int = 0) -> list[tuple[str, ...]]:
        """List unique namespaces on disk."""
        root = self._root.joinpath(*prefix) if prefix else self._root
        if not root.exists():
            return []

        namespaces: set[tuple[str, ...]] = set()
        for json_file in root.rglob("*.json"):
            rel = json_file.relative_to(self._root)
            ns = tuple(rel.parent.as_posix().split("/"))
            namespaces.add(ns)

        result = sorted(namespaces)
        return result[offset:offset + limit]

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        """Execute a batch of operations."""
        from langgraph.store.base import GetOp, PutOp, SearchOp, DeleteOp, ListNamespacesOp

        results: list[Result] = []
        for op in ops:
            if isinstance(op, GetOp):
                item = self.get(op.namespace, op.key)
                results.append(Result(
                    key=op.key,
                    namespace=op.namespace,
                    value=item.value if item else None,
                ))
            elif isinstance(op, PutOp):
                self.put(op.namespace, op.key, op.value, op.index)
                results.append(Result(key=op.key, namespace=op.namespace, value=op.value))
            elif isinstance(op, DeleteOp):
                self.delete(op.namespace, op.key)
                results.append(Result(key=op.key, namespace=op.namespace, value=None))
            elif isinstance(op, SearchOp):
                items = self.search(
                    op.namespace_prefix,
                    query=op.query,
                    filter=op.filter,
                    limit=op.limit,
                    offset=op.offset,
                )
                results.append(Result(namespace=op.namespace_prefix, key="", value=items))
            elif isinstance(op, ListNamespacesOp):
                nss = self.list_namespaces(
                    prefix=op.match_conditions.prefix,
                    max_depth=op.max_depth,
                    limit=op.limit,
                    offset=op.offset,
                )
                results.append(Result(namespace=(), key="", value=nss))

        return results

    # ------------------------------------------------------------------
    # Async API (trivially delegating to sync)
    # ------------------------------------------------------------------

    async def aget(self, namespace: tuple[str, ...], key: str, *,
                   refresh_ttl: bool | None = None) -> Item | None:
        return self.get(namespace, key)

    async def aput(self, namespace: tuple[str, ...], key: str, value: dict[str, Any],
                   index: bool | list[str] | None = None, *, ttl: float | None = None) -> None:
        self.put(namespace, key, value, index)

    async def adelete(self, namespace: tuple[str, ...], key: str) -> None:
        self.delete(namespace, key)

    async def asearch(self, namespace_prefix: tuple[str, ...], /, *,
                      query: str | None = None,
                      filter: dict[str, Any] | None = None,
                      limit: int = 10,
                      offset: int = 0,
                      refresh_ttl: bool | None = None) -> list[SearchItem]:
        return self.search(namespace_prefix, query=query, filter=filter, limit=limit, offset=offset)

    async def alist_namespaces(self, *, prefix: tuple[str, ...] | None = None,
                                suffix: tuple[str, ...] | None = None,
                                max_depth: int | None = None,
                                limit: int = 100,
                                offset: int = 0) -> list[tuple[str, ...]]:
        return self.list_namespaces(prefix=prefix, suffix=suffix, max_depth=max_depth, limit=limit, offset=offset)

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return self.batch(ops)
