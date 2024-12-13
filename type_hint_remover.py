import ast
import os
from difflib import unified_diff
from pathlib import Path
from typing import Tuple

import click

from utils import is_test_file


class TypeHintRemover(ast.NodeTransformer):
    """Removes type hints from Python source code while preserving functionality."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Remove return and argument type annotations from function definitions."""
        # Remove return annotation
        node.returns = None

        # Remove argument annotations
        for arg in node.args.args:
            arg.annotation = None

        # Remove kwonly argument annotations
        for arg in node.args.kwonlyargs:
            arg.annotation = None

        # Remove posonlyargs annotations (Python 3.8+)
        if hasattr(node.args, "posonlyargs"):
            for arg in node.args.posonlyargs:
                arg.annotation = None

        return self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign:
        """Convert annotated assignments to regular assignments."""
        if node.value is None:
            # If it's just a variable annotation without assignment, remove it
            return None

        # Convert to regular assignment
        return ast.Assign(
            targets=[node.target],
            value=node.value,
            lineno=node.lineno,
            col_offset=node.col_offset,
        )

    def process_file(self, file_path: Path) -> Tuple[str, str]:
        """Process a single Python file to remove type hints.

        Returns:
            Tuple[str, str]: The original source code and the processed source code
        """
        with open(file_path, "r", encoding="utf-8") as f:
            original_source = f.read()

        # Parse the AST
        tree = ast.parse(original_source)

        # Remove type hints
        modified_tree = self.visit(tree)

        # Generate new source code
        processed_source = ast.unparse(modified_tree)

        return original_source, processed_source

    def process_project(self) -> None:
        """Process all Python files in the project."""
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file

                    # Skip test files
                    if is_test_file(str(file_path)):
                        continue

                    try:
                        original, processed = self.process_file(file_path)

                        # Only show diff if there were changes
                        if original != processed:
                            print(
                                f"\nProcessing: {file_path.relative_to(self.project_path)}"
                            )
                            print("=" * 80)

                            # Show unified diff
                            diff = unified_diff(
                                original.splitlines(keepends=True),
                                processed.splitlines(keepends=True),
                                fromfile=str(file_path),
                                tofile=str(file_path),
                                lineterm="",
                            )
                            print("".join(diff))
                            print("=" * 80)

                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")


@click.command()
@click.option(
    "--project-path",
    "-p",
    required=True,
    help="Path to the Python project to remove type hints from",
)
def cli(project_path: str):
    """Remove type hints from Python projects."""
    remover = TypeHintRemover(project_path)
    remover.process_project()


if __name__ == "__main__":
    cli()
