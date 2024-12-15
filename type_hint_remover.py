import ast
import os
import tokenize
from difflib import unified_diff
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple, Union

import click
import libcst as cst

from utils import is_test_file


class TypeHintTransformer(cst.CSTTransformer):

    def leave_FunctionDef(self, original_node, updated_node):
        # Remove return type annotations
        if original_node.returns:
            # Create a new function definition without return type
            return updated_node.with_changes(returns=None)
        return updated_node

    def leave_Param(self, original_node, updated_node):
        # Remove parameter type annotations
        if original_node.annotation:
            # Create a new parameter without type annotation
            return updated_node.with_changes(annotation=None)
        return updated_node

    def leave_AnnAssign(self, original_node, updated_node):
        # Convert AnnAssign to regular Assign by keeping only the target and value
        return cst.Assign(
            targets=[cst.AssignTarget(target=updated_node.target)],
            value=updated_node.value or cst.Name("None"),
        )


class TypeHintRemover(ast.NodeTransformer):
    """Removes type hints from Python source code while preserving functionality."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def process_file(self, file_path: Path) -> Tuple[str, str]:
        """Process a single Python file to remove type hints while preserving comments."""
        # Read original source
        with open(file_path, "r", encoding="utf-8") as f:
            original_source = f.read()

        return original_source, self.process_file_contents(original_source)

    def process_file_contents(self, original_source: str) -> Tuple[str, str]:
        module = cst.parse_module(original_source)

        # Apply the transformer
        transformer = TypeHintTransformer()
        modified_module = module.visit(transformer)

        # Convert back to source code
        return modified_module.code

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
