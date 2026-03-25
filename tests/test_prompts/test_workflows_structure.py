"""Structural tests for workflow prompts (without fastmcp runtime).

These tests verify the prompt structure and parameters without needing
to import and run FastMCP, which has dependency issues in this environment.
"""

import ast
from pathlib import Path

import pytest


def test_workflows_file_exists():
    """The workflows.py file should exist."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    assert workflows_file.exists()


def test_workflows_syntax():
    """The workflows.py file should be valid Python."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    try:
        ast.parse(code)
    except SyntaxError as e:
        pytest.fail(f"Syntax error in workflows.py: {e}")


def test_prompt_functions_defined():
    """All 5 workflow prompt functions should be defined."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    expected_prompts = {
        "build_set_workflow",
        "expand_playlist_workflow",
        "improve_set_workflow",
        "deliver_set_workflow",
        "full_expansion_pipeline",
    }

    assert expected_prompts.issubset(function_names), (
        f"Missing prompts: {expected_prompts - function_names}"
    )


def test_prompt_functions_have_docstrings():
    """All prompt functions should have docstrings."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    expected_prompts = {
        "build_set_workflow",
        "expand_playlist_workflow",
        "improve_set_workflow",
        "deliver_set_workflow",
        "full_expansion_pipeline",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in expected_prompts:
            assert ast.get_docstring(node) is not None, f"Function {node.name} missing docstring"


def test_prompt_functions_have_mcp_decorator():
    """All prompt functions should have @mcp.prompt decorator."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    expected_prompts = {
        "build_set_workflow",
        "expand_playlist_workflow",
        "improve_set_workflow",
        "deliver_set_workflow",
        "full_expansion_pipeline",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in expected_prompts:
            # Check for @mcp.prompt decorator
            decorator_names = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Attribute):
                    decorator_names.append(f"{dec.value.id}.{dec.attr}")
                elif isinstance(dec, ast.Name):
                    decorator_names.append(dec.id)

            assert "mcp.prompt" in decorator_names, (
                f"Function {node.name} missing @mcp.prompt decorator"
            )


def test_prompt_return_annotations():
    """All prompt functions should return list[Message]."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    expected_prompts = {
        "build_set_workflow",
        "expand_playlist_workflow",
        "improve_set_workflow",
        "deliver_set_workflow",
        "full_expansion_pipeline",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in expected_prompts:
            # Check return annotation
            assert node.returns is not None, f"Function {node.name} missing return type annotation"
            # The annotation should be list[Message]
            # We can't easily check this statically without importing,
            # but we can check it's present


def test_build_set_workflow_parameters():
    """build_set_workflow should have correct parameters."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_set_workflow":
            param_names = [arg.arg for arg in node.args.args]
            assert "playlist_name" in param_names
            assert "template" in param_names
            assert "duration_min" in param_names


def test_expand_playlist_workflow_parameters():
    """expand_playlist_workflow should have correct parameters."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "expand_playlist_workflow":
            param_names = [arg.arg for arg in node.args.args]
            assert "playlist_name" in param_names
            assert "target_count" in param_names


def test_improve_set_workflow_parameters():
    """improve_set_workflow should have correct parameters."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "improve_set_workflow":
            param_names = [arg.arg for arg in node.args.args]
            assert "set_name" in param_names


def test_deliver_set_workflow_parameters():
    """deliver_set_workflow should have correct parameters."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "deliver_set_workflow":
            param_names = [arg.arg for arg in node.args.args]
            assert "set_name" in param_names
            assert "sync_ym" in param_names


def test_full_expansion_pipeline_parameters():
    """full_expansion_pipeline should have correct parameters."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "full_expansion_pipeline":
            param_names = [arg.arg for arg in node.args.args]
            assert "source_playlist" in param_names
            assert "target_per_subgenre" in param_names


def test_imports_message_from_fastmcp():
    """Should import Message from fastmcp.prompts."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    has_message_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "fastmcp.prompts":
            names = [alias.name for alias in node.names]
            if "Message" in names:
                has_message_import = True
                break

    assert has_message_import, "Missing 'from fastmcp.prompts import Message'"


def test_imports_mcp_server():
    """Should import mcp from app.server."""
    workflows_file = Path("app/mcp/prompts/workflows.py")
    code = workflows_file.read_text()
    tree = ast.parse(code)

    has_mcp_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.server":
            names = [alias.name for alias in node.names]
            if "mcp" in names:
                has_mcp_import = True
                break

    assert has_mcp_import, "Missing 'from app.server import mcp'"
