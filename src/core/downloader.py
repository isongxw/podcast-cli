#!/usr/bin/env python3
"""
音频下载模块

支持断点续传、批量下载、进度显示
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.text import Text

from utils import get_file_extension, sanitize_filename

console = Console()


class DownloadState(BaseModel):
    """下载状态"""

    url: str
    filepath: Path
    downloaded_bytes: int = 0
    total_bytes: int = 0
    status: str = "pending"
    last_error: str = ""
    timestamp: float = Field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "filepath": str(self.filepath),
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "status": self.status,
            "last_error": self.last_error,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadState":
        return cls(
            url=data["url"],
            filepath=Path(data["filepath"]),
            downloaded_bytes=data.get("downloaded_bytes", 0),
            total_bytes=data.get("total_bytes", 0),
            status=data.get("status", "pending"),
            last_error=data.get("last_error", ""),
            timestamp=data.get("timestamp", time.time()),
        )


class DownloadManager:
    """下载管理器，支持断点续传和批量下载"""

    def __init__(
        self,
        download_dir: Path | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        chunk_size: int = 8192,
        timeout: int = 60,
        resume_enabled: bool = True,
        max_concurrent: int = 3,
    ):
        self.download_dir = download_dir or Path.home() / "Podcasts"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.resume_enabled = resume_enabled
        self.max_concurrent = max_concurrent

        self.state_file = self.download_dir / ".download_states.json"
        self.states: dict[str, DownloadState] = {}

        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._load_states()

    def _load_states(self):
        """加载下载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    self.states = {k: DownloadState.from_dict(v) for k, v in data.items()}
            except Exception as e:
                console.print(f"[yellow]加载下载状态失败: {e}[/yellow]")
                self.states = {}

    def _save_states(self):
        """保存下载状态"""
        try:
            data = {k: v.to_dict() for k, v in self.states.items()}
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]保存下载状态失败: {e}[/yellow]")

    def _get_state(self, url: str) -> DownloadState | None:
        """获取下载状态"""
        return self.states.get(url)

    def _update_state(self, state: DownloadState):
        """更新下载状态"""
        self.states[state.url] = state
        self._save_states()

    def _cleanup_state(self, url: str):
        """清理下载状态"""
        if url in self.states:
            del self.states[url]
            self._save_states()

    def _generate_filename(self, url: str, title: str | None = None) -> Path:
        """生成文件名"""
        parsed = urlparse(url)
        path = unquote(parsed.path)

        if title:
            filename = sanitize_filename(title)
        else:
            filename = Path(path).name or "unnamed"

        filename = sanitize_filename(filename)
        ext = get_file_extension(url)

        if not filename.endswith(ext):
            filename += ext

        return self.download_dir / filename

    def download(
        self,
        url: str,
        title: str | None = None,
        progress_callback: Callable | None = None,
    ) -> Path | None:
        """下载单个文件，支持断点续传"""
        filepath = self._generate_filename(url, title)
        state = self._get_state(url)

        if state and state.status == "completed" and filepath.exists():
            console.print(f"[green]文件已存在: {filepath}[/green]")
            return filepath

        headers = {
            "User-Agent": "PodcastProcessor/1.0",
            "Accept-Encoding": "identity",
        }

        if self.resume_enabled and state and state.downloaded_bytes > 0:
            headers["Range"] = f"bytes={state.downloaded_bytes}-"
            console.print(f"[cyan]断点续传，从 {state.downloaded_bytes} 字节开始[/cyan]")

        state = DownloadState(url=url, filepath=filepath, status="downloading")
        self._update_state(state)

        try:
            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=self.timeout,
                allow_redirects=True,
            )

            if response.status_code in (200, 206):
                if response.status_code == 206:
                    state.downloaded_bytes = int(response.headers.get("Content-Range", "").split("/")[-1]) or 0
                else:
                    state.downloaded_bytes = 0

                state.total_bytes = int(response.headers.get("Content-Length", 0))
                self._update_state(state)

                self._write_file(response, filepath, state, progress_callback)

                state.status = "completed"
                self._update_state(state)
                self._cleanup_state(url)

                return filepath
            else:
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}")

        except Exception as e:
            state.status = "failed"
            state.last_error = str(e)
            self._update_state(state)

            if self.max_retries > 0:
                return self._retry_download(url, title, progress_callback)

            console.print(f"[red]下载失败: {e}[/red]")
            return None

    def _write_file(
        self,
        response: requests.Response,
        filepath: Path,
        state: DownloadState,
        progress_callback: Callable | None = None,
    ):
        """写入文件"""
        mode = "ab" if state.downloaded_bytes > 0 else "wb"

        # console.print(
        #     f"[cyan]下载中: {filepath.name} ({format_duration(state.total_bytes / 1000000 * 8 if state.total_bytes > 0 else 0)})[/cyan]"
        # )

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]下载 {filepath.name}[/cyan]", total=state.total_bytes or None)

            with open(filepath, mode) as f:
                downloaded = state.downloaded_bytes
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, advance=len(chunk))

                        if progress_callback:
                            progress_callback(downloaded, state.total_bytes)

    def _retry_download(
        self,
        url: str,
        title: str | None = None,
        progress_callback: Callable | None = None,
    ) -> Path | None:
        """重试下载"""
        state = self._get_state(url)
        if state and state.downloaded_bytes > 0:
            if state.downloaded_bytes > 0:
                console.print(f"[yellow]尝试重新下载 (保留已下载的 {state.downloaded_bytes} 字节)[/yellow]")
            else:
                console.print(f"[yellow]重试下载: {url}[/yellow]")

        state = self._get_state(url)
        if state:
            state.status = "pending"
            state.downloaded_bytes = 0
            self._update_state(state)

        for attempt in range(self.max_retries):
            console.print(f"[cyan]重试 {attempt + 1}/{self.max_retries}[/cyan]")
            time.sleep(self.retry_delay * (attempt + 1))

            result = self.download(url, title, progress_callback)
            if result:
                return result

        console.print(f"[red]下载失败，已重试 {self.max_retries} 次[/red]")
        return None

    def download_batch(self, items: list[dict], progress_callback: Callable | None = None) -> list[Path]:
        """批量下载"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        console.print(
            Panel(
                Text(f"开始批量下载 {len(items)} 个文件", style="bold cyan"),
                border_style="green",
            )
        )

        results = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {executor.submit(self.download, item["url"], item.get("title")): item for item in items}

            for future in as_completed(futures):
                completed += 1
                result = future.result()

                if result:
                    results.append(result)
                    console.print(f"[green][{completed}/{len(items)}] 完成: {result.name}[/green]")
                else:
                    item = futures[future]
                    console.print(f"[red][{completed}/{len(items)}] 失败: {item.get('title', item['url'])}[/red]")

        console.print(f"[green]批量下载完成: {len(results)}/{len(items)} 成功[/green]")
        return results

    def cleanup(self, filepath: Path):
        """清理文件"""
        try:
            if filepath.exists():
                filepath.unlink()
                console.print(f"[yellow]已清理: {filepath}[/yellow]")
        except Exception as e:
            console.print(f"[red]清理文件失败: {e}[/red]")

    def cleanup_temp_files(self):
        """清理所有临时文件"""
        temp_files = list(self.download_dir.glob("*.part"))
        for f in temp_files:
            try:
                f.unlink()
                console.print(f"[yellow]清理临时文件: {f}[/yellow]")
            except Exception as e:
                console.print(f"[red]清理失败: {e}[/red]")


def download_audio(
    url: str,
    title: str | None = None,
    output_dir: Path | None = None,
    resume: bool = True,
) -> Path | None:
    """便捷的音频下载函数

    Args:
        url: 音频URL
        title: 标题
        output_dir: 输出目录
        resume: 是否启用断点续传

    Returns:
        Optional[Path]: 下载的文件路径
    """
    from config import config

    downloader = DownloadManager(
        download_dir=output_dir or config.output.dir,
        max_retries=config.download.max_retries,
        retry_delay=config.download.retry_delay,
        chunk_size=config.download.chunk_size,
        timeout=config.download.timeout,
        resume_enabled=resume,
    )

    return downloader.download(url, title)
