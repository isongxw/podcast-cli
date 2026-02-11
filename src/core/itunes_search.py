#!/usr/bin/env python3
"""
iTunes搜索模块

支持并行搜索和类型安全的播客搜索
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from pydantic import BaseModel


class PodcastResult(BaseModel):
    """播客搜索结果"""

    collection_id: int
    collection_name: str
    artist_name: str
    artwork_url: str
    feed_url: str
    primary_genre_name: str
    release_date: str
    track_count: int
    collection_view_url: str


class iTunesSearch:
    """iTunes播客搜索"""

    BASE_URL = "https://itunes.apple.com/search"

    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0, timeout: int = 30):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    def search_podcasts(
        self,
        query: str,
        limit: int = 50,
        genre_id: int | None = None,
        artist_name: str | None = None,
        country: str = "US",
        lang: str = "en_us",
    ) -> list[PodcastResult]:
        """搜索播客

        Args:
            query: 搜索关键词
            limit: 结果数量限制
            genre_id: 流派ID
            artist_name: 艺术家名称过滤
            country: 国家代码
            lang: 语言

        Returns:
            list[PodcastResult]: 播客列表
        """
        params = {
            "term": query,
            "limit": min(limit, 200),
            "country": country,
            "lang": lang,
            "media": "podcast",
            "entity": "podcast",
        }

        if genre_id:
            params["genreId"] = genre_id

        if artist_name:
            params["attribute"] = "artistTerm"

        for attempt in range(self.max_retries):
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])

                podcasts = []
                for item in results:
                    if item.get("kind") == "podcast":
                        podcast = PodcastResult(
                            collection_id=item.get("collectionId", 0),
                            collection_name=item.get("collectionName", ""),
                            artist_name=item.get("artistName", ""),
                            artwork_url=item.get("artworkUrl600", item.get("artworkUrl100", "")),
                            feed_url=item.get("feedUrl", ""),
                            primary_genre_name=item.get("primaryGenreName", ""),
                            release_date=item.get("releaseDate", ""),
                            track_count=item.get("trackCount", 0),
                            collection_view_url=item.get("collectionViewUrl", ""),
                        )
                        podcasts.append(podcast)

                return podcasts

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    import time

                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"搜索请求失败: {e}")

        return []

    def search_multiple(self, queries: list[str], limit: int = 10, max_workers: int = 3) -> dict[str, list[PodcastResult]]:
        """并行搜索多个关键词

        Args:
            queries: 搜索关键词列表
            limit: 每个关键词的结果数量
            max_workers: 最大并发数

        Returns:
            dict: 关键词到播客列表的映射
        """
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_query = {executor.submit(self.search_podcasts, query, limit): query for query in queries}

            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    results[query] = future.result()
                except Exception as e:
                    print(f"搜索 '{query}' 失败: {e}")
                    results[query] = []

        return results

    def get_podcast_by_id(self, collection_id: int, country: str = "US") -> PodcastResult | None:
        """通过ID获取播客

        Args:
            collection_id: 播客ID
            country: 国家代码

        Returns:
            Optional[PodcastResult]: 播客信息
        """
        params = {
            "id": collection_id,
            "country": country,
            "media": "podcast",
            "entity": "podcast",
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if results:
                item = results[0]
                return PodcastResult(
                    collection_id=item.get("collectionId", 0),
                    collection_name=item.get("collectionName", ""),
                    artist_name=item.get("artistName", ""),
                    artwork_url=item.get("artworkUrl600", item.get("artworkUrl100", "")),
                    feed_url=item.get("feedUrl", ""),
                    primary_genre_name=item.get("primaryGenreName", ""),
                    release_date=item.get("releaseDate", ""),
                    track_count=item.get("trackCount", 0),
                    collection_view_url=item.get("collectionViewUrl", ""),
                )

        except Exception as e:
            print(f"获取播客失败: {e}")

        return None
