from dataclasses import dataclass
from typing import Dict, Optional, Union

import libcst as cst


@dataclass
class VariableInfo:
    """Stores information about a class variable or instance variable."""

    type_annotation: Optional[str]
    is_instance_var: bool  # True if it's self.x, False if class-level


class InstanceVarCollector(cst.CSTTransformer):
    def __init__(self):
        # Store variable name -> type annotation mapping
        self.variables: Dict[str, VariableInfo] = {}
        # Track whether we're inside a class definition
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.current_class = node.name.value
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        self.current_class = None
        return updated_node

    def visit_AnnAssign(self, node: cst.AnnAssign) -> bool:
        """Handle annotated assignments like 'x: int' or 'self.x: int = value'"""
        if self.current_class is None:
            return True

        # Get the type annotation as a string
        annotation = node.annotation.annotation
        type_str = self._get_annotation_string(annotation)

        # Handle both class-level and instance-level annotations
        if isinstance(node.target, cst.Name):
            # Class-level annotation: x: int
            var_name = node.target.value
            self.variables[var_name] = VariableInfo(type_str, is_instance_var=False)
        elif isinstance(node.target, cst.Attribute):
            # Instance-level annotation: self.x: int
            if (
                isinstance(node.target.value, cst.Name)
                and node.target.value.value == "self"
            ):
                var_name = node.target.attr.value
                self.variables[var_name] = VariableInfo(type_str, is_instance_var=True)

        return True

    def visit_Assign(self, node: cst.Assign) -> bool:
        """Handle regular assignments like 'self.x = value'"""
        if self.current_class is None:
            return True

        for target in node.targets:
            if isinstance(target.target, cst.Attribute):
                if (
                    isinstance(target.target.value, cst.Name)
                    and target.target.value.value == "self"
                ):
                    var_name = target.target.attr.value
                    # If we haven't seen this variable before, add it without type annotation
                    if var_name not in self.variables:
                        self.variables[var_name] = VariableInfo(
                            None, is_instance_var=True
                        )

        return True

    def _get_annotation_string(self, node: cst.BaseExpression) -> str:
        """Convert a type annotation node to its string representation."""
        if isinstance(node, cst.Name):
            return node.value
        elif isinstance(node, cst.Attribute):
            # Handle cases like typing.List
            return f"{self._get_annotation_string(node.value)}.{node.attr.value}"
        elif isinstance(node, cst.Subscript):
            # Handle cases like List[str]
            value = self._get_annotation_string(node.value)
            slice_value = self._get_annotation_string(node.slice[0].slice.value)
            return f"{value}[{slice_value}]"
        return str(node)


# Example code to parse
code = """
class MyClass:
    x: int
    y: str = "hello"

    def __init__(self, z: float = 1.0) -> None:
        self.z: float = z
        self.y: int = 1
"""

# Parse the code and collect variables
tree = cst.parse_module(code)
collector = InstanceVarCollector()
tree.visit(collector)

# Print the collected variables
for var_name, info in collector.variables.items():
    print(f"Variable: {var_name}")
    print(f"  Type: {info.type_annotation}")
    print(f"  Is instance var: {info.is_instance_var}")
