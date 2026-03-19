#!/usr/bin/env python3
"""
配置管理模块

支持YAML配置文件、环境变量、Pydantic验证
"""

import os
from pathlib import Path
from typing import Any

import yaml

from .schema import (
    DownloadConfig,
    OpenAIConfig,
    OutputConfig,
    PodcliConfig,
    SearchConfig,
    StructuredMarkdownConfig,
    WhisperConfig,
    WorkflowConfig,
)


class Config:
    """配置管理类"""

    CONFIG_FILENAME = "config.yaml"

    def __init__(self):
        self.config_dir = Path.home() / ".podcli"
        self.config_file = self.config_dir / self.CONFIG_FILENAME

        self.config = self._load_config()

        self.whisper = WhisperConfig(**self.config.get("whisper", {}))
        self.download = DownloadConfig(**self.config.get("download", {}))
        self.output = OutputConfig(**self.config.get("output", {}))
        self.search = SearchConfig(**self.config.get("search", {}))
        self.openai = OpenAIConfig(**self.config.get("openai", {}))
        self.structured = StructuredMarkdownConfig(**self.config.get("structured", {}))
        self.workflow = WorkflowConfig(**self.config.get("workflow", {}))
        self.debug = self.config.get("debug", False)

        self.output.dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> dict[str, Any]:
        """加载配置文件，支持YAML格式"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        default_config = self._get_default_config()

        if not self.config_file.exists():
            self._save_config(default_config)
            return default_config

        try:
            with open(self.config_file, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}

            # 合并配置：默认配置 + 用户配置
            merged_config = self._merge_configs(default_config, user_config)

            # 如果有新字段，自动保存回配置文件
            if merged_config != user_config:
                self._save_config(merged_config)

            return merged_config
        except Exception as e:
            print(f"配置文件读取失败: {e}")
            return default_config

    def _get_default_config(self) -> dict[str, Any]:
        """获取默认配置"""
        return {
            "whisper": {
                "model": "base",
                "device": "cpu",
                "language": "auto",
                "compute_type": "float16",
                "batch_size": 16,
                "enable_alignment": True,
                "align_model": "",
                "diarize": False,
                "hf_token": "",
                "min_speakers": None,
                "max_speakers": None,
            },
            "download": {
                "max_retries": 3,
                "retry_delay": 5.0,
                "chunk_size": 8192,
                "timeout": 60,
                "resume_download": True,
                "max_concurrent": 3,
            },
            "output": {
                "dir": str(Path.home() / "Podcasts"),
                "save_audio": True,
                "md_filename_template": "{title}.md",
                "include_timestamps": True,
            },
            "search": {"max_results": 50, "country": "US", "language": "en_us"},
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",
                "max_tokens": 8192,
                "temperature": 0.1,
                "request_timeout": 120,
            },
            "structured": {
                "enable": True,
                "segment_length": 6000,
                "preserve_original": True,
                "auto_detect_domain": True,
            },
            "workflow": {
                "auto_download": True,
                "auto_transcribe": True,
                "auto_structure": True,
                "save_intermediate": True,
            },
            "debug": False,
        }

    def _merge_configs(self, default: dict, user: dict) -> dict:
        """递归合并配置"""
        if not isinstance(user, dict):
            return default

        merged = default.copy()
        for key, value in user.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value

        return merged

    def _save_config(self, config: dict) -> None:
        """保存配置文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
        except Exception as e:
            print(f"配置文件保存失败: {e}")

    def update(self, section: str, key: str, value: Any) -> bool:
        """更新配置项

        Args:
            section: 配置章节 (whisper/download/output/search)
            key: 配置键
            value: 配置值

        Returns:
            bool: 更新是否成功
        """
        if section not in self.config:
            self.config[section] = {}

        self.config[section][key] = value
        self._save_config(self.config)

        self.__init__()
        return True

    def get_config_path(self) -> str:
        """获取配置文件路径"""
        return str(self.config_file)

    def validate(self) -> tuple[bool, list[str]]:
        """验证配置

        Returns:
            tuple: (是否有效, 错误列表)
        """
        errors = []

        try:
            WhisperConfig(**self.config.get("whisper", {}))
        except Exception as e:
            errors.append(f"Whisper配置错误: {e}")

        try:
            DownloadConfig(**self.config.get("download", {}))
        except Exception as e:
            errors.append(f"下载配置错误: {e}")

        try:
            OutputConfig(**self.config.get("output", {}))
        except Exception as e:
            errors.append(f"输出配置错误: {e}")

        return len(errors) == 0, errors


config = Config()
