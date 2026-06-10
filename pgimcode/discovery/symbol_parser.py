"""Parse source files with tree-sitter to extract symbols."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter_language_pack import get_parser


@dataclass
class Symbol:
    name: str
    kind: str          # function | class | method | import | variable
    start_line: int
    end_line: int
    signature: str = ""  # e.g. "def foo(a: int) -> str"


@dataclass
class FileSymbols:
    path: Path
    language: str
    functions: list[Symbol] = field(default_factory=list)
    classes: list[Symbol] = field(default_factory=list)
    methods: list[Symbol] = field(default_factory=list)
    imports: list[Symbol] = field(default_factory=list)
    variables: list[Symbol] = field(default_factory=list)


# Extension → tree-sitter language name
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".dockerfile": "dockerfile",
    "Dockerfile": "dockerfile",
}


def _guess_language(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in EXT_TO_LANG:
        return EXT_TO_LANG[ext]
    name = path.name
    if name in EXT_TO_LANG:
        return EXT_TO_LANG[name]
    return None


def _get_node_text(node, source: str) -> str:
    return source[node.start_byte() : node.end_byte()]


def _iter_nodes(root):
    """Iterate over all nodes in tree recursively."""
    def walk(node):
        yield node
        for i in range(node.child_count()):
            child = node.child(i)
            if child is not None:
                yield from walk(child)
    yield from walk(root)


def _extract_functions_python(root, source: str) -> list[Symbol]:
    """Walk tree for Python function definitions."""
    symbols = []
    for node in _iter_nodes(root):
        if node.kind() == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _get_node_text(name_node, source)
                params = node.child_by_field_name("parameters")
                sig_parts = [name, _get_node_text(params, source) if params else "()"]
                # return type
                ret = node.child_by_field_name("return_type")
                if ret:
                    sig_parts.append(" -> " + _get_node_text(ret, source))
                signature = "".join(sig_parts)
                symbols.append(Symbol(
                    name=name,
                    kind="function",
                    start_line=name_node.start_position().row + 1,
                    end_line=node.end_position().row + 1,
                    signature=signature,
                ))
    return symbols


def _extract_classes_python(root, source: str) -> list[Symbol]:
    symbols = []
    for node in _iter_nodes(root):
        if node.kind() == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _get_node_text(name_node, source)
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    start_line=name_node.start_position().row + 1,
                    end_line=node.end_position().row + 1,
                ))
    return symbols


def _extract_imports_python(root, source: str) -> list[Symbol]:
    symbols = []
    for node in _iter_nodes(root):
        kind = node.kind()
        if kind in ("import_statement", "import_from_statement"):
            text = _get_node_text(node, source)
            symbols.append(Symbol(
                name=text.strip(),
                kind="import",
                start_line=node.start_position().row + 1,
                end_line=node.end_position().row + 1,
            ))
    return symbols


class SymbolParser:
    """Parse source files to extract symbols using tree-sitter.

    Parser/Tree objects from the Rust-backed language pack are unsendable
    (must be created, used and dropped on the same thread), so a fresh parser
    is created per parse_file call and never cached across calls. Only plain
    Python dataclasses (FileSymbols/Symbol) escape this method, which makes
    it safe to call from any thread (e.g. LangGraph tool executor threads).
    """

    def parse_file(self, path: Path, language_hint: str | None = None) -> FileSymbols:
        language = language_hint or _guess_language(path)
        if language is None:
            return FileSymbols(path=path, language="unknown")

        try:
            parser = get_parser(language)
        except Exception:
            return FileSymbols(path=path, language=language)

        try:
            source = path.read_text()
        except Exception:
            return FileSymbols(path=path, language=language)

        tree = parser.parse(source)
        root = tree.root_node()

        result = FileSymbols(path=path, language=language)

        if language == "python":
            result.functions = _extract_functions_python(root, source)
            result.classes = _extract_classes_python(root, source)
            result.imports = _extract_imports_python(root, source)
        else:
            # For other languages, do a generic function/class extraction
            result.functions = self._generic_extract(root, source, "function")
            result.classes = self._generic_extract(root, source, "class")

        return result

    def _generic_extract(self, root, source: str, kind: str) -> list[Symbol]:
        """Generic extractor: look for nodes with type containing kind name."""
        symbols = []
        for node in _iter_nodes(root):
            node_kind = node.kind()
            if kind in node_kind and node_kind.endswith("_definition"):
                # Try to find name child
                for i in range(node.child_count()):
                    child = node.child(i)
                    if child.kind() == "identifier":
                        name = _get_node_text(child, source)
                        symbols.append(Symbol(
                            name=name,
                            kind=kind,
                            start_line=child.start_position().row + 1,
                            end_line=node.end_position().row + 1,
                        ))
                        break
        return symbols