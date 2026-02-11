#!/usr/bin/env python3
"""
pytest 配置文件
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from pathlib import Path


def pytest_configure(config):
    """pytest 配置"""
    test_dir = Path(__file__).parent
    config.addinivalue_line("markers", "integration: mark test as integration test")


@pytest.fixture
def temp_dir(tmp_path):
    """临时目录 fixture"""
    return tmp_path


@pytest.fixture
def sample_audio_file(temp_dir):
    """创建示例音频文件"""
    audio_file = temp_dir / "sample.mp3"
    audio_file.write_bytes(b"\x00" * 1024)
    return audio_file
