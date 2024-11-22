#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from aider.io import InputOutput
from aider.models import Model
from aider.repomap import RepoMap


def main():
    parser = argparse.ArgumentParser(description="Generate a repository map")
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument(
        "--map-tokens",
        type=int,
        default=1024,
        help="Maximum tokens in map (default: 1024)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="Model to use for token counting (default: gpt-3.5-turbo)",
    )
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
        return 1

    io = InputOutput()
    model = Model(args.model)

    repo_map = RepoMap(
        root=str(repo_path),
        map_tokens=args.map_tokens,
        verbose=args.verbose,
        main_model=model,
        io=io,
    )

    # Get all files in repo
    files = [str(p) for p in repo_path.rglob("*") if p.is_file()]
    result = repo_map.get_repo_map([], files)

    if not result:
        print("No repository map generated", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(result)
    else:
        print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
    sys.exit(main())
