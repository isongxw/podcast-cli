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

## Lint/Format Commands

```bash
ruff check src/ --fix   # Lint with ruff (recommended)
ruff format src/        # Format with ruff
mypy src/               # Type check
```

## Development Workflow

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run a single test with verbose output
pytest tests/unit/test_config.py::test_load_config -v

# Run tests with coverage
pytest --cov=src --cov-report=term-missing
```

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

## Configuration

- Config stored in `~/.podcli/config.yaml`
- Use `pydantic-settings` for config management
- Use `yaml.safe_load()` and `yaml.dump()` for YAML I/O
- **IMPORTANT: When modifying config schema in `src/config/schema.py`, also update `_get_default_config()` in `src/config/__init__.py` to ensure YAML config file stays in sync**

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
- Use `async`/`await` for I/O-bound operations (HTTP requests, file I/O)

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

### Logging Pattern

```python
from loguru import logger

logger.info("正在搜索播客: {query}", query=search_term)
logger.debug("API响应: {response}", response=result)
logger.warning("音频文件不存在: {path}", path=audio_path)
logger.error("下载失败: {error}", error=str(e))
```

### Async Operations

```python
import asyncio
from aiohttp import ClientSession

async def fetch_data(url: str) -> dict:
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Run async in CLI
result = asyncio.run(async_operation())
```

## CLI Development

- Use `click` for command-line interface
- Use `rich` for beautiful terminal output (tables, progress bars, panels)
- Entry point: `podcli` command defined in `pyproject.toml`

## Pre-commit Checklist

- [ ] Code runs without syntax errors
- [ ] No debug print statements
- [ ] Functions have Chinese docstrings
- [ ] Error handling covers edge cases
- [ ] CLI commands work with `--help`