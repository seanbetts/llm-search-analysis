"""Tests for frontend docstring coverage.

This module verifies that frontend Python code (Streamlit UI, API client,
helpers, network capture) follows the docstring standards defined in
CONTRIBUTING.md.

The tests are similar to backend tests but with relaxed requirements
since frontend code tends to be more UI-focused.
"""

import ast

# Import the backend test utilities (they're generic)
import sys
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "tests"))
from test_docstrings import (
    calculate_coverage,
    get_python_files,
    has_docstring,
    is_public_function,
    parse_file,
)


@pytest.fixture(scope="module")
def frontend_root() -> Path:
    """Get frontend directory path.

    Returns:
        Path to frontend directory
    """
    return Path(__file__).parent.parent


@pytest.fixture(scope="module")
def python_files(frontend_root: Path) -> List[Path]:
    """Get all frontend Python files to check.

    Args:
        frontend_root: Path to frontend directory

    Returns:
        List of Python file paths
    """
    return get_python_files(frontend_root)


def test_module_docstrings(python_files: List[Path]):
    """Test that all frontend modules have docstrings.

    Frontend modules should have docstrings explaining their purpose,
    especially API clients, helpers, and network capture logic.
    """
    errors = []
    for file_path in python_files:
        try:
            tree, _ = parse_file(file_path)
        except SyntaxError as e:
            errors.append(f"Syntax error in {file_path}: {e}")
            continue

        if not has_docstring(tree):
            errors.append(f"Missing module docstring in {file_path}")

    if errors:
        errors.sort()
        error_msg = "\n".join(errors)
        pytest.fail(
            f"\n{len(errors)} frontend module(s) missing docstrings:\n{error_msg}\n\n"
            f"Run 'make docstring-check' for more details."
        )


@pytest.mark.xfail(reason="Not all frontend classes have docstrings yet - gradual improvement")
def test_class_docstrings(python_files: List[Path]):
    """Test that frontend classes have docstrings.

    Currently set to XFAIL to allow gradual improvement.
    """
    errors = []
    for file_path in python_files:
        try:
            tree, _ = parse_file(file_path)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not has_docstring(node):
                    errors.append(
                        f"Missing class docstring for '{node.name}' in {file_path}:{node.lineno}"
                    )

    if errors:
        errors.sort()
        error_msg = "\n".join(errors[:10])
        if len(errors) > 10:
            error_msg += f"\n... and {len(errors) - 10} more"

        pytest.fail(
            f"\n{len(errors)} frontend class(es) missing docstrings:\n{error_msg}"
        )


@pytest.mark.xfail(reason="Not all frontend functions have docstrings yet - gradual improvement")
def test_function_docstrings(python_files: List[Path]):
    """Test that public frontend functions have docstrings.

    Currently set to XFAIL to allow gradual improvement.
    """
    errors = []
    for file_path in python_files:
        try:
            tree, _ = parse_file(file_path)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if is_public_function(node.name) and not has_docstring(node):
                    errors.append(
                        f"Missing function docstring for '{node.name}' in {file_path}:{node.lineno}"
                    )

    if errors:
        errors.sort()
        error_msg = "\n".join(errors[:10])
        if len(errors) > 10:
            error_msg += f"\n... and {len(errors) - 10} more"

        pytest.fail(
            f"\n{len(errors)} frontend function(s) missing docstrings:\n{error_msg}"
        )


def test_frontend_coverage_report(frontend_root: Path, capsys):
    """Generate and display frontend docstring coverage statistics.

    Args:
        frontend_root: Path to frontend directory
        capsys: Pytest fixture to capture stdout
    """
    coverage = calculate_coverage(frontend_root)

    print("\n" + "=" * 70)
    print("FRONTEND DOCSTRING COVERAGE REPORT")
    print("=" * 70)
    print(f"\nModules:   {coverage['modules']['with_docstrings']:3d} / "
          f"{coverage['modules']['total']:3d} ({coverage['modules']['coverage']:5.1f}%)")
    print(f"Classes:   {coverage['classes']['with_docstrings']:3d} / "
          f"{coverage['classes']['total']:3d} ({coverage['classes']['coverage']:5.1f}%)")
    print(f"Functions: {coverage['functions']['with_docstrings']:3d} / "
          f"{coverage['functions']['total']:3d} ({coverage['functions']['coverage']:5.1f}%)")
    print("\n" + "=" * 70)
    print("Target: 90% coverage (frontend has more UI-focused code)")
    print("=" * 70 + "\n")

    # This test always passes - it's just for reporting
    assert True
