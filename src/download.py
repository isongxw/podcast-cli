#!/usr/bin/env python3
"""
音频下载模块
"""

import os
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
from rich.console import Console
from rich.progress import Progress

# 创建控制台实例
console = Console()

class AudioDownloader:
    def __init__(self, download_dir=None):
        self.download_dir = Path(download_dir) if download_dir else Path.home() / "Podcasts"
        self.temp_dir = Path("temp")
        self.chunk_size = 8192
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def sanitize_filename(self, filename):
        """清理文件名"""
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, "_")
        filename = filename.strip()
        if not filename:
            filename = "unnamed"
        return filename
    
    def get_extension_from_url(self, url):
        """从URL获取文件扩展名"""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        audio_formats = [".mp3", ".m4a", ".m4b", ".aac", ".wav", ".ogg"]
        for fmt in audio_formats:
            if path.lower().endswith(fmt):
                return fmt
        return ".mp3"
    
    def generate_safe_filename(self, url):
        """生成安全的文件名"""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = Path(path).name
        if not filename:
            filename = "unnamed"
        safe_filename = self.sanitize_filename(filename)
        if not safe_filename.endswith(tuple([".mp3", ".m4a", ".m4b", ".aac", ".wav", ".ogg"])):
            ext = self.get_extension_from_url(url)
            safe_filename += ext
        return safe_filename
    
    def download_audio(self, url):
        """下载音频文件"""
        try:
            # 生成文件名
            filename = self.generate_safe_filename(url)
            filepath = self.download_dir / filename
            
            # 检查文件是否已存在
            if filepath.exists():
                console.print(f"[yellow]文件已存在: {filepath}[/yellow]")
                return filepath
            
            # 发送请求
            headers = {
                "User-Agent": "PodcastProcessor/1.0",
                "Accept-Encoding": "identity",
            }
            
            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=60,
                allow_redirects=True,
            )
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get("content-length", 0))
            
            # 使用rich的进度条下载文件
            console.print(f"[cyan]下载中: {filename}[/cyan]")
            with Progress(
                console=console,
                refresh_per_second=4,
                disable=False
            ) as progress:
                task = progress.add_task(f"[cyan]下载 {filename}[/cyan]", total=total_size)
                
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))
            
            console.print(f"[green]下载完成: {filepath}[/green]")
            return filepath
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]下载失败: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]下载过程中发生错误: {e}[/red]")
            return None
    
    def cleanup(self, filepath):
        """清理临时文件"""
        try:
            if filepath.exists():
                filepath.unlink()
                console.print(f"[yellow]已清理文件: {filepath}[/yellow]")
        except Exception as e:
            console.print(f"[red]清理文件失败: {e}[/red]")
    
    def cleanup_temp_files(self):
        """清理所有临时文件"""
        if self.temp_dir.exists():
            for file in self.temp_dir.glob("*"):
                try:
                    if file.is_file():
                        file.unlink()
                except Exception as e:
                    console.print(f"[red]清理临时文件失败: {e}[/red]")
