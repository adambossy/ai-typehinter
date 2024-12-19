import libcst as cst
import libcst.matchers as m
from libcst import RemovalSentinel


class TypeHintRemover(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (cst.metadata.ParentNodeProvider,)

    def leave_AnnAssign(self, original_node, updated_node):
        # Convert annotated assignment (x: int = 1) to regular assignment (x = 1)
        print(f"---entering annassign---")
        print(f"target: {updated_node.target}")
        print(f"value: {updated_node.value}")

        # Retrieve and print the type annotation
        if original_node.annotation:
            print(f"annotation: {original_node.annotation}")

        return cst.Assign(
            targets=[cst.AssignTarget(target=updated_node.target)],
            value=updated_node.value or cst.Name("None"),
        )

    def leave_FunctionDef(self, original_node, updated_node):
        # Remove return type annotations
        if original_node.returns:
            # Prints:
            # Annotation(
            #     annotation=Name(
            #         value='int',
            #         lpar=[],
            #         rpar=[],
            #     ),
            #     whitespace_before_indicator=SimpleWhitespace(
            #         value='',
            #     ),
            #     whitespace_after_indicator=SimpleWhitespace(
            #         value=' ',
            #     ),
            # )
            print(f"Return type annotation: {original_node.returns}")

            # Create a new function definition without return type
            return updated_node.with_changes(returns=None)
        return updated_node

    def leave_Param(self, original_node, updated_node):
        # Remove parameter type annotations
        if original_node.annotation:
            print(f"Parameter type annotation: {original_node.annotation}")
            # Create a new parameter without type annotation
            return updated_node.with_changes(annotation=None)
        return updated_node


def remove_type_hints(source_code):
    # Parse the module
    module = cst.parse_module(source_code)

    # Wrap the module with MetadataWrapper
    wrapper = cst.metadata.MetadataWrapper(module)

    # Apply the transformer
    transformer = TypeHintRemover()
    modified_module = wrapper.visit(transformer)

    # Convert back to source code
    return modified_module.code


# Example usage
source = """
# This is a top-level comment
def example_function(x: int, y: str) -> bool:
    # This is an inline comment
    x: int = x + 1  # This is an inline comment
    return x > 5  # Another inline comment
"""

# Remove type hints
modified_source = remove_type_hints(source)

print("---modified source---")
print(modified_source)
