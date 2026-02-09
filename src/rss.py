#!/usr/bin/env python3
"""
RSS解析模块
"""

import requests
import xml.etree.ElementTree as ET

class RSSParser:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5
    
    def get_podcast_feed(self, feed_url):
        """获取播客源"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    feed_url,
                    headers={
                        "User-Agent": "PodcastProcessor/1.0",
                        "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    },
                    timeout=30,
                )
                response.raise_for_status()

                return {
                    "feed_url": feed_url,
                    "content": response.text,
                    "status": "success",
                }

            except requests.exceptions.RequestException as e:
                print(f"获取播客源失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"获取播客源失败: {e}")

        return {"status": "error", "message": "Failed after retries"}
    
    def get_episodes(self, feed_url):
        """解析播客剧集"""
        feed_data = self.get_podcast_feed(feed_url)
        if feed_data.get("status") != "success":
            print("无法获取播客源内容")
            return []

        try:
            root = ET.fromstring(feed_data["content"])
            channel = root.find("channel")
            if channel is None:
                print("无法找到RSS频道元素")
                return []

            episodes = []
            episode_count = 0

            for item in channel.findall("item"):
                enclosure = item.find("enclosure")
                if enclosure is None or not enclosure.get("type", "").startswith("audio/"):
                    continue

                artwork = item.find("itunes:image")
                artwork_url = artwork.get("href") if artwork is not None else ""

                episode = {
                    "title": item.find("title").text if item.find("title") is not None else "Unknown",
                    "description": (
                        item.find("description").text
                        if item.find("description") is not None
                        else (
                            item.find("itunes:summary").text
                            if item.find("itunes:summary") is not None
                            else ""
                        )
                    ),
                    "pubDate": item.find("pubDate").text if item.find("pubDate") is not None else "",
                    "enclosure": {
                        "url": enclosure.get("url", ""),
                        "type": enclosure.get("type", ""),
                        "length": enclosure.get("length", "0"),
                    },
                    "artworkUrl": artwork_url,
                    "guid": item.find("guid").text if item.find("guid") is not None else "",
                    "episodeNumber": (
                        int(item.find("itunes:episode").text)
                        if item.find("itunes:episode") is not None
                        else episode_count + 1
                    ),
                }
                episodes.append(episode)
                episode_count += 1

            return episodes

        except ET.ParseError as e:
            print(f"XML解析错误: {e}")
            return []
    
    def get_podcast_title(self, feed_url):
        """获取播客标题"""
        feed_data = self.get_podcast_feed(feed_url)
        if feed_data.get("status") != "success":
            return None

        try:
            root = ET.fromstring(feed_data["content"])
            channel = root.find("channel")
            if channel is None:
                return None

            title = channel.find("title")
            return title.text if title is not None else None

        except Exception as e:
            print(f"获取播客标题失败: {e}")
            return None
