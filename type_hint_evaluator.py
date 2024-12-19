import os
import shutil
from datetime import datetime
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper

from type_hint_remover import TypeHintCollector, TypeHintRemover
from typehinter import TypeHinter


class TypeHintEvaluator:
    """Evaluates type hint removal and addition across Python projects."""

    def __init__(self, project_paths: list[str]):
        """
        Initialize with list of project paths to evaluate.

        Args:
            project_paths: List of paths to Python projects to evaluate
        """
        self.project_paths = [Path(p) for p in project_paths]

    def evaluate_projects(self):
        """Process all projects to evaluate type hint removal and addition."""
        for project_path in self.project_paths:
            print(f"\nEvaluating project: {project_path}")
            print("=" * 80)

            # Create output directories
            removed_hints_dir = self._create_output_dir(
                project_path, "with_type_hints_removed"
            )
            added_hints_dir = self._create_output_dir(project_path, "with_type_hints")

            # Step 1: Remove type hints and collect statistics
            print("\nStep 1: Removing and collecting original type hints...")
            original_stats = self._remove_and_collect_hints(
                project_path, removed_hints_dir
            )
            self._save_stats(
                removed_hints_dir, "original_type_hints_report.txt", original_stats
            )

            # Step 2: Add type hints to the hint-free code
            print("\nStep 2: Adding new type hints...")
            self._add_type_hints(removed_hints_dir, added_hints_dir)

            # Step 3: Collect statistics on added type hints
            print("\nStep 3: Collecting statistics on added type hints...")
            added_stats = self._collect_hint_stats(added_hints_dir)
            self._save_stats(
                added_hints_dir, "added_type_hints_report.txt", added_stats
            )

            # Compare results
            self._print_comparison(original_stats, added_stats)

    def _create_output_dir(self, project_path: Path, suffix: str) -> Path:
        """Create and return output directory for processed files."""
        output_dir = project_path.parent / f"{project_path.name}_{suffix}"
        if output_dir.exists():
            shutil.rmtree(output_dir)

        # Copy project files to new directory
        shutil.copytree(project_path, output_dir)
        return output_dir

    def _remove_and_collect_hints(self, project_path: Path, output_dir: Path) -> dict:
        """Remove type hints from project and collect statistics."""
        remover = TypeHintRemover(str(project_path))
        collector = TypeHintCollector()
        stats = {"functions": 0, "parameters": 0, "variables": 0}

        # Process each Python file
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(project_path)
                    output_file = output_dir / relative_path

                    try:
                        # Parse and process the file
                        with open(file_path, "r", encoding="utf-8") as f:
                            source = f.read()

                        module = cst.parse_module(source)
                        wrapper = MetadataWrapper(module)
                        modified_module = wrapper.visit(collector)

                        # Write modified code to output directory
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(modified_module.code)

                        # Update statistics
                        stats["functions"] += len(collector.annotations["functions"])
                        stats["parameters"] += len(collector.annotations["parameters"])
                        stats["variables"] += len(collector.annotations["variables"])

                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")

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


def main():
    # List of projects to evaluate
    projects = ["repos/marshmallow"]

    # Create evaluator and run evaluation
    evaluator = TypeHintEvaluator(projects)
    evaluator.evaluate_projects()


if __name__ == "__main__":
    main()
