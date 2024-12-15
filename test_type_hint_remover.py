import tempfile
import unittest
from pathlib import Path

import pytest
from libcst._exceptions import ParserSyntaxError

from type_hint_remover import TypeHintRemover


class TestTypeHintRemover:
    def setup_method(self):
        """Set up a temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.remover = TypeHintRemover(self.temp_dir)

    def test_remove_function_type_hints(self):
        """Test removing type hints from function signatures."""
        # Input code with type hints
        input_code = """
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
        # Create temporary file
        file_path = Path(self.temp_dir) / "test_func.py"
        with open(file_path, "w") as f:
            f.write(input_code)

        # Process the file
        original, processed = self.remover.process_file(file_path)

        # Normalize whitespace for comparison
        processed = processed.strip()
        expected_output = expected_output.strip()

        assert processed == expected_output

    def test_remove_variable_type_hints(self):
        """Test removing variable type annotations."""
        input_code = """
x: int = 5
y: str = "hello"
z: List[int] = []
"""
        expected_output = """
x = 5
y = "hello"
z = []
"""
        file_path = Path(self.temp_dir) / "test_vars.py"
        with open(file_path, "w") as f:
            f.write(input_code)

        original, processed = self.remover.process_file(file_path)

        assert processed.strip() == expected_output.strip()

    def test_remove_class_attribute_type_hints(self):
        """Test removing type hints from class attributes."""
        input_code = """
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
        file_path = Path(self.temp_dir) / "test_class.py"
        with open(file_path, "w") as f:
            f.write(input_code)

        original, processed = self.remover.process_file(file_path)

        assert processed.strip() == expected_output.strip()

    def test_preserve_docstrings_and_comments(self):
        """Test that docstrings and comments are preserved."""
        input_code = '''def process_data(data: List[str]) -> Dict[str, int]:
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
        file_path = Path(self.temp_dir) / "test_docs.py"
        with open(file_path, "w") as f:
            f.write(input_code)

        original, processed = self.remover.process_file(file_path)

        assert processed.strip() == expected_output.strip()

    def test_handle_empty_file(self):
        """Test handling of empty files."""
        input_code = ""
        file_path = Path(self.temp_dir) / "empty.py"
        with open(file_path, "w") as f:
            f.write(input_code)

        original, processed = self.remover.process_file(file_path)

        assert processed == ""

    def test_handle_invalid_python(self):
        """Test handling of invalid Python code."""
        input_code = "this is not valid python"
        file_path = Path(self.temp_dir) / "invalid.py"
        with open(file_path, "w") as f:
            f.write(input_code)

        with pytest.raises(ParserSyntaxError):
            self.remover.process_file(file_path)

    def teardown_method(self):
        """Clean up temporary files after each test."""
        import shutil

        shutil.rmtree(self.temp_dir)


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
