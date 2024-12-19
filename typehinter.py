from difflib import unified_diff
from pathlib import Path

from git.repo import Repo
from langchain_anthropic import ChatAnthropic

from call_graph_analyzer import CallGraphAnalyzer, FunctionNode
from conversation import Conversation


class TypeHinter:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.repo = Repo(project_path)
        self.analyzer = CallGraphAnalyzer()
        self.conversation = Conversation(
            ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.1,
                max_tokens=4096,
            )
        )

        # Analyze the codebase upfront
        self.analyzer.analyze_repository(str(project_path))

    def normalize_indentation(self, source_lines: list[str]) -> tuple[str, int]:
        """Normalize the indentation of source code lines.

        Removes the base indentation while preserving relative indentation of the code block.
        The first non-empty line is used as the reference for the base indentation level.

        Returns:
            tuple[str, int]: The normalized source code and the original base indentation level
        """
        if not source_lines:
            return "", 0

        # Find the indentation of the function signature (first line)
        first_line = source_lines[0]
        base_indent = len(first_line) - len(first_line.lstrip())

        # Remove the base indentation from all lines, preserving relative indentation
        normalized_lines = []
        for line in source_lines:
            if line.strip():  # For non-empty lines
                # Remove only the base indentation
                if line.startswith(" " * base_indent):
                    normalized_lines.append(line[base_indent:])
                else:
                    # If line has less indentation than base (shouldn't happen for valid Python)
                    normalized_lines.append(line.lstrip())
            else:
                # Preserve empty lines
                normalized_lines.append(line[base_indent:])

        return "".join(normalized_lines), base_indent

    def get_function_source(
        self, file_path: Path, function_node: FunctionNode
    ) -> tuple[str, int]:
        """Get the source code of a function, normalized to remove leading indentation.

        Returns:
            tuple[str, int]: The normalized source code and the original base indentation level
        """
        with open(file_path, "r") as f:
            source_lines = f.readlines()

        # Get the function lines
        function_lines = source_lines[
            function_node.lineno - 1 : function_node.end_lineno
        ]
        return self.normalize_indentation(function_lines)

    def get_type_hints(
        self, function_source: str, file_path: Path, function_name: str
    ) -> str:
        """Get type hints for a function using context from the call graph."""
        function_node = None
        for node in self.analyzer.nodes.values():
            if node.name == function_name and node.filename == str(file_path):
                function_node = node
                break

        if not function_node:
            return function_source

        # Build context about related functions
        context = []
        if function_node.callers:
            context.append("Called by functions:")
            for caller in function_node.callers:
                context.append(
                    f"- {caller.class_name + '.' if caller.class_name else ''}{caller.name}"
                )

        if function_node.callees:
            context.append("\nCalls these functions:")
            for callee in function_node.callees:
                context.append(
                    f"- {callee.class_name + '.' if callee.class_name else ''}{callee.name}"
                )

        context_str = "\n".join(context)

        prompt = f"""Add appropriate type hints to this Python function from file {file_path.name}.
        
Function Context:
{context_str}

Here's the function to type hint:

{function_source}

Return ONLY the type-hinted version of the function, nothing else.
Keep all existing docstrings, comments, and whitespace exactly as they appear. Only add type hints."""

        return self.conversation.completion(prompt)

    def replace_lines_in_file(
        self, file_path: Path, start_line: int, end_line: int, new_content: str
    ) -> None:
        """Replace specific lines in a file with new content.

        Args:
            file_path: Path to the file to modify
            start_line: Line number where replacement should begin (1-based)
            end_line: Line number where replacement should end (1-based)
            new_content: The new content to insert
        """
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Convert new_content to lines, preserving the final newline if it exists
        new_lines = new_content.splitlines(keepends=True)

        # Replace the specified lines with the new content
        lines[start_line - 1 : end_line] = new_lines

        # Write the modified content back to the file
        with open(file_path, "w") as f:
            f.writelines(lines)

    def update_file_with_type_hints(
        self,
        file_path: Path,
        hinted_func: str,
        base_indent: int,
        function_node: FunctionNode,
    ) -> None:
        """Update the file by replacing the original function with its type-hinted version.

        Args:
            file_path: Path to the file to modify
            hinted_func: The new type-hinted function code
            base_indent: The original indentation level to maintain
            function_node: The FunctionNode containing line number information
        """
        # Re-indent the type-hinted function
        indented_lines = []
        for line in hinted_func.splitlines():
            # Add the original base indentation to each line
            indented_lines.append(" " * base_indent + line if line.strip() else line)
        indented_hinted_func = "\n".join(indented_lines) + "\n"  # Add final newline

        self.replace_lines_in_file(
            file_path,
            function_node.lineno,
            function_node.end_lineno,
            indented_hinted_func,
        )

    def commit_changes(self, file_path: Path, function_name: str) -> None:
        """Commit the changes to git."""
        relative_path = file_path.relative_to(self.project_path)
        self.repo.index.add([str(relative_path)])
        self.repo.index.commit(f"Add type hints to {function_name} in {file_path.name}")

    def show_diff_and_confirm(
        self, file_path: Path, original_content: str, new_content: str
    ) -> bool:
        """Show diff and get user confirmation for changes."""
        print(f"\nProposed changes for {file_path}:")
        print("=" * 80)

        # Normalize line endings and remove extra blank lines
        original_lines = [line.rstrip() for line in original_content.splitlines()]
        new_lines = [line.rstrip() for line in new_content.splitlines()]

        # Use unified diff format (like git)
        diff = unified_diff(
            original_lines,
            new_lines,
            fromfile=str(file_path),
            tofile=str(file_path),
            lineterm="",
        )
        print("\n".join(diff) + "\n")
        print("=" * 80)

        while True:
            response = input("\nApply these changes? (y/n/q): ").lower()
            if response in ["yes", "y"]:
                return True
            elif response in ["no", "n"]:
                return False
            elif response in ["quit", "q"]:
                print("Exiting program...")
                exit(0)
            print("Please answer 'yes', 'no', or 'quit'")

    def process_project(self) -> None:
        """Process the entire project and add type hints to all functions."""
        walker = self.analyzer.get_walker()

        for function_node in walker:
            file_path = Path(function_node.filename)

            original_source, base_indent = self.get_function_source(
                file_path, function_node
            )
            type_hinted_source = self.get_type_hints(
                original_source, file_path, function_node.name
            )

            if not type_hinted_source:
                continue

            # Show diff and get confirmation
            if self.show_diff_and_confirm(
                file_path, original_source, type_hinted_source
            ):
                self.update_file_with_type_hints(
                    file_path, type_hinted_source, base_indent, function_node
                )
                self.commit_changes(file_path, function_node.name)
            else:
                print(f"Skipping changes to {function_node.name} in {file_path}")
