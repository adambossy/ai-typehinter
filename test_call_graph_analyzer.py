import ast
import os
import tempfile
from unittest import TestCase

from call_graph_analyzer import CallGraphAnalyzer


class TestCallGraphAnalyzer(TestCase):
    def setUp(self):
        self.sample_code = """
def calculate_square(x):
    return x * x

def add_one(num):
    result = calculate_square(num)
    return result + 1
"""

    def test_basic_call_graph(self):
        # Create a temporary file with our test code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(self.sample_code)
            temp_path = f.name

        try:
            # Analyze the file
            analyzer = CallGraphAnalyzer()
            analyzer.analyze_file(temp_path)

            # Check that both functions were found
            self.assertEqual(len(analyzer.nodes), 2)
            self.assertIn("calculate_square", analyzer.nodes)
            self.assertIn("add_one", analyzer.nodes)

            # Get the function nodes
            calc_square = analyzer.nodes["calculate_square"]
            add_one = analyzer.nodes["add_one"]

            # Check function relationships
            self.assertEqual(len(calc_square.callers), 1)
            self.assertEqual(len(calc_square.callees), 0)
            self.assertEqual(len(add_one.callers), 0)
            self.assertEqual(len(add_one.callees), 1)

            # Verify the call relationship
            self.assertIn(add_one, calc_square.callers)
            self.assertIn(calc_square, add_one.callees)

            # Check file attribution
            self.assertEqual(calc_square.filename, temp_path)
            self.assertEqual(add_one.filename, temp_path)

            # Check class attribution (should be None for both)
            self.assertIsNone(calc_square.class_name)
            self.assertIsNone(add_one.class_name)

            # Check unreachable functions
            unreachable = analyzer.find_unreachable_functions()
            self.assertEqual(len(unreachable), 1)
            self.assertEqual(unreachable[0], add_one)  # Only add_one is unreachable

        finally:
            # Clean up the temporary file
            os.unlink(temp_path)
