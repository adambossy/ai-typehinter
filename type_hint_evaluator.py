import os
import shutil
from datetime import datetime
from pathlib import Path

import click
import libcst as cst
from libcst.metadata import MetadataWrapper

from type_hint_remover import TypeHintCollector, TypeHintRemover
from typehinter import TypeHinter


class TypeHintEvaluator:
    """Evaluates type hint removal and addition across Python projects."""

    def __init__(
        self,
        project_paths: list[str],
        add_type_hints: bool = True,
        remove_type_hints: bool = True,
    ):
        """
        Initialize with list of project paths to evaluate.

        Args:
            project_paths: List of paths to Python projects to evaluate
            add_type_hints: Whether to perform type hint addition step (default: True)
            remove_type_hints: Whether to perform type hint removal step (default: True)
        """
        self.project_paths = [Path(p) for p in project_paths]
        self.add_type_hints = add_type_hints
        self.remove_type_hints = remove_type_hints

    def evaluate_projects(self):
        """Process all projects to evaluate type hint removal and addition."""
        for project_path in self.project_paths:
            print(f"\nEvaluating project: {project_path}")
            print("=" * 80)

            removed_hints_path = self._output_path(
                project_path, "with_type_hints_removed"
            )
            added_hints_path = self._output_path(project_path, "with_type_hints")

            original_stats = {}
            if self.remove_type_hints:
                # Create output directory and remove type hints
                self._create_output_dir(project_path, removed_hints_path)
                print("\nStep 1: Removing and collecting original type hints...")
                original_stats = self._remove_and_collect_hints(
                    project_path, removed_hints_path
                )
                self._save_stats(
                    removed_hints_path, "original_type_hints_report.txt", original_stats
                )
            else:
                print("\nSkipping type hint removal step as requested.")
                # If we're not removing type hints, use the existing directory
                if not removed_hints_path.exists():
                    print(
                        f"Error: Directory {removed_hints_path} not found. Must run with type hint removal first."
                    )
                    return

            if self.add_type_hints:
                print("\nStep 2: Adding new type hints...")
                self._create_output_dir(project_path, added_hints_path)
                self._add_type_hints(removed_hints_path, added_hints_path)
            else:
                print("\nSkipping type hint addition step as requested.")

            # Step 3: Collect statistics on added type hints
            print("\nStep 3: Collecting statistics on added type hints...")
            added_stats = self._collect_hint_stats(added_hints_path)
            self._save_stats(
                added_hints_path, "added_type_hints_report.txt", added_stats
            )

            # Compare results only if we have both original and added stats
            if original_stats:
                self._print_comparison(original_stats, added_stats)

    def _output_path(self, project_path: Path, suffix: str) -> Path:
        return project_path.parent / f"{project_path.name}_{suffix}"

    def _create_output_dir(self, project_path: str, output_path: Path) -> Path:
        """Create and return output directory for processed files."""
        if output_path.exists():
            shutil.rmtree(output_path)

        # Copy project files to new directory
        shutil.copytree(project_path, output_path)

    def _remove_and_collect_hints(self, project_path: Path, output_dir: Path) -> dict:
        """Remove type hints from project and collect statistics."""
        remover = TypeHintRemover(str(project_path), only_show_diffs=False)

        # Process the entire project using TypeHintRemover
        remover.process_project()

        # Collect statistics from the remover's collector
        collector = remover.collector
        stats = {
            "functions": len(collector.annotations["functions"]),
            "parameters": len(collector.annotations["parameters"]),
            "variables": len(collector.annotations["variables"]),
        }

        return stats

    def _add_type_hints(self, input_dir: Path, output_dir: Path):
        """Add type hints to the code (placeholder for future implementation)."""
        # TODO: Implement type hint addition logic
        # For now, just copy files to maintain the structure
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.copytree(input_dir, output_dir)
        type_hinter = TypeHinter(output_dir, auto_commit=True)
        type_hinter.process_project()

    def _collect_hint_stats(self, project_dir: Path) -> dict:
        """Collect statistics about type hints in the project."""
        collector = TypeHintCollector()
        stats = {"functions": 0, "parameters": 0, "variables": 0}

        for root, _, files in os.walk(project_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            source = f.read()

                        module = cst.parse_module(source)
                        wrapper = MetadataWrapper(module)
                        wrapper.visit(collector)

                        stats["functions"] += len(collector.annotations["functions"])
                        stats["parameters"] += len(collector.annotations["parameters"])
                        stats["variables"] += len(collector.annotations["variables"])

                    except Exception as e:
                        print(f"Error collecting stats from {file_path}: {str(e)}")

        return stats

    def _save_stats(self, output_dir: Path, filename: str, stats: dict):
        """Save statistics to a report file."""
        report_path = output_dir / filename
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"Type Hint Statistics Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Function return types: {stats['functions']}\n")
            f.write(f"Function parameters: {stats['parameters']}\n")
            f.write(f"Variable annotations: {stats['variables']}\n")
            f.write(f"Total type hints: {sum(stats.values())}\n")

    def _print_comparison(self, original_stats: dict, added_stats: dict):
        """Print comparison between original and added type hints."""
        print("\nComparison of Type Hints:")
        print("=" * 50)
        print(f"{'Category':<20} {'Original':<10} {'Added':<10} {'Difference':<10}")
        print("-" * 50)

        for category in original_stats:
            orig = original_stats[category]
            added = added_stats[category]
            diff = added - orig
            print(f"{category:<20} {orig:<10} {added:<10} {diff:+d}")

        orig_total = sum(original_stats.values())
        added_total = sum(added_stats.values())
        print("-" * 50)
        print(
            f"{'Total':<20} {orig_total:<10} {added_total:<10} {added_total - orig_total:+d}"
        )


@click.command()
@click.argument("projects", nargs=-1, type=str, required=True)
@click.option(
    "--add-type-hints/--noadd-type-hints",
    default=True,
    help="Whether to perform type hint addition (default: True)",
)
@click.option(
    "--remove-type-hints/--noremove-type-hints",
    default=True,
    help="Whether to perform type hint removal (default: True)",
)
def main(projects: tuple[str, ...], add_type_hints: bool, remove_type_hints: bool):
    """
    Evaluate type hints in Python projects.

    PROJECTS: One or more paths to Python projects to evaluate
    """
    evaluator = TypeHintEvaluator(
        list(projects),
        add_type_hints=add_type_hints,
        remove_type_hints=remove_type_hints,
    )
    evaluator.evaluate_projects()


if __name__ == "__main__":
    main()
