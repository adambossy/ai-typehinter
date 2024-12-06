import ast
import os
import tempfile
from unittest import TestCase

from call_graph_analyzer import CallGraphAnalyzer


class TestBasicCallGraphAnalyzer(TestCase):
    def setUp(self):
        """Create a test file and initialize the analyzer before each test."""
        self.sample_code = """
def calculate_square(x):
    return x * x

def add_one(num):
    result = calculate_square(num)
    return result + 1
"""
        # Create a temporary file with our test code
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        )
        self.temp_file.write(self.sample_code)
        self.temp_file.close()

        # Initialize and run the analyzer
        self.analyzer = CallGraphAnalyzer()
        self.analyzer.analyze_file(self.temp_file.name)

    def tearDown(self):
        """Clean up the temporary file after each test."""
        os.unlink(self.temp_file.name)

    def test_function_discovery(self):
        """Test that all functions in the file are discovered."""
        self.assertEqual(len(self.analyzer.nodes), 2)
        self.assertIn("calculate_square", self.analyzer.nodes)
        self.assertIn("add_one", self.analyzer.nodes)

    def test_function_relationships(self):
        """Test that function call relationships are correctly identified."""
        calc_square = self.analyzer.nodes["calculate_square"]
        add_one = self.analyzer.nodes["add_one"]

        # Check number of callers and callees
        self.assertEqual(len(calc_square.callers), 1)
        self.assertEqual(len(calc_square.callees), 0)
        self.assertEqual(len(add_one.callers), 0)
        self.assertEqual(len(add_one.callees), 1)

        # Verify the specific call relationships
        self.assertIn(add_one, calc_square.callers)
        self.assertIn(calc_square, add_one.callees)

    def test_file_attribution(self):
        """Test that functions are correctly attributed to their source files."""
        calc_square = self.analyzer.nodes["calculate_square"]
        add_one = self.analyzer.nodes["add_one"]

        self.assertEqual(calc_square.filename, self.temp_file.name)
        self.assertEqual(add_one.filename, self.temp_file.name)

    def test_class_attribution(self):
        """Test that functions not in classes have None as their class_name."""
        calc_square = self.analyzer.nodes["calculate_square"]
        add_one = self.analyzer.nodes["add_one"]

        self.assertIsNone(calc_square.class_name)
        self.assertIsNone(add_one.class_name)

    def test_unreachable_functions(self):
        """Test identification of functions that are never called."""
        add_one = self.analyzer.nodes["add_one"]

        unreachable = self.analyzer.find_unreachable_functions()
        self.assertEqual(len(unreachable), 1)
        self.assertEqual(unreachable[0], add_one)  # Only add_one is unreachable
