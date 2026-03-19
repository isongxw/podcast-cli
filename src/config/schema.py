#!/usr/bin/env python3
"""
配置类型定义模块
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class WhisperConfig(BaseModel):
    """WhisperX转录配置"""

    model: Literal["tiny", "base", "small", "medium", "large", "large-v1", "large-v2", "large-v3"] = "base"
    device: Literal["cpu", "cuda"] = "cpu"
    language: str = "auto"
    compute_type: Literal["int8", "float16", "float16"] = "float16"
    batch_size: int = Field(default=16, ge=1, le=64, description="WhisperX批处理大小")
    enable_alignment: bool = Field(default=True, description="是否启用词级时间戳对齐")
    align_model: str = Field(default="", description="强制使用指定对齐模型（空字符串表示自动选择）")
    diarize: bool = Field(default=False, description="是否启用说话人分离")
    hf_token: str = Field(default="", description="HuggingFace Token（用于说话人分离）")
    min_speakers: int | None = Field(default=None, ge=1, le=10, description="最小说话人数（可选）")
    max_speakers: int | None = Field(default=None, ge=1, le=10, description="最大说话人数（可选）")


class DownloadConfig(BaseModel):
    """下载配置"""

    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=5.0, ge=1.0, le=60.0)
    chunk_size: int = Field(default=8192, ge=1024, le=65536)
    timeout: int = Field(default=60, ge=10, le=300)
    resume_download: bool = Field(default=True, description="启用断点续传")
    max_concurrent: int = Field(default=3, ge=1, le=10, description="批量下载并发数")


class OutputConfig(BaseModel):
    """输出配置"""

    dir: Path = Field(default=Path.home() / "Podcasts")
    save_audio: bool = True
    md_filename_template: str = Field(default="{title}.md", description="Markdown文件名模板")
    include_timestamps: bool = True


class SearchConfig(BaseModel):
    """搜索配置"""

    max_results: int = Field(default=50, ge=1, le=200)
    country: str = Field(default="US")
    language: str = Field(default="en_us")


class OpenAIConfig(BaseModel):
    """OpenAI LLM配置"""

    base_url: str = Field(default="https://api.openai.com/v1", description="API基础URL")
    api_key: str = Field(default="", description="API密钥")
    model: str = Field(default="gpt-4o", description="使用的模型名称")
    max_tokens: int = Field(default=8192, ge=1000, le=32000, description="最大输出token数")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="生成温度")
    request_timeout: int = Field(default=120, ge=10, le=600, description="请求超时时间(秒)")


class StructuredMarkdownConfig(BaseModel):
    """结构化Markdown生成配置"""

    enable: bool = Field(default=True, description="是否启用LLM结构化")
    segment_length: int = Field(default=6000, ge=1000, description="长文本分段处理每段长度")
    preserve_original: bool = Field(default=True, description="是否保留原始转录文本")
    auto_detect_domain: bool = Field(default=True, description="是否自动检测播客内容领域")


class WorkflowConfig(BaseModel):
    """工作流配置"""

    auto_download: bool = Field(default=True, description="自动下载音频")
    auto_transcribe: bool = Field(default=True, description="自动转录音频")
    auto_structure: bool = Field(default=True, description="自动LLM结构化")
    save_intermediate: bool = Field(default=True, description="保存中间结果")


class PodcliConfig(BaseModel):
    """主配置类"""

    whisper: WhisperConfig = Field(default_factory=WhisperConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    structured: StructuredMarkdownConfig = Field(default_factory=StructuredMarkdownConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    debug: bool = Field(default=False)
