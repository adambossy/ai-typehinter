import tempfile
import unittest
from pathlib import Path

import libcst as cst
import pytest
from libcst._exceptions import ParserSyntaxError
from libcst.metadata import MetadataWrapper

from type_hint_remover import TypeHintCollector, TypeHintRemover


class TestTypeHintCollectorBase:
    def process_code(self, code: str) -> str:
        """Helper method to process code using TypeHintCollector."""
        code = code.strip()
        module = cst.parse_module(code)
        wrapper = MetadataWrapper(module)
        modified_module = wrapper.visit(self.collector)
        return modified_module.code

    def var_annotation(self, annotations, var_name):
        """Helper method to get variable annotation."""
        return annotations["variables"][var_name].annotation.value

    def func_annotation(self, annotations, func_name):
        """Helper method to get function return annotation."""
        return annotations["functions"][func_name].annotation.value

    def param_annotation(self, annotations, func_name):
        """Helper method to get function parameter annotation."""
        return annotations["parameters"][func_name].annotation.value


class TestTypeHintRemoval(TestTypeHintCollectorBase):
    def setup_method(self):
        """Set up a TypeHintCollector for collecting type hints."""
        self.collector = TypeHintCollector()

    def test_remove_function_type_hints(self):
        """Test removing type hints from function signatures."""
        # Input code with type hints
        original = """
def validates_schema(
    fn: Callable[..., Any] | None = None,
    pass_many: bool = False,
    pass_original: bool = False,
    skip_on_field_errors: bool = True,
) -> Callable[..., Any]:
    pass
"""
        # Expected output without type hints
        expected_output = """
def validates_schema(
    fn = None,
    pass_many = False,
    pass_original = False,
    skip_on_field_errors = True,
):
    pass
"""
        # Process the code
        processed = self.process_code(original)

        # Normalize whitespace for comparison
        processed = processed.strip()
        expected_output = expected_output.strip()

        assert processed == expected_output

    def test_remove_variable_type_hints(self):
        """Test removing variable type annotations."""
        original = """
x: int = 5
y: str = "hello"
z: List[int] = []
"""
        expected_output = """
x = 5
y = "hello"
z = []
"""
        processed = self.process_code(original)

        assert processed.strip() == expected_output.strip()

    def test_remove_class_attribute_type_hints(self):
        """Test removing type hints from class attributes."""
        original = """
class MyClass:
    x: int
    y: str = "hello"

    def __init__(self, z: float = 1.0) -> None:
        self.z: float = z
"""
        expected_output = """
class MyClass:
    x = None
    y = "hello"

    def __init__(self, z = 1.0):
        self.z = z
"""
        processed = self.process_code(original)

        assert processed.strip() == expected_output.strip()

    def test_preserve_docstrings_and_comments(self):
        """Test that docstrings and comments are preserved."""
        original = '''def process_data(data: List[str]) -> Dict[str, int]:
    """
    Process the input data.

    Args:
        data: List of strings to process
    Returns:
        Dict mapping strings to counts
    """
    # Initialize the result dictionary
    result: Dict[str, int] = {}  # type hint should be removed but comment kept
    return result
'''
        expected_output = '''def process_data(data):
    """
    Process the input data.

    Args:
        data: List of strings to process
    Returns:
        Dict mapping strings to counts
    """
    # Initialize the result dictionary
    result = {}  # type hint should be removed but comment kept
    return result
'''
        processed = self.process_code(original)

        assert processed.strip() == expected_output.strip()

    def test_handle_empty_file(self):
        """Test handling of empty files."""
        original = ""
        processed = self.process_code(original)

        assert processed == ""

    def test_handle_invalid_python(self):
        """Test handling of invalid Python code."""
        original = "this is not valid python"
        try:
            self.process_code(original)
            assert False, "Expected a ParserSyntaxError"
        except ParserSyntaxError:
            pass

    def teardown_method(self):
        """Clean up after each test."""
        self.collector = None


class TestProcessSingleFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.remover = TypeHintRemover(self.temp_dir)

    def test_process_file_contents(self):
        self.maxDiff = None
        """Test processing file contents with type hints, docstrings, and comments."""
        input_code = '''
def process_data(data: List[str]) -> Dict[str, int]:
    """Process the input data and return a dictionary of results.
    
    Args:
        data: List of strings to process
    
    Returns:
        Dictionary mapping strings to counts
    """
    result = {}  # Initialize empty dictionary

    # Process each item in the data
    for item in data:
        if item in result:  # Check if we've seen this item
            result[item] += 1
        else:
            result[item] = 1  # First occurrence

    return result'''

        expected_output = '''
def process_data(data):
    """Process the input data and return a dictionary of results.
    
    Args:
        data: List of strings to process
    
    Returns:
        Dictionary mapping strings to counts
    """
    result = {}  # Initialize empty dictionary

    # Process each item in the data
    for item in data:
        if item in result:  # Check if we've seen this item
            result[item] += 1
        else:
            result[item] = 1  # First occurrence

    return result'''

        input_code = input_code.strip()

        result = self.remover.process_file_contents(input_code)

        result = result.strip()
        expected_output = expected_output.strip()

        print("Input: ", input_code)
        print("Output: ", result)
        print("Expected: ", expected_output)

        self.assertEqual(result, expected_output)


class TestTypeHintCollection(TestTypeHintCollectorBase):
    def setup_method(self):
        """Set up a TypeHintCollector for collecting type hints."""
        self.collector = TypeHintCollector()

    def test_no_type_hint_assignment(self):
        """Test that simple assignment without type hint collects nothing."""
        original = "x = 5"

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == original
        assert len(annotations["variables"]) == 0

    def test_simple_type_hint_assignment(self):
        """Test that simple assignment with type hint collects the type."""
        original = "x: int = 5"
        expected_output = "x = 5"

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output
        assert len(annotations["variables"]) == 1
        assert "<module>.x" in annotations["variables"]
        assert self.var_annotation(annotations, "<module>.x") == "int"

    def test_function_no_type_hints(self):
        """Test that function without type hints collects nothing."""
        original = """
def foo(bar):
    return bar + 1"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == original.strip()
        assert len(annotations["functions"]) == 0
        assert len(annotations["parameters"]) == 0

    def test_function_param_type_hint(self):
        """Test that function with parameter type hint collects the type."""
        original = """
def foo(bar: int):
    return bar + 1"""
        expected_output = """
def foo(bar):
    return bar + 1"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output.strip()
        assert len(annotations["parameters"]) == 1
        assert "<module>.foo.bar" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.foo.bar") == "int"

    def test_function_param_and_return_type_hints(self):
        """Test that function with parameter and return type hints collects both types."""
        original = """
def foo(bar: int) -> int:
    return bar + 1"""
        expected_output = """
def foo(bar):
    return bar + 1"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output.strip()
        assert len(annotations["functions"]) == 1
        assert "<module>.foo" in annotations["functions"]
        assert self.func_annotation(annotations, "<module>.foo") == "int"
        assert len(annotations["parameters"]) == 1
        assert "<module>.foo.bar" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.foo.bar") == "int"

    def test_class_no_type_hints(self):
        """Test that class without type hints collects nothing."""
        original = """
class Foo:
    def __init__(self):
        pass"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == original.strip()
        assert len(annotations["functions"]) == 0
        assert len(annotations["parameters"]) == 0
        assert len(annotations["variables"]) == 0

    def test_class_init_param_type_hint(self):
        """Test that class __init__ with parameter type hint collects the type."""
        original = """
class Foo:
    def __init__(self, z: float = 1.0):
        pass"""
        expected_output = """
class Foo:
    def __init__(self, z = 1.0):
        pass"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output.strip()
        assert len(annotations["parameters"]) == 1
        assert "<module>.Foo.__init__.z" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.Foo.__init__.z") == "float"

    def test_class_init_with_return_type(self):
        """Test that class __init__ with return type annotation collects the type."""
        original = """
class Foo:
    def __init__(self, z: float = 1.0) -> None:
        pass"""
        expected_output = """
class Foo:
    def __init__(self, z = 1.0):
        pass"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output.strip()
        assert len(annotations["functions"]) == 1
        assert "<module>.Foo.__init__" in annotations["functions"]
        assert self.func_annotation(annotations, "<module>.Foo.__init__") == "None"
        assert len(annotations["parameters"]) == 1
        assert "<module>.Foo.__init__.z" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.Foo.__init__.z") == "float"

    def test_class_init_with_assignment(self):
        """Test that class __init__ with type hints and assignment collects all types."""
        original = """
class Foo:
    def __init__(self, z: float = 1.0) -> None:
        self.z: float = z"""
        expected_output = """
class Foo:
    def __init__(self, z = 1.0):
        self.z = z"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output.strip()
        assert len(annotations["functions"]) == 1
        assert "<module>.Foo.__init__" in annotations["functions"]
        assert self.func_annotation(annotations, "<module>.Foo.__init__") == "None"
        assert len(annotations["parameters"]) == 1
        assert "<module>.Foo.__init__.z" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.Foo.__init__.z") == "float"
        assert len(annotations["variables"]) == 1
        assert "<module>.Foo.__init__.z" in annotations["variables"]
        assert self.var_annotation(annotations, "<module>.Foo.__init__.z") == "float"

    def test_class_init_with_two_assignments(self):
        """Test that class __init__ with type hints and assignment collects all types."""
        original = """
class Foo:
    def __init__(self, y: str, z: float = 1.0) -> None:
        self.y: str = y
        self.z: float = z"""
        expected_output = """
class Foo:
    def __init__(self, y, z = 1.0):
        self.y = y
        self.z = z"""

        processed = self.process_code(original)
        annotations = self.collector.annotations

        assert processed == expected_output.strip()
        assert len(annotations["functions"]) == 1
        assert "<module>.Foo.__init__" in annotations["functions"]
        assert self.func_annotation(annotations, "<module>.Foo.__init__") == "None"
        assert len(annotations["parameters"]) == 2
        assert "<module>.Foo.__init__.y" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.Foo.__init__.y") == "str"
        assert "<module>.Foo.__init__.z" in annotations["parameters"]
        assert self.param_annotation(annotations, "<module>.Foo.__init__.z") == "float"
        assert len(annotations["variables"]) == 2
        assert "<module>.Foo.__init__.y" in annotations["variables"]
        assert self.var_annotation(annotations, "<module>.Foo.__init__.y") == "str"
        assert "<module>.Foo.__init__.z" in annotations["variables"]
        assert self.var_annotation(annotations, "<module>.Foo.__init__.z") == "float"

    def teardown_method(self):
        """Clean up after each test."""
        self.collector = None
