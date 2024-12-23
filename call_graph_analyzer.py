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
        is_called_only: bool = False,
        lineno: int = None,
        end_lineno: int = None,
    ):
        self.name: str = name
        self.filename: str = filename
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
        return f"FunctionNode({self.name})"

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
        self.leaf_nodes = [node for node in analyzer.nodes.values() if not node.callees]

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

            self.leaf_nodes.extend(current.callers)

            # is_called_only is short-hand for builtins. we don't want to type hint them but we do
            # want their callers so we can work our way up the call tree
            if not current.is_called_only:
                self.visited.add(current)
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
        # Add a dictionary to track imports
        self.imports = {}  # Maps local names to full module paths

    def push_node(self, node_name: str):
        self.current_namespace.append(node_name)

    def pop_node(self):
        self.current_namespace.pop()

    def get_namespace(self) -> str:
        return ".".join(self.current_namespace)

    def visit_Module(self, node: ast.Module) -> None:
        module_name = os.path.splitext(os.path.basename(self.current_file))[0]
        self.push_node(module_name)
        self.generic_visit(node)
        self.pop_node()

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track the current class being visited."""
        old_class = self.current_class
        self.current_class = node.name
        self.push_node(node.name)
        self.generic_visit(node)
        self.pop_node()
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Process a function definition node and analyze its calls.

        Example:
            Input node represents: def process_order(self): ...
            Output: Creates/updates FunctionNode and analyzes its calls
        """
        if self.is_test_function(node.name):
            return

        self.push_node(node.name)
        current_node = self._get_or_create_function_node(node)
        self._analyze_function_calls(node, current_node)
        self.generic_visit(node)
        self.pop_node()

    def _get_or_create_function_node(self, node: ast.FunctionDef) -> FunctionNode:
        """Create or retrieve a FunctionNode for the given function definition."""
        node_name = self.get_namespace()
        current_node = self.nodes.get(node_name)

        if not current_node:
            # Get the position metadata for the node
            current_node = FunctionNode(
                name=node_name,
                filename=self.current_file,
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
        # Check if the function is from an imported module
        if func_node.id in self.imports:
            return f"{self.imports[func_node.id]}"

        # Check if the function is a built-in function
        if func_node.id in dir(builtins):
            return f"builtins.{func_node.id}"

        # Check for class instantiations. The node_name will be something like
        # test_module.ShoppingCart.__init__, so we split out the ShoppingCart token
        # and use that to check against
        if func_node.id in [
            node_name.split(".")[-2]
            for node_name in self.nodes.keys()
            if len(node_name.split(".")) > 1
        ]:
            class_name = func_node.id
            return f"{self.get_namespace()}.{class_name}.__init__"

        # For regular function calls, include the module name
        return f"{self.get_namespace()}.{func_node.id}"

    def _resolve_attribute_call(self, func_node: ast.Attribute) -> str:
        """Resolve a method call (e.g., object.method()).

        Example:
            Input: AST node for 'self.calculate_total()'
            Output: 'test_module.ShoppingCart.calculate_total'
        """
        if not isinstance(func_node.value, ast.Name):
            return None

        instance_name = func_node.value.id
        method_name = func_node.attr

        # Handle calls on imported modules
        if instance_name in self.imports:
            base_module = self.imports[instance_name]
            return f"{base_module}.{method_name}"

        # Handle self.method() calls within a class
        if instance_name == "self" and self.current_class:
            namespace = ".".join(self.current_namespace[:-2])
            return f"{namespace}.{self.current_class}.{method_name}"

        # Handle method calls on instances
        if instance_name in self.nodes.keys():
            namespace = ".".join(self.current_namespace[:-1])
            return f"{namespace}.{method_name}"

        # Try to find the class name from the instance
        for node_name in self.nodes:
            if node_name.endswith(f".{instance_name}"):
                class_name = node_name.split(".")[-2]
                namespace = ".".join(self.current_namespace[:-1])
                return f"{namespace}.{class_name}.{method_name}"

        # FIXME (adam) There's a slight bug here, which is that in TestClassCallGraphAnalyzer,
        # this returns cart.add_item as test_module.add_item, and this gets "repaired" in
        # _get_or_create_called_node. The reason is that 'cart' can'y be resolved, and we
        # should fix this to ensure this returns the right thing. Writing unit tests for this
        # and _resolve_direct_call would help.

        namespace = ".".join(self.current_namespace[:-1])
        return f"{namespace}.{method_name}"

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
            called_node = FunctionNode(
                name=called_name,
                # Since we don't know the file yet, default to builtins until it gets overridden
                filename="builtins",
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
                print(f"{node.name}:")
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

    def visit_Import(self, node):
        """Handle simple imports like: import datetime"""
        for alias in node.names:
            self.imports[alias.asname or alias.name] = alias.name

    def visit_ImportFrom(self, node):
        """Handle from-imports like: from datetime import datetime, timedelta"""
        module = node.module
        for alias in node.names:
            local_name = alias.asname or alias.name
            self.imports[local_name] = f"{module}.{alias.name}"


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
        print(f"- {node.name} (defined in {node.filename})")


if __name__ == "__main__":
    cli()
