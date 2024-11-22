import os
import shutil
import tempfile
import unittest
from pathlib import Path

from repomap import RepoMap


class TestRepoMap(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir))

    def test_basic_repo_map(self):
        # Create test files
        test_files = {
            "main.py": """
def hello():
    print("Hello, World!")

class TestClass:
    def method(self):
        pass
""",
            "lib.py": """
def helper():
    return 42
""",
        }

        for fname, content in test_files.items():
            path = Path(self.temp_dir) / fname
            path.write_text(content)

        repo_map = RepoMap(root=self.temp_dir)
        files = [str(Path(self.temp_dir) / f) for f in test_files]
        result = repo_map.get_repo_map(files)

        # Basic assertions
        self.assertIsNotNone(result)
        self.assertIn("main.py", result)
        self.assertIn("lib.py", result)


if __name__ == "__main__":
    unittest.main()
    unittest.main()
