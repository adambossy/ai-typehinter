import ast
import os
from typing import Dict, List, Set

import click


class FunctionNode:
    def __init__(self, name: str, filename: str, class_name: str = None):
        self.name: str = name
        self.filename: str = filename
        self.class_name: str = class_name
        self.callees: Set[FunctionNode] = set()  # Functions this function calls
        self.callers: Set[FunctionNode] = set()  # Functions that call this function

    def __repr__(self) -> str:
        class_prefix = f"{self.class_name}." if self.class_name else ""
        return f"FunctionNode({class_prefix}{self.name})"

    def add_callee(self, callee: "FunctionNode"):
        """Add a function that this function calls."""
        self.callees.add(callee)
        callee.callers.add(self)

    def __str__(self) -> str:
        return f"{self.name}"


class CallGraphAnalyzer(ast.NodeVisitor):
    def __init__(self):
        # Map of function names to their nodes
        self.nodes: Dict[str, FunctionNode] = {}
        # Map of files to ordered list of function nodes
        self.files_to_functions: Dict[str, List[FunctionNode]] = {}
        # Track current class during traversal
        self.current_class: str = None
        self.current_file: str = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track the current class being visited."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Skip test functions during graph construction
        if self.is_test_function(node.name):
            return

        # Create or get the node for this function
        current_node = self.nodes.get(
            f"{self.current_class}.{node.name}" if self.current_class else node.name
        )
        if not current_node:
            current_node = FunctionNode(
                name=node.name,
                filename=self.current_file,
                class_name=self.current_class,
            )
            self.nodes[
                f"{self.current_class}.{node.name}" if self.current_class else node.name
            ] = current_node

            # Track function order in file
            if self.current_file not in self.files_to_functions:
                self.files_to_functions[self.current_file] = []
            self.files_to_functions[self.current_file].append(current_node)

        # Analyze function body for function calls
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called_name = None
                if isinstance(child.func, ast.Name):
                    called_name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name):
                        if child.func.value.id == "self" and self.current_class:
                            # Handle method calls within the same class
                            called_name = f"{self.current_class}.{child.func.attr}"
                        else:
                            # Handle method calls on instances
                            # Look up the type of the instance if possible
                            instance_name = child.func.value.id
                            method_name = child.func.attr

                            # If we're calling a method on an instance of a class we just created
                            if instance_name in [
                                n.name
                                for n in self.nodes.values()
                                if isinstance(n.name, str)
                            ]:
                                # This is a method call on a class instance
                                called_name = f"{instance_name}.{method_name}"
                            else:
                                # Try to find the class name from the instance
                                for node_name in self.nodes:
                                    if node_name.endswith(f".{instance_name}"):
                                        class_name = node_name.split(".")[0]
                                        called_name = f"{class_name}.{method_name}"
                                        break
                                if not called_name:
                                    called_name = method_name

                if called_name:
                    # Use called_name directly
                    called_node = self.nodes.get(called_name)
                    if not called_node:
                        # Try to find the method with class prefix
                        for existing_name in self.nodes:
                            if existing_name.endswith(f".{called_name}"):
                                called_node = self.nodes[existing_name]
                                break

                        if not called_node:
                            called_node = FunctionNode(
                                name=called_name.split(".")[-1],
                                filename=self.current_file,
                                class_name=(
                                    called_name.split(".")[0]
                                    if "." in called_name
                                    else None
                                ),
                            )
                            self.nodes[called_name] = called_node

                    current_node.add_callee(called_node)

        self.generic_visit(node)

    def find_unreachable_functions(self) -> List[FunctionNode]:
        """Find functions that are defined but never called."""
        return [
            node
            for node in self.nodes.values()
            if node.filename
            != "unknown"  # Only consider functions we've found definitions for
            and not node.callers  # No calling functions
            and not self.is_test_function(node.name)  # Not a test function
        ]

    def is_test_function(self, func_name: str) -> bool:
        """
        Determine if a function is a test function based on pytest naming conventions.

        :param func_name: Name of the function to check
        :return: True if the function is a test function, False otherwise
        """
        return func_name.startswith("test_") or (  # Test functions
            func_name.startswith("Test") and func_name[0].isupper()
        )  # Test classes

    def analyze_file(self, file_path: str):
        """
        Analyze a single Python file and build its call graph.

        :param file_path: Path to the Python file to analyze
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.current_file = file_path
            tree = ast.parse(content)
            self.visit(tree)

        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}")

    def analyze_repository(self, repo_path: str):
        """
        Analyze all Python files in a repository and build the complete call graph.

        :param repo_path: Path to the repository root
        """
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    self.analyze_file(file_path)

    def print_call_graph(self):
        """Print a formatted representation of the call graph."""
        print("Call Graph:")
        # Sort files for consistent output
        for file_path in sorted(self.files_to_functions.keys()):
            print(f"\nFile: {file_path}")
            # Functions are already in order of appearance
            for node in self.files_to_functions[file_path]:
                class_prefix = f"{node.class_name}." if node.class_name else ""
                print(f"{class_prefix}{node.name}:")
                print(
                    f"  Calls: {', '.join(str(n) for n in sorted(node.callees, key=lambda x: x.name)) or 'No direct calls'}"
                )
                print(
                    f"  Called by: {', '.join(str(n) for n in sorted(node.callers, key=lambda x: x.name)) or 'Never called'}"
                )


@click.command()
@click.option(
    "--project-path", "-p", required=True, help="Path to the Python project to analyze"
)
def cli(project_path: str):
    """Analyze Python function call graphs in a project."""
    analyzer = CallGraphAnalyzer()
    analyzer.analyze_repository(project_path)
    analyzer.print_call_graph()

    print("\nUnreachable Functions:")
    unreachable = analyzer.find_unreachable_functions()
    for node in sorted(unreachable, key=lambda x: x.name):
        class_prefix = f"{node.class_name}." if node.class_name else ""
        print(f"- {class_prefix}{node.name} (defined in {node.filename})")


if __name__ == "__main__":
    cli()
