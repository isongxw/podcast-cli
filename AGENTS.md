# AGENTS.md

## Project Overview

Python podcast processing CLI tool (`podcli`) with iTunes search, RSS parsing, audio download, and Qwen ASR transcription capabilities.

## Dependency Management

**IMPORTANT: Use `uv` for all dependency operations.**

```bash
uv sync                  # Install/update dependencies
uv add requests          # Add new dependency
uv add --dev pytest      # Add dev dependency
uv sync --extra dev      # Install dev dependencies
uv remove package_name   # Remove dependency
```

## Build/Install Commands

```bash
uv pip install -e .              # Install in editable mode
uv pip install -e ".[dev]"       # Install with dev dependencies
```

## Test Commands

```bash
pytest                              # Run all tests
pytest tests/unit/test_config.py    # Run single test file
pytest tests/unit/test_config.py::test_load_config  # Run single test
pytest -v                          # Verbose output
pytest --cov=src --cov-report=term-missing  # With coverage
```

## Code Style Guidelines

### Imports Order

1. Standard library (os, sys, pathlib, datetime, urllib.parse)
2. Third-party (requests, yaml, torch, pydub, rich)
3. Local (relative imports within src/)

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `CamelCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

### Formatting & Types

- Indentation: 4 spaces, Line length: 100 chars
- Quotes: double quotes for strings, single for dict keys
- Use Chinese docstrings for modules/functions
- Prefer type hints for new code

### Error Handling

```python
try:
    result = some_operation()
except SpecificException as e:
    console.print(f"[red]操作失败: {e}[/red]")
    return None
```

- Use `loguru` for logging, `rich.console.Console` for output
- Catch specific exceptions, not bare `except:`
- Print error messages in Chinese

## Project Structure

```
src/
├── cli.py              # CLI entry point (Click)
├── config/             # Configuration (YAML, Pydantic)
│   ├── __init__.py
│   └── schema.py
├── core/               # Core modules
│   ├── itunes_search.py
│   ├── rss_parser.py
│   ├── downloader.py
│   ├── transcriber.py
│   └── markdown.py
└── utils/              # Utilities
```

## CLI Development

- Use `click` for command-line interface
- Use `rich` for beautiful terminal output (tables, progress bars, panels)
- Entry point: `podcli` command defined in `pyproject.toml`

## Configuration

- Config stored in `~/.podcli/config.yaml`
- Use `pydantic-settings` for config management
- Use `yaml.safe_load()` and `yaml.dump()` for YAML I/O
- OpenAI API configuration: `base_url`, `api_key`, `model`, etc.
- LLM structured markdown: `structured.enable`, `structured.segment_length`, etc.
- Whisper parallel transcription: `whisper.parallel_workers` (default: 1, max: 4)

## Key Dependencies

- `click` - CLI framework
- `rich` - Terminal formatting
- `requests`/`aiohttp` - HTTP requests
- `feedparser` - RSS parsing
- `pydub` - Audio processing
- `torch`/`transformers` - ML backend
- `qwen-asr` - Speech recognition
- `loguru` - Logging
- `pydantic`/`pydantic-settings` - Config validation

## Lint/Format Commands

```bash
black src/              # Format code
isort src/              # Sort imports
flake8 src/             # Lint
mypy src/               # Type check
ruff check src/ --fix   # Lint with ruff
ruff format src/        # Format with ruff
```

## Pre-commit Checklist

- [ ] Code runs without syntax errors
- [ ] No debug print statements
- [ ] Functions have Chinese docstrings
- [ ] Error handling covers edge cases
- [ ] CLI commands work with `--help`
