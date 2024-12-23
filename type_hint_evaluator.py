import os
import shutil
from datetime import datetime
from pathlib import Path

import click
import libcst as cst
from libcst.metadata import MetadataWrapper

from type_hint_remover import TypeHintCollector, TypeHintProcessor, TypeHintRemover
from typehinter import TypeHinter


class TypeHintEvaluator:
    """Evaluates type hint removal and addition across Python projects."""

    def __init__(
        self,
        project_paths: list[str],
        add_type_hints: bool = True,
        remove_type_hints: bool = True,
        log_file: str | None = None,
    ):
        """
        Initialize with list of project paths to evaluate.

        Args:
            project_paths: List of paths to Python projects to evaluate
            add_type_hints: Whether to perform type hint addition step (default: True)
            remove_type_hints: Whether to perform type hint removal step (default: True)
            log_file: Path to the log file
        """
        self.project_paths = [Path(p) for p in project_paths]
        self.add_type_hints = add_type_hints
        self.remove_type_hints = remove_type_hints
        self.log_file = log_file

    def evaluate_projects(self):
        """Process all projects to evaluate type hint removal and addition."""
        for project_path in self.project_paths:
            print(f"\nEvaluating project: {project_path}")
            print("=" * 80)

            removed_hints_path = self._output_path(
                project_path, "with_type_hints_removed"
            )

            original_stats = {}
            original_hints = {}
            if self.remove_type_hints:
                print("\nStep 1: Removing and collecting original type hints...")
                self._copy_project(project_path, removed_hints_path)
                original_stats = self._remove_and_collect_hints(removed_hints_path)
                original_hints = self._collect_detailed_hint_stats(project_path)
                self._save_stats(
                    removed_hints_path, "original_type_hints_report.txt", original_stats
                )
                self._save_detailed_hints(
                    removed_hints_path,
                    "original_type_hints_details.txt",
                    original_hints,
                )
            else:
                print("\nSkipping type hint removal step as requested.")
                # If we're not removing type hints, use the existing directory
                if not removed_hints_path.exists():
                    print(
                        f"Error: Directory {removed_hints_path} not found. Must run with type hint removal first."
                    )
                    return

            added_hints_path = self._output_path(project_path, "with_type_hints")
            if self.add_type_hints:
                print("\nStep 2: Adding new type hints...")
                self._copy_project(removed_hints_path, added_hints_path)
                self._add_type_hints(added_hints_path)
            else:
                print("\nSkipping type hint addition step as requested.")

            # Step 3: Collect statistics and compare
            print("\nStep 3: Collecting and comparing type hints...")

            # Compute original stats if not already done
            if not original_stats:
                print("\nCollecting original type hints without removal...")
                original_stats = self._collect_hint_stats(project_path)
                original_hints = self._collect_detailed_hint_stats(project_path)
                self._save_detailed_hints(
                    project_path, "original_type_hints_details.txt", original_hints
                )

            added_stats = self._collect_hint_stats(added_hints_path)
            added_hints = self._collect_detailed_hint_stats(added_hints_path)
            self._save_stats(
                added_hints_path, "added_type_hints_report.txt", added_stats
            )
            self._save_detailed_hints(
                added_hints_path, "added_type_hints_details.txt", added_hints
            )

            # Compare results
            if original_stats:
                self._print_comparison(original_stats, added_stats)
                # Add detailed comparison
                self._compare_type_hints(project_path, added_hints_path)

    def _output_path(self, project_path: Path, suffix: str) -> Path:
        return project_path.parent / f"{project_path.name}_{suffix}"

    def _copy_project(self, project_path: str, output_path: Path) -> Path:
        """Create and return output directory for processed files."""
        if output_path.exists():
            shutil.rmtree(output_path)

        # Copy project files to new directory
        shutil.copytree(project_path, output_path)

    def _remove_and_collect_hints(self, project_path: Path) -> dict:
        """Remove type hints from project and collect statistics."""
        processor = TypeHintProcessor(str(project_path), only_show_diffs=False)

        # Process the entire project
        processor.process_project()

        # Collect statistics from the processor's collector
        collector = processor.collector
        stats = {
            "functions": len(collector.annotations["functions"]),
            "parameters": len(collector.annotations["parameters"]),
            "variables": len(collector.annotations["variables"]),
        }

        return stats

    def _add_type_hints(self, input_dir: Path):
        """Add type hints to the code (placeholder for future implementation)."""
        # TODO: Implement type hint addition logic
        # For now, just copy files to maintain the structure
        type_hinter = TypeHinter(input_dir, auto_commit=True, log_file=self.log_file)
        type_hinter.process_project()

    def _collect_hint_stats(self, project_dir: Path) -> dict:
        """Collect statistics about type hints in the project."""
        collector = TypeHintCollector()
        stats = {"functions": 0, "parameters": 0, "variables": 0}

        for root, _, files in os.walk(project_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file

                    print(f"Collecting type hints from {file_path}")

                    with open(file_path, "r", encoding="utf-8") as f:
                        source = f.read()

                    source = self.preprocess_source(source)
                    module = cst.parse_module(source)
                    wrapper = MetadataWrapper(module)
                    collector.set_module_name(file_path)
                    wrapper.visit(collector)

                    stats["functions"] += len(collector.annotations["functions"])
                    stats["parameters"] += len(collector.annotations["parameters"])
                    stats["variables"] += len(collector.annotations["variables"])

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

    def _collect_detailed_hint_stats(self, project_dir: Path) -> dict:
        """Collect detailed statistics about type hints in the project, including the actual annotations."""
        collector = TypeHintCollector()

        for root, _, files in os.walk(project_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            source = f.read()

                        source = self.preprocess_source(source)
                        module = cst.parse_module(source)
                        wrapper = MetadataWrapper(module)
                        collector.set_module_name(file_path)
                        wrapper.visit(collector)

                    except Exception as e:
                        print(f"Error collecting stats from {file_path}: {str(e)}")

        return collector.annotations

    def _compare_type_hints(self, original_path: Path, added_path: Path):
        """Compare type hints between original and processed versions in detail."""
        print("\nDetailed Type Hint Comparison:")
        print("=" * 80)

        # Collect detailed annotations from both versions
        original_hints = self._collect_detailed_hint_stats(original_path)
        added_hints = self._collect_detailed_hint_stats(added_path)

        categories = ["functions", "parameters", "variables"]

        for category in categories:
            print(f"\n{category.title()} Type Hints:")
            print("-" * 80)

            original_set = set(original_hints[category].keys())
            added_set = set(added_hints[category].keys())

            # Find items in both, only in original, and only in added
            common = original_set & added_set
            only_original = original_set - added_set
            only_added = added_set - original_set

            # Print items that appear in both versions
            if common:
                print("\nPresent in both versions:")
                for name in sorted(common):
                    original_type = self._get_annotation_string(
                        original_hints[category][name]
                    )
                    added_type = self._get_annotation_string(
                        added_hints[category][name]
                    )
                    if original_type != added_type:
                        print(f"  {name}:")
                        print(f"    Original: {original_type}")
                        print(f"    Added:    {added_type}")
                    else:
                        print(f"  {name}: {original_type} (unchanged)")

            # Print items only in original
            if only_original:
                print("\nOnly in original:")
                for name in sorted(only_original):
                    annotation_str = self._get_annotation_string(
                        original_hints[category][name]
                    )
                    print(f"  {name}: {annotation_str}")

            # Print items only in added
            if only_added:
                print("\nOnly in added:")
                for name in sorted(only_added):
                    annotation_str = self._get_annotation_string(
                        added_hints[category][name]
                    )
                    print(f"  {name}: {annotation_str}")

            # Print summary
            print(f"\nSummary for {category}:")
            print(f"  Total in original: {len(original_set)}")
            print(f"  Total in added: {len(added_set)}")
            print(f"  Common: {len(common)}")
            print(f"  Only in original: {len(only_original)}")
            print(f"  Only in added: {len(only_added)}")

    def _get_annotation_string(self, annotation) -> str:
        """Recursively get the string representation of an annotation."""
        if isinstance(annotation, cst.Annotation):
            return self._get_annotation_string(annotation.annotation)
        elif isinstance(annotation, cst.Name):
            return annotation.value
        elif isinstance(annotation, cst.Subscript):
            value = self._get_annotation_string(annotation.value)
            slices = ", ".join(
                self._get_annotation_string(e.slice.value) for e in annotation.slice
            )
            return f"{value}[{slices}]"
        else:
            return str(annotation)

    def preprocess_source(self, source: str) -> str:
        if source.startswith('"""'):
            end_index = source.find('"""', 3)
            if end_index != -1:
                return source[end_index + 3 :]
        return source

    def _save_detailed_hints(self, output_dir: Path, filename: str, hints: dict):
        """Save detailed type hint information to a file."""
        report_path = output_dir / filename
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"Detailed Type Hint Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")

            for category in ["functions", "parameters", "variables"]:
                f.write(f"\n{category.title()} Type Hints:\n")
                f.write("-" * 50 + "\n")

                # Sort hints by fully qualified name
                sorted_hints = sorted(hints[category].items(), key=lambda x: x[0])

                for name, annotation in sorted_hints:
                    annotation_str = self._get_annotation_string(annotation)
                    f.write(f"{name}: {annotation_str}\n")


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
@click.option(
    "--log-file",
    type=click.Path(),
    help="Path to the log file",
    default=None,
)
def main(
    projects: tuple[str, ...],
    add_type_hints: bool,
    remove_type_hints: bool,
    log_file: str | None,
):
    """
    Evaluate type hints in Python projects.

    PROJECTS: One or more paths to Python projects to evaluate
    """
    evaluator = TypeHintEvaluator(
        list(projects),
        add_type_hints=add_type_hints,
        remove_type_hints=remove_type_hints,
        log_file=log_file,
    )
    evaluator.evaluate_projects()


if __name__ == "__main__":
    main()
