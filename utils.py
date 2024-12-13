from pathlib import Path


def is_test_file(file_path: str) -> bool:
    """
    Determine if a file is a test file based on pytest conventions.

    Pytest looks for:
    - Files that start with test_
    - Files that end with _test.py
    - Files in directories named test or tests

    Args:
        file_path: Path to the file to check
    Returns:
        bool: True if the file is a test file
    """
    path = Path(file_path)
    file_name = path.name

    # Check file naming patterns
    if file_name.startswith("test_") or file_name.endswith("_test.py"):
        return True

    # Check if file is in a test directory
    parts = path.parts
    return any(part.lower() in ("test", "tests") for part in parts)
