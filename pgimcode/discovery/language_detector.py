"""Detect programming languages and frameworks from file paths."""

from pathlib import Path
from collections import Counter

from pgimcode.discovery.repo_scanner import ScannedFile


# Extension → language
EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
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
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".scala": "scala",
    ".r": "r",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".fish": "fish",
    ".ps1": "powershell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "scss",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".dockerfile": "dockerfile",
    "Dockerfile": "dockerfile",
    ".makefile": "makefile",
    "Makefile": "makefile",
    ".cmake": "cmake",
}


def detect_language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in EXT_MAP:
        return EXT_MAP[suffix]
    name = path.name
    if name in EXT_MAP:
        return EXT_MAP[name]
    return None


def annotate_languages(files: list[ScannedFile]) -> list[ScannedFile]:
    """Return new list with language fields populated."""
    return [
        ScannedFile(
            path=f.path,
            abs_path=f.abs_path,
            size=f.size,
            is_binary=f.is_binary,
            language=detect_language(f.path),
        )
        for f in files
    ]


def detect_frameworks(files: list[ScannedFile]) -> list[str]:
    """Return list of detected frameworks from file presence."""
    names = {f.path.name for f in files}
    frameworks = []
    if "pyproject.toml" in names:
        frameworks.append("python")
        # peek inside for poetry
        for f in files:
            if f.path.name == "pyproject.toml":
                try:
                    text = f.abs_path.read_text(errors="ignore")
                    if "[tool.poetry]" in text:
                        frameworks.append("poetry")
                    if "pytest" in text or "[tool.pytest" in text:
                        frameworks.append("pytest")
                except Exception:
                    pass
                break
    if "requirements.txt" in names:
        frameworks.append("pip")
    if "package.json" in names:
        frameworks.append("npm")
        for f in files:
            if f.path.name == "package.json":
                try:
                    text = f.abs_path.read_text(errors="ignore")
                    if '"next"' in text or "nextjs" in text:
                        frameworks.append("nextjs")
                    if '"react"' in text:
                        frameworks.append("react")
                    if '"vite"' in text:
                        frameworks.append("vite")
                except Exception:
                    pass
                break
    if "Cargo.toml" in names:
        frameworks.append("rust/cargo")
    if "go.mod" in names:
        frameworks.append("go")
    if "pom.xml" in names or any("build.gradle" in n for n in names):
        frameworks.append("java/maven" if "pom.xml" in names else "java/gradle")
    if "Dockerfile" in names or any(f.path.name.startswith("Dockerfile") for f in files):
        frameworks.append("docker")
    if "vite.config" in str(names):
        frameworks.append("vite")
    return list(dict.fromkeys(frameworks))  # dedupe preserve order


def find_entry_points(files: list[ScannedFile]) -> list[str]:
    """Guess main entry points."""
    candidates = []
    for f in files:
        name = f.path.name
        if name in ("main.py", "app.py", "index.js", "index.ts", "main.rs", "main.go", "main.java", "__main__.py"):
            candidates.append(str(f.path))
        if name == "cli.py" and f.language == "python":
            candidates.append(str(f.path))
    return candidates


def find_test_locations(files: list[ScannedFile]) -> list[str]:
    dirs = set()
    for f in files:
        parts = f.path.parts
        for i, part in enumerate(parts):
            if part.lower() in ("tests", "test", "__tests__", "spec", "specs"):
                dirs.add("/".join(parts[: i + 1]))
    return sorted(dirs)


def find_dependency_files(files: list[ScannedFile]) -> list[str]:
    names = {"pyproject.toml", "requirements.txt", "poetry.lock", "package.json", "package-lock.json",
             "yarn.lock", "pnpm-lock.yaml", "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
             "pom.xml", "build.gradle", "Gemfile", "composer.json", "Pipfile", "setup.py"}
    return sorted({str(f.path) for f in files if f.path.name in names})


def infer_build_commands(files: list[ScannedFile]) -> list[str]:
    names = {f.path.name for f in files}
    cmds = []
    if "pyproject.toml" in names or "requirements.txt" in names or "setup.py" in names:
        cmds.append("pytest")
    if "package.json" in names:
        cmds.append("npm test")
    if "Cargo.toml" in names:
        cmds.append("cargo test")
    if "go.mod" in names:
        cmds.append("go test")
    if "Makefile" in names:
        cmds.append("make test")
    return cmds