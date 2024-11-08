# AI TypeHinter

Automatically add type hints to Python projects using Claude API.

## Installation

```bash
pip install poetry
poetry install
```

## Usage

1. Set up your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY=your-api-key
   ```
   Or create a `.env` file:
   ```
   ANTHROPIC_API_KEY=your-api-key
   ```

2. Run the type hinter:
   ```bash
   poetry run typehint --project-path /path/to/your/project
   ```

   Or with explicit API key:
   ```bash
   poetry run typehint --project-path /path/to/your/project --api-key your-api-key
   ```

## Features

- Automatically adds type hints to Python functions using Claude API
- Processes one function at a time
- Creates separate git commits for each function
- Preserves existing docstrings and comments
- Handles errors gracefully

## Requirements

- Python 3.10+
- Git repository
- Anthropic API key

## License

MIT
