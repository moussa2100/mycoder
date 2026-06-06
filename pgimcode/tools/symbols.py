"""Symbol lookup using tree-sitter."""

from pathlib import Path

from pgimcode.discovery.symbol_parser import SymbolParser, FileSymbols, Symbol


def find_symbol(name: str, path: Path) -> list[Symbol]:
    """Find all symbols matching `name` in a file."""
    parser = SymbolParser()
    result = parser.parse_file(path)
    matches = []
    for sym_list in (result.functions, result.classes, result.methods, result.imports, result.variables):
        for sym in sym_list:
            if sym.name == name or name in sym.name:
                matches.append(sym)
    return matches


def find_references(name: str, path: Path) -> list[Symbol]:
    """Find references to `name` in a file (grep-level, not full call graph)."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    refs = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        # Skip definition lines
        if stripped.startswith(f"def {name}") or stripped.startswith(f"class {name}"):
            continue
        if name in stripped:
            refs.append(Symbol(
                name=f"ref: {line.strip()[:80]}",
                kind="reference",
                start_line=i,
                end_line=i,
            ))
    return refs