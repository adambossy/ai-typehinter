import ast
import os
from difflib import unified_diff
from pathlib import Path

import click
import libcst as cst
from libcst.metadata import ParentNodeProvider

from utils import is_test_file


class TypeHintCollector(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    def __init__(self):
        super().__init__()
        self.annotations = {
            "functions": {},  # fully_qualified_name -> return_type
            "parameters": {},  # fully_qualified_name -> {param_name -> type}
            "variables": {},  # fully_qualified_name -> type
        }
        self.current_namespace = []
        self.module_name = None

    def visit_Module(self, node: cst.Module) -> None:
        # Get module name from first statement if it's a docstring
        if (
            node.body
            and isinstance(node.body[0], cst.SimpleStatementLine)
            and isinstance(node.body[0].body[0], cst.Expr)
            and isinstance(node.body[0].body[0].value, cst.SimpleString)
        ):
            self.module_name = node.body[0].body[0].value.value.strip("\"' ")
        else:
            self.module_name = "<module>"
        self.current_namespace = [self.module_name]

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.current_namespace.append(node.name.value)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        self.current_namespace.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.current_namespace.append(node.name.value)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        # Record return type annotation if present
        if original_node.returns:
            qualified_name = ".".join(self.current_namespace)
            self.annotations["functions"][qualified_name] = original_node.returns

        self.current_namespace.pop()

        # Remove return type annotations
        if original_node.returns:
            return updated_node.with_changes(returns=None)
        return updated_node

    def leave_Param(
        self, original_node: cst.Param, updated_node: cst.Param
    ) -> cst.Param:
        # Record parameter type annotation if present
        if original_node.annotation:
            qualified_name = ".".join(
                self.current_namespace + [original_node.name.value]
            )
            if qualified_name not in self.annotations["parameters"]:
                self.annotations["parameters"][qualified_name] = {}
            self.annotations["parameters"][qualified_name] = original_node.annotation

        # Remove parameter type annotations
        if original_node.annotation:
            return updated_node.with_changes(annotation=None)
        return updated_node

    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.Assign:
        # Handle both class-level and instance-level annotations
        if isinstance(original_node.target, cst.Name):
            # Class-level annotation: x: int
            target_value = original_node.target.value
        elif isinstance(original_node.target, cst.Attribute):
            # Instance-level annotation: self.x: int
            if (
                isinstance(original_node.target.value, cst.Name)
                and original_node.target.value.value == "self"
            ):
                target_value = original_node.target.attr.value

        # Record variable type annotation with namespace
        qualified_name = ".".join(self.current_namespace + [target_value])
        self.annotations["variables"][qualified_name] = original_node.annotation

        # Convert AnnAssign to regular Assign
        return cst.Assign(
            targets=[cst.AssignTarget(target=updated_node.target)],
            value=updated_node.value or cst.Name("None"),
        )

    def _get_parent_function(self, node):
        # Use metadata to get the parent function node
        parent = self.get_metadata(ParentNodeProvider, node)
        while parent:
            if isinstance(parent, cst.FunctionDef):
                return parent.name.value
            parent = self.get_metadata(ParentNodeProvider, parent)
        return None


class TypeHintRemover(ast.NodeTransformer):
    """Removes type hints from Python source code while preserving functionality."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def process_file(self, file_path: Path) -> tuple[str, str]:
        """Process a single Python file to remove type hints while preserving comments."""
        # Read original source
        with open(file_path, "r", encoding="utf-8") as f:
            original_source = f.read()

        return original_source, self.process_file_contents(original_source)

    def process_file_contents(self, original_source: str) -> str:
        module = cst.parse_module(original_source)
        wrapper = cst.MetadataWrapper(module)

        # Apply the transformer
        collector = TypeHintCollector()
        modified_module = wrapper.visit(collector)

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
