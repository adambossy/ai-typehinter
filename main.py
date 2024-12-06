import ast
from pathlib import Path
from typing import List

import click
from dotenv import load_dotenv
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

    def get_python_files(self) -> List[Path]:
        """Get all Python files in the project directory."""
        return list(self.project_path.rglob("*.py"))

    def get_function_source(self, file_path: Path, function_node: FunctionNode) -> str:
        """Get the source code of a function."""
        with open(file_path, "r") as f:
            source_lines = f.readlines()
        return "".join(
            source_lines[function_node.lineno - 1 : function_node.end_lineno]
        )

    def get_type_hints(
        self, function_source: str, file_path: Path, function_name: str
    ) -> str:
        """Get type hints for a function using context from the call graph."""

        print(f"Entering get_type_hints with parameters:")
        print(f"  function_source: {function_source}")
        print(f"  file_path: {file_path}")
        print(f"  function_name: {function_name}")

        # Get calling and callee functions
        function_node = None
        for node in self.analyzer.nodes.values():
            if node.name == function_name and node.filename == str(file_path):
                function_node = node
                break

        print(f"Found function node: {function_node}")

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
Keep all existing docstrings and comments. Only add type hints."""

        return self.conversation.completion(prompt)

    def update_file_with_type_hints(
        self, file_path: Path, original_func: str, hinted_func: str
    ) -> None:
        """Update the file by replacing the original function with its type-hinted version."""
        with open(file_path, "r") as f:
            content = f.read()

        new_content = content.replace(original_func, hinted_func)

        with open(file_path, "w") as f:
            f.write(new_content)

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

        # Create a simple diff output
        for i, (old_line, new_line) in enumerate(
            zip(original_content.splitlines(), new_content.splitlines())
        ):
            if old_line != new_line:
                print(f"- {old_line}")
                print(f"+ {new_line}")
        print("=" * 80)

        while True:
            response = input("\nApply these changes? (yes/no): ").lower()
            if response in ["yes", "y"]:
                return True
            elif response in ["no", "n"]:
                return False
            print("Please answer 'yes' or 'no'")

    def process_project(self) -> None:
        """Process the entire project and add type hints to all functions."""
        python_files = self.get_python_files()

        for file_path in python_files:
            walker = self.analyzer.get_walker()
            for function_node in walker:
                original_source = self.get_function_source(file_path, function_node)
                type_hinted_source = self.get_type_hints(
                    original_source, file_path, function_node.name
                )

                if not type_hinted_source:
                    print(f"Skipping {function_node.name} in {file_path}")
                    continue

                # Show diff and get confirmation
                if self.show_diff_and_confirm(
                    file_path, original_source, type_hinted_source
                ):
                    self.update_file_with_type_hints(
                        file_path, original_source, type_hinted_source
                    )
                    self.commit_changes(file_path, function_node.name)
                else:
                    print(f"Skipping changes to {function_node.name} in {file_path}")


@click.command()
@click.option(
    "--project-path",
    "-p",
    required=True,
    help="Path to the Python project to type hint",
)
def cli(project_path: str):
    """Add type hints to Python projects using Claude API."""
    type_hinter = TypeHinter(project_path)
    type_hinter.process_project()


if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env file
    cli()
