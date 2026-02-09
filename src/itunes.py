#!/usr/bin/env python3
"""
iTunes搜索模块
"""

import requests
from urllib.parse import urlencode

class iTunesSearch:
    def __init__(self):
        self.base_url = "https://itunes.apple.com/search"
        self.default_params = {
            "media": "podcast",
            "entity": "podcast",
            "limit": 50,
        }
        self.max_retries = 3
        self.retry_delay = 5
    
    def search_podcasts(
        self,
        query,
        limit=50,
        genre_id=None,
        artist_name=None,
        country="US",
        lang="en_us",
    ):
        """搜索播客"""
        params = {
            "term": query,
            "limit": min(limit, 200),
            "country": country,
            "lang": lang,
        }

        if genre_id:
            params["genreId"] = genre_id

        if artist_name:
            params["attribute"] = "artistTerm"

        params.update(self.default_params)

        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])

                podcasts = []
                for item in results:
                    if item.get("kind") == "podcast":
                        podcast = {
                            "collectionId": item.get("collectionId", 0),
                            "collectionName": item.get("collectionName", ""),
                            "artistName": item.get("artistName", ""),
                            "artworkUrl": item.get("artworkUrl600", item.get("artworkUrl100", "")),
                            "feedUrl": item.get("feedUrl", ""),
                            "primaryGenreName": item.get("primaryGenreName", ""),
                            "releaseDate": item.get("releaseDate", ""),
                            "trackCount": item.get("trackCount", 0),
                            "collectionViewUrl": item.get("collectionViewUrl", ""),
                        }
                        podcasts.append(podcast)

                return podcasts

            except requests.exceptions.RequestException as e:
                print(f"搜索请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"搜索请求失败: {e}")

        return []
