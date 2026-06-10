"""Tree-sitter powered code reading tools.

All code-file reads go through tree-sitter: every read returns a structural
outline (classes, functions, imports) extracted from the parse tree, plus the
requested source. Parsed symbols are cached by (path, mtime, size) so repeated
reads of the same file are cheap.
"""

from __future__ import annotations

from pathlib import Path

from pgimcode.discovery.symbol_parser import EXT_TO_LANG, FileSymbols, SymbolParser

_parser = SymbolParser()
_symbol_cache: dict[str, tuple[tuple[int, int], FileSymbols]] = {}

# Files larger than this (in lines) are not dumped whole; the agent gets the
# outline and must request a line range or a specific symbol.
MAX_FULL_READ_LINES = 800


def is_code_file(path: Path) -> bool:
    """True if tree-sitter has a grammar for this file."""
    return path.suffix.lower() in EXT_TO_LANG or path.name in EXT_TO_LANG


def resolve_path(root: Path, path: str) -> Path | None:
    """Resolve a virtual ('/pkg/mod.py') or relative path against the repo root.

    Returns None if the path escapes the workspace root.
    """
    p = path.replace("\\", "/").lstrip("/")
    resolved = (root / p).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def get_symbols(path: Path) -> FileSymbols:
    """Parse a file with tree-sitter, using an mtime/size cache."""
    key = str(path)
    try:
        stat = path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return FileSymbols(path=path, language="unknown")
    cached = _symbol_cache.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    symbols = _parser.parse_file(path)
    _symbol_cache[key] = (stamp, symbols)
    return symbols


def build_outline(path: Path) -> str:
    """Build a tree-sitter structural outline of a code file."""
    symbols = get_symbols(path)
    if symbols.language == "unknown":
        return "(no tree-sitter grammar for this file)"
    lines: list[str] = [f"[tree-sitter:{symbols.language}]"]
    for sym in symbols.imports:
        lines.append(f"  import  {sym.name}  (line {sym.start_line})")
    for sym in symbols.classes:
        lines.append(f"  class   {sym.name}  (lines {sym.start_line}-{sym.end_line})")
    for sym in symbols.methods:
        lines.append(f"  method  {sym.signature or sym.name}  (lines {sym.start_line}-{sym.end_line})")
    for sym in symbols.functions:
        lines.append(f"  def     {sym.signature or sym.name}  (lines {sym.start_line}-{sym.end_line})")
    for sym in symbols.variables:
        lines.append(f"  var     {sym.name}  (line {sym.start_line})")
    if len(lines) == 1:
        lines.append("  (no top-level symbols found)")
    return "\n".join(lines)


def _numbered(lines: list[str], start: int) -> str:
    return "\n".join(f"{i:>5} | {line}" for i, line in enumerate(lines, start=start))


def create_code_tools(root: Path) -> list:
    """Create tree-sitter code tools bound to a workspace root, for deepagents."""
    root = Path(root).resolve()

    def code_outline(path: str) -> str:
        """Get the tree-sitter structural outline of a source code file: imports, classes, methods and functions with their line ranges. ALWAYS call this first before reading a code file — it is the cheapest way to understand a file and decide which lines or symbols to read."""
        target = resolve_path(root, path)
        if target is None or not target.is_file():
            return f"Error: file not found: {path}"
        if not is_code_file(target):
            return f"Not a code file (no tree-sitter grammar): {path}. Use read_file instead."
        total = target.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        return f"File: {path} ({total} lines)\n{build_outline(target)}"

    def read_code(path: str, start_line: int = 0, end_line: int = 0) -> str:
        """Read a source code file THROUGH tree-sitter. Returns a structural outline (parsed with tree-sitter) followed by the source with line numbers. Use start_line/end_line (1-based, inclusive) to read a specific range. This is the REQUIRED tool for reading any code file — never use read_file for code."""
        target = resolve_path(root, path)
        if target is None or not target.is_file():
            return f"Error: file not found: {path}"
        if not is_code_file(target):
            return f"Not a code file (no tree-sitter grammar): {path}. Use read_file instead."
        try:
            all_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            return f"Error reading {path}: {exc}"
        total = len(all_lines)
        outline = build_outline(target)
        header = f"File: {path} ({total} lines)\n## Outline (tree-sitter)\n{outline}\n"
        if start_line or end_line:
            start = max(1, start_line or 1)
            end = min(total, end_line or total)
            body = _numbered(all_lines[start - 1 : end], start)
            return f"{header}## Source (lines {start}-{end} of {total})\n{body}"
        if total > MAX_FULL_READ_LINES:
            body = _numbered(all_lines[:MAX_FULL_READ_LINES], 1)
            return (
                f"{header}## Source (lines 1-{MAX_FULL_READ_LINES} of {total} — file too large for a full read)\n"
                f"{body}\n... [truncated — use read_code with start_line/end_line, "
                f"or read_symbol to fetch a specific function/class]"
            )
        return f"{header}## Source (lines 1-{total})\n{_numbered(all_lines, 1)}"

    def read_symbol(path: str, symbol_name: str) -> str:
        """Read the exact source of a single function, class or method from a code file, located via the tree-sitter parse tree. Much cheaper than reading the whole file — prefer this when you only need one symbol."""
        target = resolve_path(root, path)
        if target is None or not target.is_file():
            return f"Error: file not found: {path}"
        if not is_code_file(target):
            return f"Not a code file (no tree-sitter grammar): {path}."
        symbols = get_symbols(target)
        matches = [
            sym
            for group in (symbols.classes, symbols.functions, symbols.methods)
            for sym in group
            if sym.name == symbol_name
        ]
        if not matches:
            return (
                f"Symbol '{symbol_name}' not found in {path}.\n"
                f"Available symbols:\n{build_outline(target)}"
            )
        all_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        parts = []
        for sym in matches:
            body = _numbered(all_lines[sym.start_line - 1 : sym.end_line], sym.start_line)
            parts.append(f"{sym.kind} {sym.name} (lines {sym.start_line}-{sym.end_line}) in {path}:\n{body}")
        return "\n\n".join(parts)

    return [code_outline, read_code, read_symbol]
