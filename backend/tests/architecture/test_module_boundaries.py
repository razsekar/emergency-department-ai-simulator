"""Architecture tests for the modular monolith.

Rules (see ARCHITECTURE.md, "Allowed dependency direction"):
  1. A module may import another module only via `app.modules.<other>.public`.
  2. The module dependency graph has no cycles.
  3. API controllers contain no persistence code (no sqlalchemy, no infrastructure imports).
  4. Raw SQL / ORM writes to another module's schema are forbidden.
  5. `app.platform` (shared kernel) never imports a module.
"""
import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
MODULES_DIR = APP / "modules"
MODULES = sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir() and not p.name.startswith("_"))
LAYERS = ("api", "application", "domain", "infrastructure")


def _py_files(root: Path):
    return [p for p in root.rglob("*.py")]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
            # `from app.modules.x import public` style
            names += [f"{node.module}.{a.name}" for a in node.names]
    return names


def _target_module(name: str) -> str | None:
    m = re.match(r"app\.modules\.([a-z_]+)", name)
    return m.group(1) if m else None


def test_expected_modules_exist_with_standard_layout():
    expected = {
        "identity", "simulation", "patient_queue", "resource_management", "analytics",
        "knowledge_base", "rag", "ai_orchestration", "agent_tools", "model_providers", "audit",
    }
    assert set(MODULES) == expected
    for m in MODULES:
        assert (MODULES_DIR / m / "public.py").is_file(), f"{m} lacks public.py"
        for layer in LAYERS:
            assert (MODULES_DIR / m / layer).is_dir(), f"{m} lacks {layer}/"


def test_cross_module_imports_use_public_interface_only():
    violations = []
    for m in MODULES:
        for f in _py_files(MODULES_DIR / m):
            for imp in _imports(f):
                target = _target_module(imp)
                if target and target != m and not re.fullmatch(rf"app\.modules\.{target}(\.public(\.\w+)?)?", imp):
                    violations.append(f"{f.relative_to(APP)} imports {imp}")
    assert not violations, "\n".join(violations)


def _graph() -> dict[str, set[str]]:
    g: dict[str, set[str]] = {m: set() for m in MODULES}
    for m in MODULES:
        for f in _py_files(MODULES_DIR / m):
            for imp in _imports(f):
                t = _target_module(imp)
                if t and t != m:
                    g[m].add(t)
    return g


def test_no_circular_module_dependencies():
    graph = _graph()
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]):
        if state.get(node) == 1:
            raise AssertionError("Cycle: " + " -> ".join(path + [node]))
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in graph[node]:
            visit(nxt, path + [node])
        state[node] = 2

    for m in MODULES:
        visit(m, [])


def test_api_controllers_have_no_persistence_code():
    violations = []
    for m in MODULES:
        for f in _py_files(MODULES_DIR / m / "api"):
            for imp in _imports(f):
                if imp.startswith("sqlalchemy") or ".infrastructure" in imp or ".domain" in imp.replace("app.platform", ""):
                    violations.append(f"{f.relative_to(APP)} imports {imp}")
            if re.search(r"\.(execute|query|add|commit)\(", f.read_text()):
                violations.append(f"{f.relative_to(APP)} appears to run persistence calls")
    assert not violations, "\n".join(violations)


def test_no_cross_schema_sql_access():
    """A module's code may mention only its own schema in SQL / table definitions."""
    violations = []
    for m in MODULES:
        for f in _py_files(MODULES_DIR / m):
            text = f.read_text()
            for other in MODULES:
                if other != m and re.search(rf"(?i)\b(from|join|into|update|delete\s+from)\s+{other}\.\w+", text):
                    violations.append(f"{f.relative_to(APP)} touches schema '{other}'")
                if other != m and re.search(rf"schema\s*=\s*[\"']{other}[\"']", text):
                    violations.append(f"{f.relative_to(APP)} defines table in schema '{other}'")
    assert not violations, "\n".join(violations)


def test_platform_does_not_import_modules():
    violations = []
    for f in _py_files(APP / "platform"):
        for imp in _imports(f):
            if _target_module(imp):
                violations.append(f"{f.relative_to(APP)} imports {imp}")
    assert not violations, "\n".join(violations)
