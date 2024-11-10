import ast
from pathlib import Path
from typing import List

import click
from aider import models
from aider.coders import Coder
from aider.io import InputOutput
from dotenv import load_dotenv
from git.repo import Repo


class TypeHinter:
    def __init__(self, project_path: str, coder: Coder):
        self.project_path = Path(project_path)
        self.coder = coder
        self.repo = Repo(project_path)

    def get_python_files(self) -> List[Path]:
        """Get all Python files in the project directory."""
        return list(self.project_path.rglob("*.py"))

    def extract_functions(self, file_path: Path) -> List[ast.FunctionDef]:
        """Extract all function definitions from a Python file."""
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node)
        return functions

    def get_function_source(
        self, file_path: Path, function_node: ast.FunctionDef
    ) -> str:
        """Get the source code of a function."""
        with open(file_path, "r") as f:
            source_lines = f.readlines()
        return "".join(
            source_lines[function_node.lineno - 1 : function_node.end_lineno]
        )

    def get_type_hints(self, function_source: str, file_path: Path) -> str:
        """Get type hints for a function using Aider's Coder interface."""
        prompt = f"""Add appropriate type hints to this Python function from file {file_path.name}. 
        Return ONLY the type-hinted version of the function, nothing else.
        Keep all existing docstrings and comments. Only add type hints.
        
        Here's the function:
        
        {function_source}"""

        response = self.coder.run_one(prompt, preproc=True)
        print(f"Response: {response}")
        return response

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
            # Add file to context before processing
            self.coder.add_rel_fname(str(file_path))
            
            functions = self.extract_functions(file_path)
            for func in functions:
                original_source = self.get_function_source(file_path, func)
                type_hinted_source = self.get_type_hints(original_source, file_path)

                # Show diff and get confirmation
                if self.show_diff_and_confirm(
                    file_path, original_source, type_hinted_source
                ):
                    self.update_file_with_type_hints(
                        file_path, original_source, type_hinted_source
                    )
                    self.commit_changes(file_path, func.name)
                else:
                    print(f"Skipping changes to {func.name} in {file_path}")
            
            # Remove file from context after processing
            self.coder.remove_file(str(file_path))


@click.command()
@click.option(
    "--project-path",
    "-p",
    required=True,
    help="Path to the Python project to type hint",
)
def cli(project_path: str):
    """Add type hints to Python projects using Claude API."""
    main_model = models.Model(
        "claude-3-5-sonnet-20241022",
        editor_model="claude-3-5-sonnet-20241022",
        editor_edit_format="editor-diff",
    )

    io = InputOutput(llm_history_file="typehinter_chat_history.txt")
    coder = Coder.create(main_model=main_model, io=io)

    type_hinter = TypeHinter(project_path, coder)
    type_hinter.process_project()


if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env file
    cli()
