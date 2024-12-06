import ast
import os
from typing import Dict, List, Set

import click


class CallGraphAnalyzer(ast.NodeVisitor):
    def __init__(self):
        # Dictionary to store function call graph
        # Key: function name, Value: set of functions it calls
        self.call_graph: Dict[str, Set[str]] = {}

        # Dictionary to store reverse call graph
        # Key: function name, Value: set of functions that call it
        self.reverse_call_graph: Dict[str, Set[str]] = {}

        # Dictionary to track function definitions
        # Key: function name, Value: filename where it's defined
        self.function_definitions: Dict[str, str] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Record the function definition
        current_function = node.name

        # Skip test functions during graph construction
        if self.is_test_function(current_function):
            return

        self.function_definitions[current_function] = self.current_file

        # Initialize the call graph entries for this function
        if current_function not in self.call_graph:
            self.call_graph[current_function] = set()
        if current_function not in self.reverse_call_graph:
            self.reverse_call_graph[current_function] = set()

        # Analyze function body for function calls
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Try to get the function name being called
                if isinstance(child.func, ast.Name):
                    called_function = child.func.id
                    # Add to forward call graph
                    self.call_graph[current_function].add(called_function)
                    # Add to reverse call graph
                    if called_function not in self.reverse_call_graph:
                        self.reverse_call_graph[called_function] = set()
                    self.reverse_call_graph[called_function].add(current_function)

        # Continue traversing the AST
        self.generic_visit(node)

    def analyze_repository(self, repo_path: str):
        """
        Analyze all Python files in the given repository.

        :param repo_path: Path to the repository root
        """
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    self.analyze_file(file_path)

    def analyze_file(self, file_path: str):
        """
        Analyze a single Python source file.

        :param file_path: Path to the Python source file
        """
        with open(file_path, "r") as f:
            self.current_file = file_path
            try:
                tree = ast.parse(f.read())
                self.visit(tree)
            except SyntaxError:
                print(f"Error parsing {file_path}")

    def get_call_graph(self) -> Dict[str, Set[str]]:
        """
        Retrieve the generated call graph.

        :return: Dictionary representing the function call graph
        """
        return self.call_graph

    def print_call_graph(self):
        """
        Print the call graph in a readable format.
        """
        for func, calls in self.call_graph.items():
            print(f"{func} calls: {', '.join(calls) or 'No direct calls'}")

    def is_test_function(self, func_name: str) -> bool:
        """
        Determine if a function is a test function based on pytest naming conventions.

        :param func_name: Name of the function to check
        :return: True if the function is a test function, False otherwise
        """
        return func_name.startswith("test_") or (  # Test functions
            func_name.startswith("Test") and func_name[0].isupper()
        )  # Test classes

    def find_unreachable_functions(self) -> List[str]:
        """
        Find functions that are defined but never called.
        Excludes test functions and methods that are meant to be called by pytest.

        :return: List of unreachable function names
        """
        all_defined = set(self.function_definitions.keys())
        all_called = set()

        for calls in self.call_graph.values():
            all_called.update(calls)

        # Filter out test functions
        unreachable = all_defined - all_called
        non_test_unreachable = {
            func for func in unreachable if not self.is_test_function(func)
        }

        return list(non_test_unreachable)


@click.command()
@click.option(
    "--project-path", "-p", required=True, help="Path to the Python project to analyze"
)
def cli(project_path: str):
    """Analyze Python function call graphs in a project."""
    analyzer = CallGraphAnalyzer()
    analyzer.analyze_repository(project_path)

    print("Call Graph:")
    for func, calls in analyzer.call_graph.items():
        callers = analyzer.reverse_call_graph.get(func, set())
        print(f"{func}:")
        print(f"  Calls: {', '.join(calls) or 'No direct calls'}")
        print(f"  Called by: {', '.join(callers) or 'Never called'}")
        print()

    print("\nUnreachable Functions:")
    unreachable = analyzer.find_unreachable_functions()
    for func in unreachable:
        print(f"- {func} (defined in {analyzer.function_definitions[func]})")


if __name__ == "__main__":
    cli()
