import unittest
from pathlib import Path

from aider.io import InputOutput
from aider.models import Model
from aider.repomap import RepoMap
from aider.utils import GitTemporaryDirectory


class TestRepoMap(unittest.TestCase):
    def setUp(self):
        self.model = Model("gpt-3.5-turbo")

    def test_basic_repo_map(self):
        with GitTemporaryDirectory() as temp_dir:
            # Create test files
            test_files = {
                "main.py": """
def hello():
    print("Hello, World!")

class TestClass:
    def method(self):
        pass

# Use the functions/methods to create references
result = hello()
test = TestClass()
test.method()
""",
                "lib.py": """
def helper():
    return 42

# Reference the helper function
value = helper()
""",
            }

            for fname, content in test_files.items():
                path = Path(temp_dir) / fname
                path.write_text(content)

            io = InputOutput()
            repo_map = RepoMap(main_model=self.model, root=temp_dir, io=io)

            files = [str(Path(temp_dir) / f) for f in test_files]
            result = repo_map.get_repo_map([], files)

            expected_result = """lib.py:
⋮...
│def helper():
⋮...

main.py:
⋮...
│def hello():
⋮...
│class TestClass:
│    def method(self):
⋮..."""
            self.assertEqual(result.strip(), expected_result.strip())


if __name__ == "__main__":
    unittest.main()
