#!/usr/bin/env python3
"""
Markdown生成器模块
"""

import os
from pathlib import Path
from datetime import datetime

class MarkdownGenerator:
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else Path.home() / "Podcasts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, result, title, podcast, audio_source):
        """生成Markdown文件"""
        try:
            # 生成文件名
            safe_title = self.sanitize_filename(title)
            md_filename = f"{safe_title}.md"
            md_filepath = self.output_dir / md_filename
            
            # 格式化日期
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 格式化时长
            duration_str = ""  
            if result.duration:
                hours = int(result.duration // 3600)
                minutes = int((result.duration % 3600) // 60)
                seconds = int(result.duration % 60)
                if hours > 0:
                    duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes:02d}:{seconds:02d}"
            
            # 生成Markdown内容
            md_content = f"""---
title: "{title}"
podcast: "{podcast}"
date: {current_date}
duration: "{duration_str}"
source: `{audio_source}`
audio: {Path(result.audio_file).name}
---

# {title}

## 章节

- [00:00:00] 开场介绍

## 转录文本

**[00:00:00]** {result.transcript}
"""
            
            # 写入文件
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            
            print(f"Markdown文件生成完成: {md_filepath}")
            return md_filepath
            
        except Exception as e:
            print(f"生成Markdown文件失败: {e}")
            return None
    
    def sanitize_filename(self, filename):
        """清理文件名"""
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, "_")
        filename = filename.strip()
        if not filename:
            filename = "unnamed"
        # 限制文件名长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename
    
    def generate_with_timestamps(self, result, title, podcast, audio_source):
        """生成带时间戳的Markdown文件"""
        try:
            # 生成文件名
            safe_title = self.sanitize_filename(title)
            md_filename = f"{safe_title}_with_timestamps.md"
            md_filepath = self.output_dir / md_filename
            
            # 格式化日期
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 格式化时长
            duration_str = ""  
            if result.duration:
                hours = int(result.duration // 3600)
                minutes = int((result.duration % 3600) // 60)
                seconds = int(result.duration % 60)
                if hours > 0:
                    duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes:02d}:{seconds:02d}"
            
            # 生成Markdown内容
            md_content = f"""---
title: "{title}"
podcast: "{podcast}"
date: {current_date}
duration: "{duration_str}"
source: `{audio_source}`
audio: {Path(result.audio_file).name}
---

# {title}

## 章节

- [00:00:00] 开场介绍

## 转录文本（带时间戳）

**[00:00:00]** {result.transcript}
"""
            
            # 写入文件
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            
            print(f"带时间戳的Markdown文件生成完成: {md_filepath}")
            return md_filepath
            
        except Exception as e:
            print(f"生成带时间戳的Markdown文件失败: {e}")
            return None
