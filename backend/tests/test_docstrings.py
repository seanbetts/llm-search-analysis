"""Tests for docstring coverage and quality.

This module uses AST parsing to verify that all modules, classes, and public
functions have docstrings. It enforces the docstring standardization policy
defined in CONTRIBUTING.md.

The tests check:
- Module-level docstrings (all .py files)
- Class docstrings (all classes)
- Public function/method docstrings (non-dunder, non-private)

Exemptions are maintained for:
- Auto-generated files (Alembic migrations)
- Test helper functions (test_*.py files get relaxed rules)
- Simple dunder methods (__repr__, __str__, etc.)
"""

import ast
import os
from pathlib import Path
from typing import List, Tuple, Set

import pytest


# Exemption lists
EXEMPT_MODULES = {
    # Alembic auto-generated migrations
    "backend/alembic/versions",
}

EXEMPT_FILES = {
    # Empty __init__.py files don't need docstrings (D104 ignored in config)
    "__init__.py",
}

EXEMPT_DUNDER_METHODS = {
    "__init__",
    "__repr__",
    "__str__",
    "__eq__",
    "__ne__",
    "__lt__",
    "__le__",
    "__gt__",
    "__ge__",
    "__hash__",
    "__bool__",
    "__len__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__iter__",
    "__next__",
    "__enter__",
    "__exit__",
}


def get_python_files(root_dir: Path) -> List[Path]:
    """Get all Python files in directory, excluding exempted paths.

    Args:
        root_dir: Root directory to search

    Returns:
        List of Python file paths
    """
    python_files = []
    for path in root_dir.rglob("*.py"):
        # Skip exempted directories
        if any(exempt in str(path) for exempt in EXEMPT_MODULES):
            continue

        # Skip exempted files
        if path.name in EXEMPT_FILES:
            continue

        python_files.append(path)

    return python_files


def parse_file(file_path: Path) -> Tuple[ast.Module, str]:
    """Parse Python file and return AST.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (AST Module, file content)

    Raises:
        SyntaxError: If file has syntax errors
    """
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    return tree, content


def has_docstring(node: ast.AST) -> bool:
    """Check if AST node has a docstring.

    Args:
        node: AST node (Module, ClassDef, or FunctionDef)

    Returns:
        True if node has a docstring, False otherwise
    """
    if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return False

    # Check if first statement is a docstring (Expr with Constant string value)
    if not node.body:
        return False

    first_stmt = node.body[0]
    if not isinstance(first_stmt, ast.Expr):
        return False

    # In Python 3.8+, strings are ast.Constant
    if isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
        return True

    # Fallback for older Python versions
    if isinstance(first_stmt.value, ast.Str):
        return True

    return False


def is_public_function(name: str) -> bool:
    """Check if function name indicates it's public.

    Args:
        name: Function name

    Returns:
        True if function is public (not private, not dunder)
    """
    # Private functions start with _
    if name.startswith("_") and not name.startswith("__"):
        return False

    # Dunder methods in exemption list
    if name in EXEMPT_DUNDER_METHODS:
        return False

    return True


def check_module_docstring(file_path: Path) -> List[str]:
    """Check if module has docstring.

    Args:
        file_path: Path to Python file

    Returns:
        List of error messages (empty if no errors)
    """
    try:
        tree, _ = parse_file(file_path)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]

    errors = []
    if not has_docstring(tree):
        errors.append(f"Missing module docstring in {file_path}")

    return errors


def check_class_docstrings(file_path: Path) -> List[str]:
    """Check if all classes have docstrings.

    Args:
        file_path: Path to Python file

    Returns:
        List of error messages (empty if no errors)
    """
    try:
        tree, _ = parse_file(file_path)
    except SyntaxError:
        return []  # Syntax errors caught by module check

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not has_docstring(node):
                errors.append(
                    f"Missing class docstring for '{node.name}' in {file_path}:{node.lineno}"
                )

    return errors


def check_function_docstrings(file_path: Path) -> List[str]:
    """Check if all public functions have docstrings.

    Args:
        file_path: Path to Python file

    Returns:
        List of error messages (empty if no errors)
    """
    try:
        tree, _ = parse_file(file_path)
    except SyntaxError:
        return []  # Syntax errors caught by module check

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_public_function(node.name) and not has_docstring(node):
                errors.append(
                    f"Missing function docstring for '{node.name}' in {file_path}:{node.lineno}"
                )

    return errors


def calculate_coverage(root_dir: Path) -> dict:
    """Calculate docstring coverage statistics.

    Args:
        root_dir: Root directory to analyze

    Returns:
        Dictionary with coverage statistics
    """
    files = get_python_files(root_dir)

    total_modules = len(files)
    total_classes = 0
    total_functions = 0
    modules_with_docstrings = 0
    classes_with_docstrings = 0
    functions_with_docstrings = 0

    for file_path in files:
        try:
            tree, _ = parse_file(file_path)
        except SyntaxError:
            continue

        # Count module docstring
        if has_docstring(tree):
            modules_with_docstrings += 1

        # Count classes and functions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                total_classes += 1
                if has_docstring(node):
                    classes_with_docstrings += 1

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if is_public_function(node.name):
                    total_functions += 1
                    if has_docstring(node):
                        functions_with_docstrings += 1

    return {
        "modules": {
            "total": total_modules,
            "with_docstrings": modules_with_docstrings,
            "coverage": (
                (modules_with_docstrings / total_modules * 100) if total_modules > 0 else 0
            ),
        },
        "classes": {
            "total": total_classes,
            "with_docstrings": classes_with_docstrings,
            "coverage": (
                (classes_with_docstrings / total_classes * 100) if total_classes > 0 else 0
            ),
        },
        "functions": {
            "total": total_functions,
            "with_docstrings": functions_with_docstrings,
            "coverage": (
                (functions_with_docstrings / total_functions * 100) if total_functions > 0 else 0
            ),
        },
    }


# Pytest fixtures and tests
@pytest.fixture(scope="module")
def backend_root() -> Path:
    """Get backend/app directory path.

    Returns:
        Path to backend/app directory
    """
    # tests/test_docstrings.py -> tests/ -> backend/ -> backend/app/
    return Path(__file__).parent.parent / "app"


@pytest.fixture(scope="module")
def python_files(backend_root: Path) -> List[Path]:
    """Get all Python files to check.

    Args:
        backend_root: Path to backend/app directory

    Returns:
        List of Python file paths
    """
    return get_python_files(backend_root)


def test_module_docstrings(python_files: List[Path]):
    """Test that all modules have docstrings.

    This test checks for D100 violations (missing module docstrings).
    Currently set to XFAIL to allow gradual improvement.
    """
    all_errors = []
    for file_path in python_files:
        errors = check_module_docstring(file_path)
        all_errors.extend(errors)

    if all_errors:
        # Sort errors for consistent output
        all_errors.sort()
        error_msg = "\n".join(all_errors)
        pytest.fail(
            f"\n{len(all_errors)} module(s) missing docstrings:\n{error_msg}\n\n"
            f"Run 'make docstring-check' for more details."
        )


def test_class_docstrings(python_files: List[Path]):
    """Test that all classes have docstrings.

    This test checks for D101 violations (missing class docstrings).
    Phase 2 complete - all classes now have docstrings.
    """
    all_errors = []
    for file_path in python_files:
        errors = check_class_docstrings(file_path)
        all_errors.extend(errors)

    if all_errors:
        all_errors.sort()
        error_msg = "\n".join(all_errors[:20])  # Show first 20
        if len(all_errors) > 20:
            error_msg += f"\n... and {len(all_errors) - 20} more"

        pytest.fail(
            f"\n{len(all_errors)} class(es) missing docstrings:\n{error_msg}\n\n"
            f"Run 'make docstring-check' for more details."
        )


def test_function_docstrings(python_files: List[Path]):
    """Test that all public functions have docstrings.

    This test checks for D102/D103 violations (missing function docstrings).
    Phase 2 complete - all public functions now have docstrings.
    """
    all_errors = []
    for file_path in python_files:
        errors = check_function_docstrings(file_path)
        all_errors.extend(errors)

    if all_errors:
        all_errors.sort()
        error_msg = "\n".join(all_errors[:20])  # Show first 20
        if len(all_errors) > 20:
            error_msg += f"\n... and {len(all_errors) - 20} more"

        pytest.fail(
            f"\n{len(all_errors)} function(s) missing docstrings:\n{error_msg}\n\n"
            f"Run 'make docstring-check' for more details."
        )


def test_docstring_coverage_report(backend_root: Path, capsys):
    """Generate and display docstring coverage statistics.

    Args:
        backend_root: Path to backend/app directory
        capsys: Pytest fixture to capture stdout
    """
    coverage = calculate_coverage(backend_root)

    print("\n" + "=" * 70)
    print("DOCSTRING COVERAGE REPORT")
    print("=" * 70)
    print(f"\nModules:   {coverage['modules']['with_docstrings']:3d} / "
          f"{coverage['modules']['total']:3d} ({coverage['modules']['coverage']:5.1f}%)")
    print(f"Classes:   {coverage['classes']['with_docstrings']:3d} / "
          f"{coverage['classes']['total']:3d} ({coverage['classes']['coverage']:5.1f}%)")
    print(f"Functions: {coverage['functions']['with_docstrings']:3d} / "
          f"{coverage['functions']['total']:3d} ({coverage['functions']['coverage']:5.1f}%)")
    print("\n" + "=" * 70)
    print("Target: 95% coverage for modules, classes, and public functions")
    print("=" * 70 + "\n")

    # This test always passes - it's just for reporting
    assert True
