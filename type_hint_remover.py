import ast
import os
import tokenize
from difflib import unified_diff
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple

import click

from utils import is_test_file


class TypeHintRemover(ast.NodeTransformer):
    """Removes type hints from Python source code while preserving functionality."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Remove return and argument type annotations from function definitions."""
        # Remove return annotation
        node.returns = None

        # Remove argument annotations
        for arg in node.args.args:
            arg.annotation = None

        # Remove kwonly argument annotations
        for arg in node.args.kwonlyargs:
            arg.annotation = None

        # Remove posonlyargs annotations (Python 3.8+)
        if hasattr(node.args, "posonlyargs"):
            for arg in node.args.posonlyargs:
                arg.annotation = None

        return self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign:
        """Convert annotated assignments to regular assignments."""
        if node.value is None:
            # If it's just a variable annotation without assignment, remove it
            return None

        # Convert to regular assignment
        return ast.Assign(
            targets=[node.target],
            value=node.value,
            lineno=node.lineno,
            col_offset=node.col_offset,
        )

    def get_comments(self, source: str) -> Dict[int, List[Tuple[str, bool]]]:
        """Extract comments and their line numbers from source file.
        Returns Dict[line_number, [(comment_text, is_standalone, col_offset)]]"""
        comments = {}
        # tokens = list(tokenize.tokenize(source))
        tokens = list(tokenize.tokenize(BytesIO(source.encode("utf-8")).readline))

        for token in tokens:
            if token.type == tokenize.COMMENT:
                line_no = token.start[0]
                col_offset = token.start[1]

                # Check if comment is standalone by looking at preceding tokens
                preceding_tokens = [
                    t
                    for t in tokens
                    if t.start[0] == line_no and t.start[1] < col_offset
                ]

                is_standalone = all(
                    t.type
                    in (
                        tokenize.NL,
                        tokenize.NEWLINE,
                        tokenize.INDENT,
                        tokenize.DEDENT,
                    )
                    for t in preceding_tokens
                )

                # Preserve the original whitespace
                whitespace_prefix = " " * col_offset if is_standalone else " "
                comment_text = whitespace_prefix + token.string

                comments[line_no] = (comment_text, is_standalone)

        return comments

    def merge_comments(
        self,
        processed_source: str,
        original_source: str,
        comments: Dict[int, List[Tuple[str, bool]]],
    ) -> str:
        """Merge comments back into processed source code.

        Args:
            processed_source: Source code after type hint removal
            original_source: Original source code with type hints
            comments: Dict mapping line numbers to list of (comment_text, is_standalone) tuples

        Returns:
            Processed source with comments merged back in
        """
        # Get mapping from original to processed lines
        orig_to_proc = self.map_original_to_processed_lines(
            original_source, processed_source
        )

        # Split sources into lines
        processed_lines_dict = {
            i + 1: line for i, line in enumerate(processed_source.strip().splitlines())
        }
        original_lines = original_source.strip().splitlines()

        # Initialize result list
        result_lines = []

        # Iterate through original line numbers
        for orig_line_no in range(1, len(original_lines) + 1):
            # Check if we have a mapping for this line
            if orig_line_no in orig_to_proc:
                # Get the corresponding processed line
                proc_line_no = orig_to_proc[orig_line_no]
                current_line = processed_lines_dict[proc_line_no]

                # Add any inline comments if present
                if orig_line_no in comments:
                    comment_text, is_standalone = comments[orig_line_no]
                    if not is_standalone:
                        current_line += comment_text

                result_lines.append(current_line)

            else:
                # Check if there's a standalone comment for this line
                if orig_line_no in comments:
                    comment_text, is_standalone = comments[orig_line_no]
                    if is_standalone:
                        result_lines.append(comment_text)
                        continue

                # If no mapping and no comment, add empty line
                result_lines.append("")

        return "\n".join(result_lines)

    def process_file(self, file_path: Path) -> Tuple[str, str]:
        """Process a single Python file to remove type hints while preserving comments."""
        # Read original source
        with open(file_path, "r", encoding="utf-8") as f:
            original_source = f.read()

        return self.process_file_contents(original_source)

    def process_file_contents(self, original_source: str) -> Tuple[str, str]:
        original_source = original_source.strip()

        # Remove type hints via AST transformation
        tree = ast.parse(original_source)
        modified_tree = self.visit(tree)

        # Generate processed source while preserving line numbers
        processed_source = ast.unparse(modified_tree)

        # Merge comments back into the processed source
        comments = self.get_comments(original_source)
        final_source = self.merge_comments(processed_source, original_source, comments)

        return final_source

    def process_project(self) -> None:
        """Process all Python files in the project."""
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file

                    # Skip test files
                    if is_test_file(str(file_path)):
                        continue

                    try:
                        original, processed = self.process_file(file_path)

                        # Only show diff if there were changes
                        if original != processed:
                            print(
                                f"\nProcessing: {file_path.relative_to(self.project_path)}"
                            )
                            print("=" * 80)

                            # Show unified diff
                            diff = unified_diff(
                                original.splitlines(keepends=True),
                                processed.splitlines(keepends=True),
                                fromfile=str(file_path),
                                tofile=str(file_path),
                                lineterm="",
                            )
                            print("".join(diff))
                            print("=" * 80)

                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")

    def lines_match(self, proc_line: str, orig_line: str) -> bool:
        """Check if two lines match by comparing their non-type-hint content."""
        # Remove whitespace and comments for comparison
        proc_line = proc_line.split("#")[0].strip()
        orig_line = orig_line.split("#")[0].strip()

        if not proc_line and not orig_line:
            return True

        # Skip empty lines in original
        if not orig_line:
            return False

        i = 0  # pointer for proc_line
        j = 0  # pointer for orig_line

        while i < len(proc_line) and j < len(orig_line):
            # If characters match, advance both pointers
            if proc_line[i] == orig_line[j]:
                i += 1

            # If they don't match, only advance j
            j += 1

            # If we've reached the end of orig_line but haven't matched all of proc_line
            if j >= len(orig_line) and i < len(proc_line):
                return False

        # Return True if we've matched all characters in proc_line
        return i == len(proc_line)

    def map_original_to_processed_lines(
        self,
        original_source: str,
        processed_source: str,
    ) -> Dict[int, int]:
        """Maps lines in processed source to their corresponding lines in original source.

        Uses a line-by-line comparison approach, matching lines based on their common prefixes.
        The processed source contains only code lines (no comments or empty lines), while
        the original source contains all lines including comments and whitespace.

        Args:
            processed_source: The source code after type hint removal (code only)
            original_source: The original source code with type hints, comments, and empty lines

        Returns:
            Dictionary mapping processed line numbers to original line numbers
        """
        processed_lines = processed_source.strip().splitlines()
        original_lines = original_source.strip().splitlines()

        line_mapping = {}
        orig_idx = 0

        # Iterate through processed lines (which are all code lines)
        for proc_idx, proc_line in enumerate(processed_lines, start=1):
            # Look for matching line in original source, starting from current position
            found_match = False
            while orig_idx < len(original_lines):
                orig_line = original_lines[orig_idx]

                if self.lines_match(proc_line, orig_line):
                    line_mapping[orig_idx + 1] = proc_idx
                    orig_idx += 1
                    found_match = True
                    break

                orig_idx += 1

            if not found_match:
                raise ValueError(f"Could not find matching line for: {proc_line}")

        return line_mapping


@click.command()
@click.option(
    "--project-path",
    "-p",
    required=True,
    help="Path to the Python project to remove type hints from",
)
def cli(project_path: str):
    """Remove type hints from Python projects."""
    remover = TypeHintRemover(project_path)
    remover.process_project()


if __name__ == "__main__":
    cli()
