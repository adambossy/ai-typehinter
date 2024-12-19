import click
from dotenv import load_dotenv

from typehinter import TypeHinter


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
