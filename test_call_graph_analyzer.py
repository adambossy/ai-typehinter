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
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()
        # Define the specific name for the temporary file
        self.temp_file_name = os.path.join(self.temp_dir, "test_module.py")

        # Write the sample code to the file
        with open(self.temp_file_name, "w") as f:
            f.write(self.sample_code)

        # Initialize and run the analyzer
        self.analyzer = CallGraphAnalyzer()
        self.analyzer.analyze_file(self.temp_file_name)

    def tearDown(self):
        """Clean up the temporary file and directory after each test."""
        os.unlink(self.temp_file_name)
        os.rmdir(self.temp_dir)

    def test_function_discovery(self):
        """Test that all functions in the file are discovered."""
        self.assertEqual(len(self.analyzer.nodes), 2)
        self.assertIn("test_module.calculate_square", self.analyzer.nodes)
        self.assertIn("test_module.add_one", self.analyzer.nodes)

    def test_add_one_calls_calculate_square(self):
        """Test that add_one correctly records calculate_square as its callee."""
        add_one = self.analyzer.nodes["test_module.add_one"]
        calc_square = self.analyzer.nodes["test_module.calculate_square"]

        # Check that add_one calls exactly one function
        self.assertEqual(len(add_one.callees), 1)
        # Verify that function is calculate_square
        self.assertIn(calc_square, add_one.callees)

    def test_calculate_square_is_called_by_add_one(self):
        """Test that calculate_square correctly records add_one as its caller."""
        add_one = self.analyzer.nodes["test_module.add_one"]
        calc_square = self.analyzer.nodes["test_module.calculate_square"]

        # Check that calculate_square is called by exactly one function
        self.assertEqual(len(calc_square.callers), 1)
        # Verify that function is add_one
        self.assertIn(add_one, calc_square.callers)

    def test_file_attribution(self):
        """Test that functions are correctly attributed to their source files."""
        calc_square = self.analyzer.nodes["test_module.calculate_square"]
        add_one = self.analyzer.nodes["test_module.add_one"]

        self.assertEqual(calc_square.filename, self.temp_file_name)
        self.assertEqual(add_one.filename, self.temp_file_name)

    def test_unreachable_functions(self):
        """Test identification of functions that are never called."""
        add_one = self.analyzer.nodes["test_module.add_one"]

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
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()
        # Define the specific name for the temporary file
        self.temp_file_name = os.path.join(self.temp_dir, "test_module.py")

        # Write the sample code to the file
        with open(self.temp_file_name, "w") as f:
            f.write(self.sample_code)
        # Create a temporary directory

        # Initialize and run the analyzer
        self.analyzer = CallGraphAnalyzer()
        self.analyzer.analyze_file(self.temp_file_name)

    def tearDown(self):
        """Clean up the temporary file and directory after each test."""
        os.unlink(self.temp_file_name)
        os.rmdir(self.temp_dir)

    def test_function_discovery(self):
        """Test that all functions (both module-level and class methods) are discovered."""
        expected_nodes = {
            "builtins.sum",
            "test_module.format_price",
            "test_module.process_shopping_cart",
            "test_module.ShoppingCart.__init__",
            "test_module.ShoppingCart.add_item",
            "test_module.ShoppingCart.calculate_total",
        }
        actual_nodes = set(self.analyzer.nodes.keys())
        self.assertSetEqual(actual_nodes, expected_nodes)

    def test_process_cart_calls_add_item(self):
        """Test that process_shopping_cart calls ShoppingCart.add_item."""
        process_cart = self.analyzer.nodes["test_module.process_shopping_cart"]
        add_item = self.analyzer.nodes["test_module.ShoppingCart.add_item"]

        self.assertIn(add_item, process_cart.callees)
        self.assertIn(process_cart, add_item.callers)

    def test_add_item_calls_calculate_total(self):
        """Test that add_item calls calculate_total."""
        add_item = self.analyzer.nodes["test_module.ShoppingCart.add_item"]
        calc_total = self.analyzer.nodes["test_module.ShoppingCart.calculate_total"]

        self.assertIn(calc_total, add_item.callees)
        self.assertIn(add_item, calc_total.callers)

    def test_calculate_total_calls_format_price(self):
        """Test that calculate_total calls format_price."""
        calc_total = self.analyzer.nodes["test_module.ShoppingCart.calculate_total"]
        format_price = self.analyzer.nodes["test_module.format_price"]

        self.assertIn(format_price, calc_total.callees)
        self.assertIn(calc_total, format_price.callers)

    def test_file_attribution(self):
        """Test that all functions are correctly attributed to the source file."""
        for node in self.analyzer.nodes.values():
            self.assertTrue(
                node.filename == "builtins" or node.filename == self.temp_file_name
            )

    def test_unreachable_functions(self):
        """Test identification of functions that are never called."""
        process_cart = self.analyzer.nodes["test_module.process_shopping_cart"]

        unreachable = self.analyzer.find_unreachable_functions()
        self.assertEqual(len(unreachable), 1)
        self.assertEqual(
            unreachable[0], process_cart
        )  # Only process_shopping_cart is unreachable


class TestCallGraphWalker(TestCase):
    def setUp(self):
        """Set up test by creating a temporary file with library system code and analyzing it."""
        self.library_code = """
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class Book:
    def __init__(self, title: str, author: str, isbn: str) -> None:
        self.title = title
        self.author = author
        self.isbn = isbn
        self.checked_out = False
        self.due_date = None

    def __str__(self) -> str:
        status = "Checked Out" if self.checked_out else "Available"
        return f"{self.title} by {self.author} ({status})"


class Library:
    def __init__(self):
        self.books = {}  # Intentionally untyped
        self.members = []  # Intentionally untyped

    def add_book(self, book: Book) -> None:
        self.books[book.isbn] = book

    def add_member(self, member_id, name):  # Intentionally untyped parameters
        self.members.append({"id": member_id, "name": name})

    def checkout_book(self, isbn: str) -> Optional[datetime]:
        if isbn not in self.books:
            return None

        book = self.books[isbn]
        if book.checked_out:
            return None

        book.checked_out = True
        book.due_date = datetime.now() + timedelta(days=14)
        return book.due_date

    def return_book(self, isbn):  # Intentionally untyped parameter
        if isbn in self.books:
            book = self.books[isbn]
            book.checked_out = False
            book.due_date = None
            return True
        return False

    def get_all_books(self) -> List[Book]:
        return list(self.books.values())

    def get_available_books(self):  # Intentionally untyped return
        return [book for book in self.books.values() if not book.checked_out]


def main():
    # Example usage
    library = Library()

    # Add some books
    books = [
        Book("The Hobbit", "J.R.R. Tolkien", "978-0547928227"),
        Book("Dune", "Frank Herbert", "978-0441172719"),
        Book("Foundation", "Isaac Asimov", "978-0553293357"),
    ]

    for book in books:
        library.add_book(book)

    # Add some members
    library.add_member("M001", "John Doe")
    library.add_member("M002", "Jane Smith")

    # Checkout and return books
    print("All books:")
    for book in library.get_all_books():
        print(book)

    print("\\nChecking out The Hobbit...")
    due_date = library.checkout_book("978-0547928227")
    if due_date:
        print(f"Due date: {due_date}")

    print("\\nAvailable books:")
    for book in library.get_available_books():
        print(book)


if __name__ == "__main__":
    main()
"""
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file_name = os.path.join(self.temp_dir, "library_system.py")

        # Write the library code to the temporary file
        with open(self.temp_file_name, "w") as f:
            f.write(self.library_code)

        # Initialize and run the analyzer
        self.analyzer = CallGraphAnalyzer()
        self.analyzer.analyze_file(self.temp_file_name)

        # Create the walker
        self.walker = self.analyzer.get_walker()

    def tearDown(self):
        """Clean up temporary files."""
        os.unlink(self.temp_file_name)
        os.rmdir(self.temp_dir)

    def test_analyzer_nodes(self):
        """Test that all expected nodes are present in the analyzer."""
        expected_nodes = {
            "library_system.Book.__init__",
            "library_system.Book.__str__",
            "library_system.Library.__init__",
            "library_system.Library.add_book",
            "library_system.Library.add_member",
            "library_system.Library.checkout_book",
            "library_system.Library.return_book",
            "library_system.Library.get_all_books",
            "library_system.Library.get_available_books",
            "library_system.main",
            "builtins.print",
            "builtins.list",
            "datetime.timedelta",
            "datetime.datetime.now",
        }

        actual_nodes = set(self.analyzer.nodes.keys())
        self.assertSetEqual(actual_nodes, expected_nodes)

    def test_leaf_nodes(self):
        """Test that leaf nodes (functions with no callees) are correctly identified."""
        expected_leaf_functions = {
            "library_system.Book.__init__",
            "library_system.Book.__str__",
            "library_system.Library.add_book",
            "library_system.Library.add_member",
            "library_system.Library.return_book",
            "library_system.Library.__init__",
            "library_system.Library.get_available_books",
            "builtins.print",
            "builtins.list",
            "datetime.timedelta",
            "datetime.datetime.now",
        }

        actual_leaf_nodes = {node.name for node in self.walker.leaf_nodes}
        print(f"Actual leaf nodes: {actual_leaf_nodes}")

        self.assertSetEqual(actual_leaf_nodes, expected_leaf_functions)

    def test_walker_iteration(self):
        """Test that walking through the call graph visits all nodes in bottom-up order."""
        expected_nodes = {
            "library_system.Book.__init__",
            "library_system.Book.__str__",
            "library_system.Library.__init__",
            "library_system.Library.add_book",
            "library_system.Library.add_member",
            "library_system.Library.checkout_book",
            "library_system.Library.return_book",
            "library_system.Library.get_all_books",
            "library_system.Library.get_available_books",
            "library_system.main",
        }

        # Collect all nodes visited by the walker
        visited_nodes = set()
        for node in self.walker:
            visited_nodes.add(node.name)

        # Verify we visited all expected nodes
        self.assertSetEqual(visited_nodes, expected_nodes)
