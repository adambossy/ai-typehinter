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

    def test_add_one_calls_calculate_square(self):
        """Test that add_one correctly records calculate_square as its callee."""
        add_one = self.analyzer.nodes["add_one"]
        calc_square = self.analyzer.nodes["calculate_square"]

        # Check that add_one calls exactly one function
        self.assertEqual(len(add_one.callees), 1)
        # Verify that function is calculate_square
        self.assertIn(calc_square, add_one.callees)

    def test_calculate_square_is_called_by_add_one(self):
        """Test that calculate_square correctly records add_one as its caller."""
        add_one = self.analyzer.nodes["add_one"]
        calc_square = self.analyzer.nodes["calculate_square"]

        # Check that calculate_square is called by exactly one function
        self.assertEqual(len(calc_square.callers), 1)
        # Verify that function is add_one
        self.assertIn(add_one, calc_square.callers)

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


class TestClassCallGraphAnalyzer(TestCase):
    def setUp(self):
        """Create a test file with class and module functions and initialize the analyzer."""
        self.sample_code = """
def format_price(amount):
    return f"${amount:.2f}"

class ShoppingCart:
    def __init__(self):
        self.items = []
        
    def add_item(self, price):
        self.items.append(price)
        self.calculate_total()
        
    def calculate_total(self):
        total = sum(self.items)
        return format_price(total)

def process_shopping_cart():
    cart = ShoppingCart()
    cart.add_item(10.99)
    return cart
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
        """Test that all functions (both module-level and class methods) are discovered."""
        self.assertEqual(len(self.analyzer.nodes), 6)
        self.assertIn("sum", self.analyzer.nodes)
        self.assertIn("format_price", self.analyzer.nodes)
        self.assertIn("process_shopping_cart", self.analyzer.nodes)
        self.assertIn("ShoppingCart.__init__", self.analyzer.nodes)
        self.assertIn("ShoppingCart.add_item", self.analyzer.nodes)
        self.assertIn("ShoppingCart.calculate_total", self.analyzer.nodes)

    def test_class_attribution(self):
        """Test that class methods are correctly attributed to their class."""
        add_item = self.analyzer.nodes["ShoppingCart.add_item"]
        calc_total = self.analyzer.nodes["ShoppingCart.calculate_total"]
        init_method = self.analyzer.nodes["ShoppingCart.__init__"]
        format_price = self.analyzer.nodes["format_price"]
        process_cart = self.analyzer.nodes["process_shopping_cart"]

        self.assertEqual(add_item.class_name, "ShoppingCart")
        self.assertEqual(calc_total.class_name, "ShoppingCart")
        self.assertEqual(init_method.class_name, "ShoppingCart")
        self.assertIsNone(format_price.class_name)
        self.assertIsNone(process_cart.class_name)

    def test_process_cart_calls_add_item(self):
        """Test that process_shopping_cart calls ShoppingCart.add_item."""
        process_cart = self.analyzer.nodes["process_shopping_cart"]
        add_item = self.analyzer.nodes["ShoppingCart.add_item"]

        self.assertIn(add_item, process_cart.callees)
        self.assertIn(process_cart, add_item.callers)

    def test_add_item_calls_calculate_total(self):
        """Test that add_item calls calculate_total."""
        add_item = self.analyzer.nodes["ShoppingCart.add_item"]
        calc_total = self.analyzer.nodes["ShoppingCart.calculate_total"]

        self.assertIn(calc_total, add_item.callees)
        self.assertIn(add_item, calc_total.callers)

    def test_calculate_total_calls_format_price(self):
        """Test that calculate_total calls format_price."""
        calc_total = self.analyzer.nodes["ShoppingCart.calculate_total"]
        format_price = self.analyzer.nodes["format_price"]

        self.assertIn(format_price, calc_total.callees)
        self.assertIn(calc_total, format_price.callers)

    def test_file_attribution(self):
        """Test that all functions are correctly attributed to the source file."""
        for node in self.analyzer.nodes.values():
            self.assertEqual(node.filename, self.temp_file.name)

    def test_unreachable_functions(self):
        """Test identification of functions that are never called."""
        process_cart = self.analyzer.nodes["process_shopping_cart"]

        unreachable = self.analyzer.find_unreachable_functions()
        self.assertEqual(len(unreachable), 1)
        self.assertEqual(
            unreachable[0], process_cart
        )  # Only process_shopping_cart is unreachable
