"""Structural tests for workflow prompts (Phase 10 split — directory layout).

After Phase 10, workflows.py was split into per-prompt modules under
app/controllers/prompts/workflows/. These tests verify each module has
the expected @prompt-decorated function with correct parameters and
docstrings, without importing fastmcp at runtime.
"""

import ast
from pathlib import Path

import pytest

WORKFLOWS_DIR = Path("app/controllers/prompts/workflows")

EXPECTED = {
    "build_set.py": {
        "function": "build_set_workflow",
        "params": {"playlist_name", "template", "duration_min"},
    },
    "expand_playlist.py": {
        "function": "expand_playlist_workflow",
        "params": {"playlist_name", "target_count"},
    },
    "improve_set.py": {
        "function": "improve_set_workflow",
        "params": {"set_name"},
    },
    "deliver_set.py": {
        "function": "deliver_set_workflow",
        "params": {"set_name", "sync_ym"},
    },
    "full_pipeline.py": {
        "function": "full_expansion_pipeline",
        "params": {"source_playlist", "target_per_subgenre"},
    },
    "llm_discovery.py": {
        "function": "llm_discovery_workflow",
        "params": set(),  # any
    },
}


def _parse(filename: str) -> ast.Module:
    path = WORKFLOWS_DIR / filename
    assert path.exists(), f"missing module: {path}"
    return ast.parse(path.read_text())


def _find_func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    pytest.fail(f"function {name} not found")


@pytest.mark.parametrize("filename, spec", EXPECTED.items())
def test_workflow_module_exists(filename: str, spec: dict) -> None:
    tree = _parse(filename)
    fn = _find_func(tree, spec["function"])
    assert ast.get_docstring(fn) is not None, f"{spec['function']} missing docstring"
    if spec["params"]:
        param_names = {arg.arg for arg in fn.args.args}
        missing = spec["params"] - param_names
        assert not missing, f"{spec['function']} missing params: {missing}"
    decorator_names = []
    for dec in fn.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
            decorator_names.append(dec.func.id)
        elif isinstance(dec, ast.Name):
            decorator_names.append(dec.id)
    assert "prompt" in decorator_names, f"{spec['function']} missing @prompt decorator"


def test_init_reexports_all_workflows() -> None:
    init = WORKFLOWS_DIR / "__init__.py"
    code = init.read_text()
    tree = ast.parse(code)
    reexported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "workflows." in node.module:
            for alias in node.names:
                reexported.add(alias.name)
    expected_funcs = {spec["function"] for spec in EXPECTED.values()}
    missing = expected_funcs - reexported
    assert not missing, f"__init__ missing re-exports: {missing}"


def test_imports_message_and_prompt_from_fastmcp() -> None:
    for filename in EXPECTED:
        tree = _parse(filename)
        has_message = has_prompt = False
        uses_shared_wrappers = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "fastmcp.prompts":
                names = {alias.name for alias in node.names}
                if "Message" in names:
                    has_message = True
                if "prompt" in names:
                    has_prompt = True
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "app.controllers.prompts.workflow_shared"
            ):
                names = {alias.name for alias in node.names}
                if "message_user" in names and "message_assistant" in names:
                    uses_shared_wrappers = True
        assert has_message or uses_shared_wrappers, (
            f"{filename} must import Message from fastmcp.prompts or "
            "message_user/message_assistant from workflow_shared"
        )
        assert has_prompt, f"{filename} missing 'from fastmcp.prompts import prompt'"
