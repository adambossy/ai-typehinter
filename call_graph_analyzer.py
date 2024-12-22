import ast
import builtins
import os
from typing import Dict, List, Set

import click

from utils import is_test_file


class FunctionNode:
    def __init__(
        self,
        name: str,
        filename: str,
        class_name: str = None,
        is_called_only: bool = False,
        lineno: int = None,
        end_lineno: int = None,
    ):
        self.name: str = name
        self.filename: str = filename
        self.class_name: str = class_name
        self.callees: Set[FunctionNode] = set()  # Functions this function calls
        self.callers: Set[FunctionNode] = set()  # Functions that call this function
        self.lineno: int = lineno
        self.end_lineno: int = end_lineno
        self.is_called_only: bool = is_called_only

        # Assert that line numbers are not set for called-only functions
        if is_called_only:
            assert (
                lineno is None and end_lineno is None
            ), "Called-only functions should not have line numbers"

    def __repr__(self) -> str:
        class_prefix = f"{self.class_name}." if self.class_name else ""
        return f"FunctionNode({class_prefix}{self.name})"

    def add_callee(self, callee: "FunctionNode"):
        """Add a function that this function calls."""
        self.callees.add(callee)
        callee.callers.add(self)

    def __str__(self) -> str:
        return f"{self.name}"


class CallGraphWalker:
    """Iterator class that walks a call graph from leaf nodes up to their callers."""

    def __init__(self, analyzer: "CallGraphAnalyzer"):
        """Initialize the walker with a CallGraphAnalyzer instance.

        Args:
            analyzer: The CallGraphAnalyzer containing the call graph to walk
        """
        self.analyzer = analyzer
        self.visited = set()
        self.leaf_nodes = [
            node
            for node in analyzer.nodes.values()
            if not node.callees and not node.is_called_only
        ]

    def __iter__(self):
        """Return self as iterator."""
        return self

    def __next__(self) -> FunctionNode:
        """Get the next function in bottom-up order.

        Returns:
            FunctionNode: The next unvisited function in bottom-up order

        Raises:
            StopIteration: When all reachable nodes have been visited
        """
        while self.leaf_nodes:
            current = self.leaf_nodes.pop(0)

            # Skip if we've seen this node before
            if current in self.visited:
                continue

            # Mark as visited and add its callers to the queue
            self.visited.add(current)
            self.leaf_nodes.extend(current.callers)

            return current

        raise StopIteration()


class CallGraphAnalyzer(ast.NodeVisitor):
    def __init__(self):
        # Map of function names to their nodes
        self.nodes: Dict[str, FunctionNode] = {}
        # Map of files to ordered list of function nodes
        self.files_to_functions: Dict[str, List[FunctionNode]] = {}
        # Track current class during traversal
        self.current_class: str = None
        self.current_file: str = None
        self.current_namespace = []

    def visit_Module(self, node: ast.Module) -> None:
        self.current_namespace = [
            os.path.splitext(os.path.basename(self.current_file))[0]
        ]
        self.generic_visit(node)
        self.current_namespace.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track the current class being visited."""
        old_class = self.current_class
        self.current_class = node.name
        self.current_namespace.append(node.name)
        self.generic_visit(node)
        self.current_namespace.pop()
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Process a function definition node and analyze its calls.

        Example:
            Input node represents: def process_order(self): ...
            Output: Creates/updates FunctionNode and analyzes its calls
        """
        if self.is_test_function(node.name):
            return

        self.current_namespace.append(node.name)
        current_node = self._get_or_create_function_node(node)
        self._analyze_function_calls(node, current_node)
        self.generic_visit(node)
        self.current_namespace.pop()

    def _get_or_create_function_node(self, node: ast.FunctionDef) -> FunctionNode:
        """Create or retrieve a FunctionNode for the given function definition."""
        # Include module name in the node_name
        # TODO (adam) Handle full namespace
        module_name = self.current_namespace[0]
        if self.current_class:
            node_name = f"{module_name}.{self.current_class}.{node.name}"
        else:
            node_name = f"{module_name}.{node.name}"

        current_node = self.nodes.get(node_name)

        if not current_node:
            # Get the position metadata for the node
            current_node = FunctionNode(
                name=node.name,
                filename=self.current_file,
                class_name=self.current_class,
                lineno=node.lineno,
                end_lineno=node.end_lineno,
                is_called_only=False,
            )
            self.nodes[node_name] = current_node
            self._track_function_in_file(current_node)
        else:
            # If we found an existing node, update it as we now have its implementation
            current_node.is_called_only = False
            current_node.filename = self.current_file
            current_node.lineno = node.lineno
            current_node.end_lineno = node.end_lineno

        return current_node

    def _track_function_in_file(self, node: FunctionNode):
        """Track the function's order of appearance in its file.

        Example:
            Input: FunctionNode for 'calculate_total'
            Output: self.files_to_functions['/path/to/file.py'] = [..., calculate_total_node]
        """
        if self.current_file not in self.files_to_functions:
            self.files_to_functions[self.current_file] = []
        self.files_to_functions[self.current_file].append(node)

    def _analyze_function_calls(
        self, node: ast.FunctionDef, current_node: FunctionNode
    ):
        """Analyze all function calls within a function body."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called_name = self._resolve_call_name(child)
                if called_name:
                    # Pass the call node to get line numbers
                    called_node = self._get_or_create_called_node(called_name, child)
                    current_node.add_callee(called_node)

    def _resolve_call_name(self, call_node: ast.Call) -> str:
        """Resolve the full name of a called function.

        Example:
            Input: AST node for 'cart.add_item(price)'
            Output: 'ShoppingCart.add_item'
        """
        if isinstance(call_node.func, ast.Name):
            return self._resolve_direct_call(call_node.func)
        elif isinstance(call_node.func, ast.Attribute):
            return self._resolve_attribute_call(call_node.func)
        return None

    def _resolve_direct_call(self, func_node: ast.Name) -> str:
        """Resolve a direct function call (e.g., function_name()).

        Example:
            Input: AST node for 'ShoppingCart()'
            Output: 'test_module.ShoppingCart.__init__'
        """
        # Check if the function is a built-in function
        if func_node.id in dir(builtins):
            return f"builtins.{func_node.id}"

        # TODO (adam) Handle full namespace
        module_name = self.current_namespace[0]

        if func_node.id in [n.class_name for n in self.nodes.values() if n.class_name]:
            return f"{module_name}.{func_node.id}.__init__"

        # For regular function calls, include the module name
        return f"{module_name}.{func_node.id}"

    def _resolve_attribute_call(self, func_node: ast.Attribute) -> str:
        """Resolve a method call (e.g., object.method()).

        Example:
            Input: AST node for 'self.calculate_total()'
            Output: 'test_module.ShoppingCart.calculate_total'
        """
        if not isinstance(func_node.value, ast.Name):
            return None

        # TODO (adam) Handle full namespace
        module_name = self.current_namespace[0]
        instance_name = func_node.value.id
        method_name = func_node.attr

        if instance_name == "self" and self.current_class:
            return f"{module_name}.{self.current_class}.{method_name}"

        # Handle method calls on instances
        if instance_name in [
            n.name for n in self.nodes.values() if isinstance(n.name, str)
        ]:
            return f"{module_name}.{instance_name}.{method_name}"

        # Try to find the class name from the instance
        for node_name in self.nodes:
            if node_name.endswith(f".{instance_name}"):
                class_name = node_name.split(".")[
                    -2
                ]  # Get the class name from the full path
                return f"{module_name}.{class_name}.{method_name}"

        return f"{module_name}.{method_name}"

    def _get_or_create_called_node(
        self, called_name: str, call_node: ast.Call
    ) -> FunctionNode:
        """Get or create a FunctionNode for the called function."""
        called_node = self.nodes.get(called_name)
        if not called_node:
            # Try to find the method with module and class prefix
            for existing_name in self.nodes:
                if existing_name.endswith(f".{called_name.split('.')[-1]}"):
                    return self.nodes[existing_name]

            # Create new node if not found - mark it as called-only
            # TODO (adam) Handle full namespace
            module_name = self.current_namespace[0]
            name_parts = called_name.split(".")

            # Handle different name formats
            # TODO (adam) Woof, this could be cleaner
            if len(name_parts) == 3:  # module.class.method
                class_name = name_parts[1]
                func_name = name_parts[2]
            elif len(name_parts) == 2:  # module.function or class.method
                class_name = name_parts[0] if name_parts[0] != module_name else None
                func_name = name_parts[1]
            else:
                class_name = None
                func_name = called_name

            called_node = FunctionNode(
                name=func_name,
                # Since we don't know the file yet, default to builtins until it gets overridden
                filename="builtins",
                class_name=class_name,
                is_called_only=True,  # Mark as called-only
            )
            self.nodes[called_name] = called_node

        return called_node

    def find_unreachable_functions(self) -> List[FunctionNode]:
        """Find functions that are defined but never called."""
        return [
            node
            for node in self.nodes.values()
            if node.filename
            != "builtins"  # Only consider functions we've found definitions for
            and not node.callers  # No calling functions
            and not self.is_test_function(
                node.name.split(".")[-1]
            )  # Not a test function
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
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.current_file = file_path
        tree = ast.parse(content)
        self.visit(tree)

    def analyze_repository(self, repo_path: str):
        """
        Analyze all Python files in a repository and build the complete call graph.

        :param repo_path: Path to the repository root
        """
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    # Skip test files at the same level as .py extension check
                    if is_test_file(file_path):
                        continue
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

    def get_walker(self) -> CallGraphWalker:
        """Create a new walker to traverse the call graph bottom-up.

        Returns:
            CallGraphWalker: An iterator that yields functions from leaves up to callers
        """
        return CallGraphWalker(self)


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
