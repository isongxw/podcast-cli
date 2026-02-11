#!/usr/bin/env python3
"""
工具函数模块

提供通用的工具函数：文件处理、装饰器、并行处理等
"""

import os
import re
import hashlib
import time
import logging
from pathlib import Path
from functools import wraps, lru_cache
from typing import Callable, TypeVar, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console

console = Console()

T = TypeVar("T")


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """清理文件名，移除非法字符

    Args:
        filename: 原始文件名
        max_length: 最大长度限制

    Returns:
        str: 清理后的文件名
    """
    illegal_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]
    for char in illegal_chars:
        filename = filename.replace(char, "_")
    filename = filename.strip()
    if not filename:
        filename = "unnamed"
    if len(filename) > max_length:
        filename = filename[:max_length]
    return filename


def get_file_extension(url: str, audio_formats: list[str] = None) -> str:
    """从URL获取文件扩展名

    Args:
        url: 文件URL
        audio_formats: 支持的音频格式列表

    Returns:
        str: 文件扩展名
    """
    from urllib.parse import urlparse, unquote

    if audio_formats is None:
        audio_formats = [
            ".mp3",
            ".m4a",
            ".m4b",
            ".aac",
            ".wav",
            ".ogg",
            ".flac",
            ".wma",
        ]

    parsed = urlparse(url)
    path = unquote(parsed.path)

    for fmt in audio_formats:
        if path.lower().endswith(fmt):
            return fmt
    return ".mp3"


def calculate_file_hash(filepath: Path, algorithm: str = "sha256") -> str:
    """计算文件哈希值

    Args:
        filepath: 文件路径
        algorithm: 哈希算法 (sha256/sha1/md5)

    Returns:
        str: 文件哈希值
    """
    hash_func = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def format_duration(seconds: float | None) -> str:
    """格式化时长

    Args:
        seconds: 秒数，可为None

    Returns:
        str: 格式化后的时长字符串 (HH:MM:SS)
    """
    if seconds is None or seconds <= 0:
        return "Unknown"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def retry(
    max_retries: int = 3,
    delay: float = 5.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟增长倍数
        exceptions: 需要捕获的异常类型

    Returns:
        Callable: 装饰器函数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        console.print(
                            f"[yellow]尝试 {attempt + 1}/{max_retries + 1} 失败，"
                            f"{current_delay:.1f}秒后重试: {e}[/yellow]"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        console.print(f"[red]重试次数耗尽: {e}[/red]")
                        raise

            raise last_exception

        return wrapper

    return decorator


class ProgressTracker:
    """进度追踪器"""

    def __init__(self, description: str = "处理中"):
        self.start_time = None
        self.total_items = 0
        self.completed_items = 0
        self.description = description

    def start(self, total: int):
        """开始进度追踪"""
        self.start_time = time.time()
        self.total_items = total
        self.completed_items = 0

    def update(self, advance: int = 1):
        """更新进度"""
        self.completed_items += advance
        elapsed = time.time() - self.start_time
        if self.completed_items > 0 and self.total_items > 0:
            eta = (elapsed / self.completed_items) * (
                self.total_items - self.completed_items
            )
            percent = (self.completed_items / self.total_items) * 100
            return f"{self.description} | {percent:.1f}% | 已完成 {self.completed_items}/{self.total_items} | 预计剩余: {format_duration(eta)}"
        return self.description

    def summary(self) -> str:
        """获取完成总结"""
        elapsed = time.time() - self.start_time
        return f"{self.description} 完成！总耗时: {format_duration(elapsed)}"


def parallel_map(
    func: Callable[..., T],
    items: list[Any],
    max_workers: int = 3,
    description: str = "并行处理",
) -> list[T]:
    """并行处理列表

    Args:
        func: 处理函数
        items: 处理项列表
        max_workers: 最大并发数
        description: 进度描述

    Returns:
        list[T]: 处理结果列表
    """
    results = []
    tracker = ProgressTracker(description)
    tracker.start(len(items))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(func, item): item for item in items}

        for future in as_completed(future_to_item):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                console.print(f"[red]处理失败: {e}[/red]")

            console.print(f"[cyan]{tracker.update()}[/cyan]")

    console.print(f"[green]{tracker.summary()}[/green]")
    return results


@lru_cache(maxsize=128)
def cached_download(url: str) -> str:
    """缓存下载URL的响应（用于避免重复下载）

    Args:
        url: 下载URL

    Returns:
        str: 缓存键
    """
    return hashlib.md5(url.encode()).hexdigest()


def setup_logging(debug: bool = False):
    """设置日志配置

    Args:
        debug: 是否开启调试模式
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
