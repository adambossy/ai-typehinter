import ast
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
import anthropic
import git
from git.repo import Repo
import click
from dotenv import load_dotenv

class TypeHinter:
    def __init__(self, project_path: str, api_key: str):
        self.project_path = Path(project_path)
        self.client = anthropic.Client(api_key=api_key)
        self.repo = Repo(project_path)

    def get_python_files(self) -> List[Path]:
        """Get all Python files in the project directory."""
        return list(self.project_path.rglob("*.py"))

    def extract_functions(self, file_path: Path) -> List[ast.FunctionDef]:
        """Extract all function definitions from a Python file."""
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node)
        return functions

    def get_function_source(self, file_path: Path, function_node: ast.FunctionDef) -> str:
        """Get the source code of a function."""
        with open(file_path, 'r') as f:
            source_lines = f.readlines()
        return ''.join(source_lines[function_node.lineno-1:function_node.end_lineno])

    def get_type_hints(self, function_source: str) -> str:
        """Get type hints for a function using Claude API."""
        prompt = f"""Add appropriate type hints to this Python function. Return ONLY the type-hinted version of the function, nothing else.
        Keep all existing docstrings and comments. Only add type hints.
        
        Here's the function:
        
        {function_source}"""

        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def update_file_with_type_hints(self, file_path: Path, original_func: str, hinted_func: str) -> None:
        """Update the file by replacing the original function with its type-hinted version."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        new_content = content.replace(original_func, hinted_func)
        
        with open(file_path, 'w') as f:
            f.write(new_content)

    def commit_changes(self, file_path: Path, function_name: str) -> None:
        """Commit the changes to git."""
        self.repo.index.add([str(file_path)])
        self.repo.index.commit(f"Add type hints to {function_name} in {file_path.name}")

    def process_project(self) -> None:
        """Process the entire project and add type hints to all functions."""
        python_files = self.get_python_files()
        
        for file_path in python_files:
            functions = self.extract_functions(file_path)
            
            for func in functions:
                original_source = self.get_function_source(file_path, func)
                type_hinted_source = self.get_type_hints(original_source)
                self.update_file_with_type_hints(file_path, original_source, type_hinted_source)
                self.commit_changes(file_path, func.name)

@click.command()
@click.option('--project-path', '-p', required=True, help='Path to the Python project to type hint')
@click.option('--api-key', '-k', envvar='ANTHROPIC_API_KEY', help='Anthropic API key (can also be set via ANTHROPIC_API_KEY env var)')
def cli(project_path: str, api_key: str):
    """Add type hints to Python projects using Claude API."""
    if not api_key:
        raise click.UsageError("ANTHROPIC_API_KEY must be provided either via --api-key or environment variable")
    
    try:
        type_hinter = TypeHinter(project_path, api_key)
        type_hinter.process_project()
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()

if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env file
    cli()
