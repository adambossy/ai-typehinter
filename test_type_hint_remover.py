import tempfile
import unittest
from pathlib import Path

import pytest

from type_hint_remover import TypeHintRemover

# class TestTypeHintRemover:
#     def setup_method(self):
#         """Set up a temporary directory for test files."""
#         self.temp_dir = tempfile.mkdtemp()
#         self.remover = TypeHintRemover(self.temp_dir)

#     def test_remove_function_type_hints(self):
#         """Test removing type hints from function signatures."""
#         # Input code with type hints
#         input_code = """
# def validates_schema(
#     fn: Callable[..., Any] | None = None,
#     pass_many: bool = False,
#     pass_original: bool = False,
#     skip_on_field_errors: bool = True,
# ) -> Callable[..., Any]:
#     pass
# """
#         # Expected output without type hints
#         expected_output = """
# def validates_schema(fn=None, pass_many=False, pass_original=False, skip_on_field_errors=True):
#     pass
# """
#         # Create temporary file
#         file_path = Path(self.temp_dir) / "test_func.py"
#         with open(file_path, "w") as f:
#             f.write(input_code)

#         # Process the file
#         original, processed = self.remover.process_file(file_path)

#         # Normalize whitespace for comparison
#         processed = processed.strip()
#         expected_output = expected_output.strip()

#         assert processed == expected_output

#     def test_remove_variable_type_hints(self):
#         """Test removing variable type annotations."""
#         input_code = """
# x: int = 5
# y: str = "hello"
# z: List[int] = []
# """
#         expected_output = """
# x = 5
# y = "hello"
# z = []
# """
#         file_path = Path(self.temp_dir) / "test_vars.py"
#         with open(file_path, "w") as f:
#             f.write(input_code)

#         original, processed = self.remover.process_file(file_path)

#         assert processed.strip() == expected_output.strip()

#     def test_remove_class_attribute_type_hints(self):
#         """Test removing type hints from class attributes."""
#         input_code = """
# class MyClass:
#     x: int
#     y: str = "hello"

#     def __init__(self, z: float = 1.0) -> None:
#         self.z: float = z
# """
#         expected_output = """
# class MyClass:
#     y = "hello"

#     def __init__(self, z=1.0):
#         self.z = z
# """
#         file_path = Path(self.temp_dir) / "test_class.py"
#         with open(file_path, "w") as f:
#             f.write(input_code)

#         original, processed = self.remover.process_file(file_path)

#         assert processed.strip() == expected_output.strip()

#     def test_preserve_docstrings_and_comments(self):
#         """Test that docstrings and comments are preserved."""
#         input_code = '''def process_data(data: List[str]) -> Dict[str, int]:
#     """
#     Process the input data.

#     Args:
#         data: List of strings to process
#     Returns:
#         Dict mapping strings to counts
#     """
#     # Initialize the result dictionary
#     result: Dict[str, int] = {}  # type hint should be removed but comment kept
#     return result
# '''
#         expected_output = '''def process_data(data):
#     """
#     Process the input data.

#     Args:
#         data: List of strings to process
#     Returns:
#         Dict mapping strings to counts
#     """
#     # Initialize the result dictionary
#     result = {} # type hint should be removed but comment kept
#     return result
# '''
#         file_path = Path(self.temp_dir) / "test_docs.py"
#         with open(file_path, "w") as f:
#             f.write(input_code)

#         original, processed = self.remover.process_file(file_path)

#         assert processed.strip() == expected_output.strip()

#     def test_handle_empty_file(self):
#         """Test handling of empty files."""
#         input_code = ""
#         file_path = Path(self.temp_dir) / "empty.py"
#         with open(file_path, "w") as f:
#             f.write(input_code)

#         original, processed = self.remover.process_file(file_path)

#         assert processed == ""

#     def test_handle_invalid_python(self):
#         """Test handling of invalid Python code."""
#         input_code = "this is not valid python"
#         file_path = Path(self.temp_dir) / "invalid.py"
#         with open(file_path, "w") as f:
#             f.write(input_code)

#         with pytest.raises(SyntaxError):
#             self.remover.process_file(file_path)

#     def teardown_method(self):
#         """Clean up temporary files after each test."""
#         import shutil

#         shutil.rmtree(self.temp_dir)


class TestLineMapping(unittest.TestCase):
    def setUp(self):
        """Initialize the TypeHintRemover instance before each test."""
        self.remover = TypeHintRemover("dummy_path")

    def assert_completeness(self, mapping, processed):
        """Assert that every line in the processed source has a corresponding mapping to the original source.

        Args:
            mapping: Dictionary mapping original line numbers to processed line numbers
            processed: The processed source code as a string
        """
        processed_lines = processed.strip().splitlines()
        reverse_mapping = {v: k for k, v in mapping.items()}
        for i in range(1, len(processed_lines) + 1):
            assert i in reverse_mapping, f"Original line {i} should have a mapping"
            assert (
                reverse_mapping[i] > 0
            ), f"Original line {i} should map to a positive line number"
            assert reverse_mapping[i] <= len(
                processed
            ), f"Original line {i} maps beyond processed source"

    def test_all_lines_mapped(self):
        original = """
def func(x: int) -> int:

    # A comment
    y: int = x + 1
    
    return y  # return comment
"""
        processed = """
def func(x):
    y = x + 1
    return y"""

        original = original.strip()
        processed = processed.strip()

        mapping = self.remover.map_original_to_processed_lines(original, processed)

        # Verify specific mappings
        assert mapping[1] == 1  # def line
        assert mapping[4] == 2  # assignment line
        assert mapping[6] == 3  # return line

        self.assert_completeness(mapping, processed)

    def test_basic_mapping(self):
        original = """
def hello(name: str) -> str:
    x: int = 42
    return f"Hello {name}"
"""
        processed = """
def hello(name):
    x = 42
    return f"Hello {name}"
"""
        mapping = self.remover.map_original_to_processed_lines(original, processed)

        assert mapping[1] == 1  # def hello(name):
        assert mapping[2] == 2  # x = 42
        assert mapping[3] == 3  # return f"Hello {name}"

        self.assert_completeness(mapping, processed)

    def test_mapping_with_comments(self):
        original = """
# Type-hinted function
def process(data: List[int]) -> Optional[int]:
    # Process the data
    result: int = 0
    return result
"""
        processed = """
def process(data):
    result = 0
    return result
"""
        mapping = self.remover.map_original_to_processed_lines(original, processed)

        assert mapping[2] == 1  # def process(data):
        assert mapping[4] == 2  # result = 0
        assert mapping[5] == 3  # return result

        self.assert_completeness(mapping, processed)

    def test_complex_type_mapping(self):
        original = """
def complex_func(
    x: Dict[str, Any],
    y: Optional[List[int]]
) -> Tuple[int, str]:
    result: str = "test"
    return 1, result
"""
        processed = """
def complex_func(
    x,
    y
):
    result = "test"
    return 1, result
"""
        mapping = self.remover.map_original_to_processed_lines(original, processed)

        assert mapping[1] == 1  # def complex_func(
        assert mapping[2] == 2  # x,
        assert mapping[3] == 3  # y
        assert mapping[4] == 4  # ):
        assert mapping[5] == 5  # result = "test"
        assert mapping[6] == 6  # return 1, result

        self.assert_completeness(mapping, processed)

    def test_multiline_docstring_mapping(self):
        original = """
def func(x: int) -> int:
    \"\"\"
    This is a docstring
    that spans multiple lines
    \"\"\"
    y: int = x + 1
    return y
"""
        processed = """
def func(x):
    \"\"\"
    This is a docstring
    that spans multiple lines
    \"\"\"
    y = x + 1
    return y
"""
        mapping = self.remover.map_original_to_processed_lines(original, processed)

        assert mapping[1] == 1  # def func(x):
        assert mapping[2] == 2  # """
        assert mapping[3] == 3  # This is a docstring
        assert mapping[4] == 4  # that spans multiple lines
        assert mapping[5] == 5  # """
        assert mapping[6] == 6  # y = x + 1
        assert mapping[7] == 7  # return y

        self.assert_completeness(mapping, processed)

    def test_whole_file(self):
        original = '''
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

        processed = '''
def process_data(data):
    """Process the input data and return a dictionary of results.
    
    Args:
        data: List of strings to process
    
    Returns:
        Dictionary mapping strings to counts
    """
    result = {}
    for item in data:
        if item in result:
            result[item] += 1
        else:
            result[item] = 1
    return result'''

        original = original.strip()
        processed = processed.strip()

        mapping = self.remover.map_original_to_processed_lines(original, processed)

        assert mapping[1] == 1  # def process_data(data):
        assert (
            mapping[2] == 2
        )  # """Process the input data and return a dictionary of results.
        assert mapping[3] == 3  #
        assert mapping[4] == 4  # Args:
        assert mapping[5] == 5  #     data: List of strings to process
        assert mapping[6] == 6  #
        assert mapping[7] == 7  # Returns:
        assert mapping[8] == 8  #     Dictionary mapping strings to counts
        assert mapping[9] == 9  # """
        assert mapping[10] == 10  # result = {}
        assert mapping[13] == 11  # for item in data:
        assert mapping[14] == 12  #     if item in result:
        assert mapping[15] == 13  #         result[item] += 1
        assert mapping[16] == 14  #     else:
        assert mapping[17] == 15  #         result[item] = 1
        assert mapping[19] == 16  # return result

        self.assert_completeness(mapping, processed)


class TestGetComments:
    def setup_method(self):
        """Set up test instance."""
        self.remover = TypeHintRemover("dummy_path")

    def test_get_comments_with_mixed_content(self):
        """Test extracting comments from code with docstrings and both inline and standalone comments."""
        input_code = '''
def process_data(data: List[str]) -> Dict[str, int]:
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

        input_code = input_code.strip()
        comments = self.remover.get_comments(input_code)

        assert comments == {
            10: ("    # Initialize the result dictionary", True),
            11: (" # type hint should be removed but comment kept", False),
        }

    def test_standalone_comment_before_line(self):
        """Test extracting a standalone comment before a line."""
        source = """# Initialize x
x = 1"""
        comments = self.remover.get_comments(source)
        assert comments == {1: ("# Initialize x", True)}

    def test_standalone_comment_after_line(self):
        """Test extracting a standalone comment after a line."""
        source = """x = 1
# End of initialization"""
        comments = self.remover.get_comments(source)
        assert comments == {2: ("# End of initialization", True)}

    def test_inline_comment_end_of_line(self):
        """Test extracting an inline comment at the end of a line."""
        source = "x = 1 # Initialize counter"
        comments = self.remover.get_comments(source)
        assert comments == {1: (" # Initialize counter", False)}

    def test_standalone_before_and_inline_same_line(self):
        """Test extracting a standalone comment before a line and an inline comment."""
        source = """# Initialize variable
x = 1 # Counter variable"""
        comments = self.remover.get_comments(source)
        assert comments == {
            1: ("# Initialize variable", True),
            2: (" # Counter variable", False),
        }

    def test_standalone_after_and_inline_same_line(self):
        """Test extracting a standalone comment after a line and an inline comment."""
        source = """x = 1 # Counter variable
# End of initialization"""
        comments = self.remover.get_comments(source)
        assert comments == {
            1: (" # Counter variable", False),
            2: ("# End of initialization", True),
        }

    def test_multiple_standalone_comments_same_line(self):
        """Test extracting multiple standalone comments and an inline comment."""
        source = """# First comment
# Second comment
x = 1 # Inline comment"""
        comments = self.remover.get_comments(source)
        assert comments == {
            1: ("# First comment", True),
            2: ("# Second comment", True),
            3: (" # Inline comment", False),
        }


class TestMergeComments:
    def setup_method(self):
        """Set up test instance."""
        self.remover = TypeHintRemover("dummy_path")

    def test_merge_comments_with_mixed_content(self):
        """Test merging comments with processed code."""
        processed_source = '''
def process_data(data):
    """
    Process the input data.

    Args:
        data: List of strings to process
    Returns:
        Dict mapping strings to counts
    """
    result = {}
    return result
'''
        original_source = '''
def process_data(data: List[str]) -> Dict[str, int]:
    """
    Process the input data.

    Args:
        data: List of strings to process
    Returns:
        Dict mapping strings to counts
    """
    # Initialize the result dictionary

    result: Dict[str, int] = {} # type hint should be removed but comment kept
    return result
'''

        processed_source = processed_source.strip()
        original_source = original_source.strip()

        comments = {
            10: ("    # Initialize the result dictionary", True),
            12: (" # type hint should be removed but comment kept", False),
        }

        expected_output = '''
def process_data(data):
    """
    Process the input data.

    Args:
        data: List of strings to process
    Returns:
        Dict mapping strings to counts
    """
    # Initialize the result dictionary

    result = {} # type hint should be removed but comment kept
    return result
'''
        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )

        print("Processed: ", processed_source)
        print("Expected: ", expected_output)
        print("Merged: ", merged)

        assert merged.strip() == expected_output.strip()

    def test_merge_mixed_standalone_and_inline_comments(self):
        """Test merging both standalone and inline comments."""
        processed_source = """
line1
line2
line3"""
        comments = {
            2: ("    # standalone comment", True),
            3: (" # inline comment", False),
            4: ("    # another standalone", True),
        }
        expected = """
line1
    # standalone comment
line2 # inline comment
    # another standalone
line3"""

        processed_source = processed_source.strip()
        original_source = expected = (
            expected.strip()
        )  # Can reuse expected as original here since we're not removing typehints

        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )

        print("Processed: ", processed_source)
        print("Expected: ", expected)
        print("Merged: ", merged)

        assert merged.strip() == expected.strip()

    def test_standalone_comment_before_line(self):
        """Test inserting a standalone comment before a line of code."""
        processed_source = "x = 1"
        original_source = """# Initialize x
x: int = 1"""
        comments = {1: ("# Initialize x", True)}
        expected = """# Initialize x
x = 1"""
        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )
        assert merged.strip() == expected.strip()

    def test_standalone_comment_after_line(self):
        """Test inserting a standalone comment after a line of code."""
        processed_source = "x = 1"
        original_source = """x: int = 1
# End of initialization"""
        comments = {2: ("# End of initialization", True)}
        expected = """x = 1
# End of initialization"""
        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )
        assert merged.strip() == expected.strip()

    def test_inline_comment_end_of_line(self):
        """Test appending an inline comment to the end of a line."""
        processed_source = "x = 1"
        original_source = "x: int = 1 # Initialize counter"
        comments = {1: (" # Initialize counter", False)}
        expected = "x = 1 # Initialize counter"
        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )
        assert merged.strip() == expected.strip()

    def test_standalone_before_and_inline_same_line(self):
        """Test inserting a standalone comment before a line and an inline comment at the end."""
        processed_source = "x = 1"
        original_source = """# Initialize variable
x: int = 1 # Counter variable"""
        comments = {
            1: ("# Initialize variable", True),
            2: (" # Counter variable", False),
        }
        expected = """# Initialize variable
x = 1 # Counter variable"""
        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )
        assert merged.strip() == expected.strip()

    def test_standalone_after_and_inline_same_line(self):
        """Test inserting a standalone comment after a line and an inline comment at the end."""
        processed_source = "x = 1"
        original_source = """x: int = 1 # Counter variable
# End of initialization"""
        comments = {
            1: (" # Counter variable", False),
            2: ("# End of initialization", True),
        }
        expected = """x = 1 # Counter variable
# End of initialization"""
        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )
        assert merged.strip() == expected.strip()

    def test_multiple_standalone_comments_same_line(self):
        """Test handling multiple standalone comments before a line."""
        processed_source = "x = 1"
        comments = {
            1: ("# First comment", True),
            2: ("# Second comment", True),
            3: (" # Inline comment", False),
        }
        expected = """
# First comment
# Second comment
x = 1 # Inline comment"""
        original_source = expected = (
            expected.strip()
        )  # We can reuse expected as original here since we're not removing typehints

        merged = self.remover.merge_comments(
            processed_source, original_source, comments
        )

        print("Processed: ", processed_source)
        print("Expected: ", expected)
        print("Merged: ", merged)

        assert merged.strip() == expected.strip()


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
    result = {} # Initialize empty dictionary

    # Process each item in the data
    for item in data:
        if item in result: # Check if we've seen this item
            result[item] += 1
        else:
            result[item] = 1 # First occurrence

    return result'''

        input_code = input_code.strip()

        result = self.remover.process_file_contents(input_code)

        result = result.strip()
        expected_output = expected_output.strip()

        print("Input: ", input_code)
        print("Output: ", result)
        print("Expected: ", expected_output)

        self.assertEqual(result, expected_output)


class TestLinesMatch(unittest.TestCase):
    def setUp(self):
        """Initialize the TypeHintRemover instance before each test."""
        self.remover = TypeHintRemover("dummy_path")

    def test_basic_matching(self):
        self.assertTrue(self.remover.lines_match("def hello", "def hello"))
        self.assertTrue(self.remover.lines_match("def hello", "def hello:"))

    def test_type_hints(self):
        self.assertTrue(self.remover.lines_match("def hello", "def hello(x: int)"))
        self.assertTrue(
            self.remover.lines_match("def test", "def test(data: List[str]) -> bool:")
        )
        self.assertTrue(self.remover.lines_match("x = 5", "x: int = 5"))
        self.assertTrue(self.remover.lines_match("data = []", "data: List[str] = []"))

    def test_comments(self):
        self.assertTrue(self.remover.lines_match("x = 1", "x = 1  # comment"))
        self.assertTrue(
            self.remover.lines_match("def test", "def test  # testing function")
        )

    def test_empty_lines(self):
        self.assertTrue(self.remover.lines_match("    ", "    "))
        self.assertFalse(self.remover.lines_match("def test", ""))

    def test_non_matching_lines(self):
        self.assertFalse(self.remover.lines_match("def hello", "def world"))
        self.assertFalse(self.remover.lines_match("x = 1", "y = 1"))
        self.assertFalse(self.remover.lines_match("def hello_world", "def hello"))

    def test_complex_type_hints(self):
        self.assertTrue(
            self.remover.lines_match(
                "def process_data",
                "def process_data(items: List[Dict[str, Any]], config: Optional[Config] = None) -> Iterator[Result]:",
            )
        )

    def test_whitespace_variations(self):
        self.assertTrue(self.remover.lines_match("def test", "   def test   "))
        self.assertTrue(self.remover.lines_match("x=1", "x = 1"))

    def test_special_characters(self):
        self.assertTrue(self.remover.lines_match("def test_*", "def test_*(x: int):"))
        self.assertTrue(
            self.remover.lines_match("@decorator", "@decorator(param=True)")
        )

    def test_none_inputs(self):
        with self.assertRaises(AttributeError):
            self.remover.lines_match(None, "test")
        with self.assertRaises(AttributeError):
            self.remover.lines_match("test", None)

    def test_real_world_examples(self):
        self.assertTrue(
            self.remover.lines_match(
                "def process_file(self, file_path)",
                "def process_file(self, file_path: Path) -> Tuple[str, str]:",
            )
        )

        self.assertTrue(
            self.remover.lines_match(
                "class TypeHintRemover", "class TypeHintRemover(ast.NodeTransformer):"
            )
        )

        self.assertTrue(
            self.remover.lines_match(
                "self.line_mapping = {}", "self.line_mapping: Dict[int, int] = {}"
            )
        )

        self.assertTrue(
            self.remover.lines_match(
                "return self.process_file_contents(original_source)",
                "return self.process_file_contents(original_source: str) -> Tuple[str, str]:",
            )
        )
