#!/usr/bin/env python3
"""
RSS解析模块

改进的错误处理和类型安全
"""

import xml.etree.ElementTree as ET

import requests
from pydantic import BaseModel, Field
from rich.console import Console

from utils import retry

console = Console()


class Episode(BaseModel):
    """单集数据类"""

    title: str = ""
    description: str = ""
    pub_date: str = ""
    audio_url: str = ""
    audio_type: str = ""
    audio_length: str = ""
    artwork_url: str = ""
    guid: str = ""
    episode_number: int = 0

    @classmethod
    def from_element(cls, item, episode_count: int) -> "Episode":
        """从XML元素创建Episode实例"""
        enclosure = item.find("enclosure")

        def safe_text(element, tag):
            """安全获取文本，处理None情况"""
            el = element.find(tag)
            return el.text if el is not None else ""

        def safe_int(element, tag, default: int) -> int:
            """安全获取整数"""
            el = element.find(tag)
            if el is not None and el.text:
                try:
                    return int(el.text)
                except (ValueError, TypeError):
                    return default
            return default

        artwork = item.find("itunes:image")
        artwork_url = artwork.get("href") if artwork is not None else ""
        return cls(
            title=safe_text(item, "title") or "Unknown",
            description=safe_text(item, "description")
            or safe_text(item, "itunes:summary")
            or "",
            pub_date=safe_text(item, "pubDate") or "",
            audio_url=enclosure.get("url") if enclosure is not None else "",
            audio_type=enclosure.get("type") if enclosure is not None else "audio/mpeg",
            audio_length=enclosure.get("length") if enclosure is not None else "0",
            artwork_url=artwork_url,
            guid=safe_text(item, "guid") or "",
            episode_number=safe_int(item, "itunes:episode", episode_count + 1),
        )


class Podcast(BaseModel):
    """播客数据类"""

    feed_url: str
    title: str
    description: str
    artwork_url: str
    author: str
    episodes: list[Episode] = Field(default_factory=list)

    @classmethod
    def from_feed(cls, feed_url: str, content: str) -> "Podcast":
        """从RSS内容创建Podcast实例"""
        root = ET.fromstring(content)
        channel = root.find("channel")

        if channel is None:
            raise ValueError("无法找到RSS频道元素")

        def safe_text(element, tag):
            el = element.find(tag)
            return el.text if el is not None else ""

        podcast = cls(
            feed_url=feed_url,
            title=safe_text(channel, "title") or "Unknown Podcast",
            description=safe_text(channel, "description")
            or safe_text(channel, "itunes:summary")
            or "",
            artwork_url="",
            author=safe_text(channel, "itunes:author")
            or safe_text(channel, "author")
            or "",
        )

        artwork = channel.find("itunes:image")
        if artwork is not None:
            podcast.artwork_url = artwork.get("href") or ""

        episodes = []
        episode_count = 0
        for item in channel.findall("item"):
            enclosure = item.find("enclosure")
            if enclosure is None or not enclosure.get("type", "").startswith("audio/"):
                continue

            episode = Episode.from_element(item, episode_count)
            episodes.append(episode)
            episode_count += 1

        podcast.episodes = episodes
        return podcast


class RSSParser:
    """RSS解析器"""

    def __init__(
        self, max_retries: int = 3, retry_delay: float = 5.0, timeout: int = 30
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    @retry(max_retries=3, delay=5.0)
    def fetch_feed(self, feed_url: str) -> dict:
        """获取播客源内容"""
        response = requests.get(
            feed_url,
            headers={
                "User-Agent": "PodcastProcessor/1.0",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        return {"feed_url": feed_url, "content": response.text, "status": "success"}

    def get_episodes(self, feed_url: str) -> list[Episode]:
        """获取播客单集列表"""
        feed_data = self.fetch_feed(feed_url)

        if feed_data.get("status") != "success":
            console.print("[yellow]无法获取播客源内容[/yellow]")
            return []

        try:
            podcast = Podcast.from_feed(feed_url, feed_data["content"])
            return podcast.episodes
        except ET.ParseError as e:
            console.print(f"[red]XML解析错误: {e}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]解析播客源失败: {e}[/red]")
            return []

    def get_podcast(self, feed_url: str) -> Podcast | None:
        """获取完整播客信息"""
        feed_data = self.fetch_feed(feed_url)

        if feed_data.get("status") != "success":
            console.print("[yellow]无法获取播客源内容[/yellow]")
            return None

        try:
            return Podcast.from_feed(feed_url, feed_data["content"])
        except Exception as e:
            console.print(f"[red]解析播客源失败: {e}[/red]")
            return None

    def get_podcast_title(self, feed_url: str) -> str | None:
        """获取播客标题"""
        podcast = self.get_podcast(feed_url)
        return podcast.title if podcast else None


class RSSValidator:
    """RSS源验证器"""

    VALID_AUDIO_TYPES = {
        "audio/mpeg",
        "audio/mp3",
        "audio/x-m4a",
        "audio/m4a",
        "audio/x-m4b",
        "audio/m4b",
        "audio/aac",
        "audio/wav",
        "audio/ogg",
        "audio/flac",
    }

    @staticmethod
    def is_valid_feed_url(url: str) -> bool:
        """验证是否为有效的RSS URL"""
        if not url.startswith(("http://", "https://")):
            return False

        try:
            response = requests.head(url, timeout=10)
            content_type = response.headers.get("Content-Type", "")
            return "xml" in content_type or "rss" in content_type
        except Exception:
            return False

    @staticmethod
    def is_audio_enclosure(enclosure) -> bool:
        """检查是否为有效的音频enclosure"""
        if enclosure is None:
            return False
        audio_type = enclosure.get("type", "")
        return audio_type.startswith("audio/")
