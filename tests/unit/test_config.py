#!/usr/bin/env python3
"""
配置模块测试
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config.schema import (
    WhisperConfig,
    DownloadConfig,
    OutputConfig,
    SearchConfig,
    PodcliConfig,
)


class TestWhisperConfig:
    """Whisper配置测试"""

    def test_default_values(self):
        config = WhisperConfig()
        assert config.model == "base"
        assert config.device == "cpu"
        assert config.language == "auto"
        assert config.chunk_length == 60

    def test_custom_values(self):
        config = WhisperConfig(
            model="small", device="cuda", language="zh", chunk_length=30
        )
        assert config.model == "small"
        assert config.device == "cuda"
        assert config.language == "zh"
        assert config.chunk_length == 30

    def test_invalid_model(self):
        with pytest.raises(ValueError):
            WhisperConfig(model="invalid")

    def test_invalid_device(self):
        with pytest.raises(ValueError):
            WhisperConfig(device="gpu")

    def test_chunk_length_bounds(self):
        config = WhisperConfig(chunk_length=10)
        assert config.chunk_length == 10

        config = WhisperConfig(chunk_length=600)
        assert config.chunk_length == 600

        with pytest.raises(ValueError):
            WhisperConfig(chunk_length=5)

        with pytest.raises(ValueError):
            WhisperConfig(chunk_length=700)


class TestDownloadConfig:
    """下载配置测试"""

    def test_default_values(self):
        config = DownloadConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 5.0
        assert config.chunk_size == 8192
        assert config.timeout == 60
        assert config.resume_download is True
        assert config.max_concurrent == 3

    def test_custom_values(self):
        config = DownloadConfig(
            max_retries=5,
            retry_delay=10.0,
            chunk_size=16384,
            timeout=120,
            resume_download=False,
            max_concurrent=5,
        )
        assert config.max_retries == 5
        assert config.retry_delay == 10.0


class TestOutputConfig:
    """输出配置测试"""

    def test_default_values(self):
        config = OutputConfig()
        assert str(config.dir) == str(Path.home() / "Podcasts")
        assert config.save_audio is True

    def test_custom_values(self):
        config = OutputConfig(dir=Path("/tmp/test"), save_audio=False)
        assert config.dir == Path("/tmp/test")
        assert config.save_audio is False


class TestSearchConfig:
    """搜索配置测试"""

    def test_default_values(self):
        config = SearchConfig()
        assert config.max_results == 50
        assert config.country == "US"
        assert config.language == "en_us"

    def test_custom_values(self):
        config = SearchConfig(max_results=100, country="CN", language="zh_cn")
        assert config.max_results == 100
        assert config.country == "CN"


class TestPodcliConfig:
    """主配置测试"""

    def test_default_values(self):
        config = PodcliConfig()
        assert isinstance(config.whisper, WhisperConfig)
        assert isinstance(config.download, DownloadConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.search, SearchConfig)
        assert config.debug is False

    def test_nested_override(self):
        config = PodcliConfig(whisper={"model": "large"}, download={"max_retries": 5})
        assert config.whisper.model == "large"
        assert config.download.max_retries == 5


class TestConfigFile:
    """配置文件测试"""

    def test_load_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                yaml.dump(
                    {"whisper": {"model": "medium"}, "output": {"save_audio": False}}
                )
            )

            from src.config import Config

            cfg = Config()
            cfg.config_dir = Path(tmpdir)
            cfg.config_file = config_file
            loaded = cfg._load_config()

            assert loaded["whisper"]["model"] == "medium"
            assert loaded["output"]["save_audio"] is False
