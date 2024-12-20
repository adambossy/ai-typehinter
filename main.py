import click

from typehinter import TypeHinter


@click.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option(
    "--auto-commit",
    is_flag=True,
    help="Automatically commit changes without confirmation",
)
@click.option(
    "--log-file",
    type=click.Path(),
    help="Path to the log file",
    default=None,
)
def main(project_path: str, auto_commit: bool, log_file: str | None) -> None:
    """Add type hints to Python code in the specified project."""
    type_hinter = TypeHinter(project_path, log_file=log_file, auto_commit=auto_commit)
    type_hinter.process_project()


if __name__ == "__main__":
    main()
