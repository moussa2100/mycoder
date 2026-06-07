"""Ripgrep-based search wrapper."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GrepResult:
    path: Path
    line_number: int
    text: str
    context_before: list[str]
    context_after: list[str]


def rg_search(
    query: str,
    root: Path,
    glob: str | None = None,
    max_results: int = 50,
    context_lines: int = 2,
) -> list[GrepResult]:
    """Run ripgrep and return structured results."""
    cmd = [
        "rg",
        "--json",
        "--max-count", "1",
        "--max-columns", "200",
        "--line-number",
        "--context", str(context_lines),
        "--heading",
        "--color=never",
    ]
    if glob:
        cmd += ["--glob", glob]
    cmd += [query, str(root)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return [GrepResult(
            path=root,
            line_number=0,
            text=f"[Error: ripgrep (rg) not found. Install it from https://github.com/BurntSushi/ripgrep]",
            context_before=[],
            context_after=[],
        )]
    except Exception as e:
        return [GrepResult(
            path=root,
            line_number=0,
            text=f"[Error: {e}]",
            context_before=[],
            context_after=[],
        )]

    results = []
    current_match = None
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        kind = obj.get("type")
        if kind == "match":
            data = obj.get("data", {})
            path_data = data.get("path", {})
            path_text = path_data.get("text", "")
            abs_path = (root / path_text) if not Path(path_text).is_absolute() else Path(path_text)
            lines = data.get("lines", {})
            line_num = data.get("line_number", 0)
            text = lines.get("text", "") if isinstance(lines, dict) else ""
            current_match = {
                "path": abs_path,
                "line_number": line_num,
                "text": text,
                "before": [],
                "after": [],
            }
        elif kind == "context" and current_match:
            data = obj.get("data", {})
            lines = data.get("lines", {})
            text = lines.get("text", "") if isinstance(lines, dict) else ""
            if data.get("lines_before", False):
                current_match["before"].append(text)
            else:
                current_match["after"].append(text)
        elif kind == "end" and current_match:
            results.append(GrepResult(
                path=current_match["path"],
                line_number=current_match["line_number"],
                text=current_match["text"],
                context_before=current_match["before"],
                context_after=current_match["after"],
            ))
            current_match = None
            if len(results) >= max_results:
                break

    return results


def rg_search_symbol(symbol_name: str, root: Path, language: str = "python") -> list[GrepResult]:
    """Search for a symbol definition in a language-aware way."""
    if language == "python":
        query = f"^(def|class)\\s+{symbol_name}\\b"
    elif language in ("javascript", "typescript"):
        query = f"^(function|class|const|let|var)\\s+{symbol_name}\\b"
    elif language == "rust":
        query = f"^(fn|struct|impl|trait)\\s+{symbol_name}\\b"
    elif language == "go":
        query = f"^(func)\\s+.*\\b{symbol_name}\\b"
    elif language == "java":
        query = f"^(public|private|protected)?\\s*(class|interface|void|\\w+)\\s+{symbol_name}\\b"
    else:
        query = f"\\b{symbol_name}\\b"
    return rg_search(query, root, glob=None, max_results=20, context_lines=0)