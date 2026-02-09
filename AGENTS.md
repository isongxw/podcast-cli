# AGENTS.md

## Project Overview

Python podcast processing CLI tool (`podcli`) with iTunes search, RSS parsing, audio download, and Whisper transcription capabilities.

## Build/Install Commands

```bash
# Install dependencies with uv (recommended)
uv sync

# Or install with pip in editable mode
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

## Test Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_<module>.py

# Run a single test
pytest tests/test_<module>.py::test_<function_name>

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src
```

## Code Style Guidelines

### Imports

```python
#!/usr/bin/env python3
"""
模块描述（中文）
"""

# 1. Standard library imports
import os
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# 2. Third-party imports
import requests
import yaml
import torch
from pydub import AudioSegment
from rich.console import Console

# 3. Local imports (use relative within src/)
from config import Config
from itunes import iTunesSearch
```

### Naming Conventions

- **Modules/Files**: `snake_case.py` (e.g., `cli.py`, `download.py`)
- **Classes**: `CamelCase` (e.g., `WhisperTranscriber`, `RSSParser`)
- **Functions/Variables**: `snake_case` (e.g., `download_audio`, `model_size`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_MODEL`, `MAX_RETRIES`)
- **Private methods**: `_leading_underscore` (e.g., `_load_config`)

### Code Formatting

- **Indentation**: 4 spaces
- **Line length**: 100 characters max
- **Quotes**: Use double quotes for strings, single quotes for dict keys
- **Docstrings**: Chinese comments for modules/functions
- **No trailing whitespace**

### Error Handling

```python
try:
    result = some_operation()
except SpecificException as e:
    console.print(f"[red]操作失败: {e}[/red]")
    # Log error or return error state
    return None
```

- Use `loguru` for logging (imported in dependencies)
- Use `rich.console.Console` for user-facing output
- Always catch specific exceptions, not bare `except:`
- Print error messages in Chinese for user-facing errors

### Type Hints (Optional)

While not currently used, prefer adding type hints for new code:

```python
def search_podcasts(self, query: str, limit: int = 50) -> list[dict]:
    ...
```

### Project Structure

```
src/
├── cli.py              # CLI entry point (Click commands)
├── config.py           # Configuration management (YAML)
├── itunes.py           # iTunes API search
├── rss.py              # RSS feed parsing
├── download.py         # Audio file downloading
├── transcribe.py       # Whisper transcription
└── markdown.py         # Markdown output generation
```

### CLI Development

- Use `click` for command-line interface
- Use `rich` for beautiful terminal output (tables, progress bars, panels)
- Entry point: `podcli` command defined in `pyproject.toml`

### Configuration

- Config stored in `~/.podcli/config.yaml`
- Use `yaml.safe_load()` and `yaml.dump()` for config I/O
- Default config in `config.py` with merge logic for user overrides

### External Dependencies

Key libraries in use:
- `click` - CLI framework
- `rich` - Terminal formatting
- `requests` - HTTP requests
- `whisper` - OpenAI speech recognition
- `pydub` - Audio processing
- `torch` - ML backend
- `yaml` - Config file handling

### Lint/Format Commands (if tools configured)

```bash
# Format code
black src/

# Sort imports
isort src/

# Lint
flake8 src/

# Type check (if mypy added)
mypy src/
```

### Pre-commit Checklist

- [ ] Code runs without syntax errors
- [ ] No debug print statements left in code
- [ ] Functions have Chinese docstrings
- [ ] Error handling covers edge cases
- [ ] CLI commands work with `--help`

## Dependencies

See `pyproject.toml` for full list. Key dev dependencies:
- pytest>=7.4.0
- black>=23.0.0
- isort>=5.12.0
- flake8>=6.0.0
