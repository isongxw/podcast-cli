#!/usr/bin/env python3
"""
Markdown生成器模块

支持模板配置、时间戳、发言人标注
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
from string import Template

from utils import sanitize_filename, format_duration
from .transcriber import TranscriptionResult


class MarkdownGenerator:
    """Markdown文件生成器"""

    DEFAULT_TEMPLATE = """---
title: "$title"
podcast: "$podcast"
date: $date
duration: "$duration"
source: `$audio_source`
audio: $audio_filename
---

# $title

## 基本信息

- **播客**: $podcast
- **日期**: $date
- **时长**: $duration
- **语言**: $language

## 章节

$chapters

## 转录文本

$transcript

---
*由 podcli 生成*
"""

    def __init__(
        self, output_dir: Optional[Path] = None, template: Optional[str] = None
    ):
        self.output_dir = Path(output_dir) if output_dir else Path.home() / "Podcasts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template = (
            Template(template) if template else Template(self.DEFAULT_TEMPLATE)
        )

    def generate(
        self,
        result: TranscriptionResult,
        title: str,
        podcast: str,
        audio_source: str,
        chapters: Optional[list[dict]] = None,
        speakers: Optional[list[dict]] = None,
    ) -> Path:
        """生成Markdown文件

        Args:
            result: 转录结果
            title: 标题
            podcast: 播客名称
            audio_source: 音频来源
            chapters: 章节列表
            speakers: 发言人列表

        Returns:
            Path: 生成的Markdown文件路径
        """
        md_path = self.output_dir / f"{sanitize_filename(title)}.md"

        duration_str = format_duration(result.duration)
        date_str = datetime.now().strftime("%Y-%m-%d")
        chapters_str = self._format_chapters(chapters or [])
        speakers_str = self._format_speakers(speakers or [])
        transcript_str = self._format_transcript(result, speakers)

        content = self.template.substitute(
            title=title,
            podcast=podcast,
            date=date_str,
            duration=duration_str,
            audio_source=audio_source,
            audio_filename=Path(result.audio_file).name,
            language=result.language or "Unknown",
            chapters=chapters_str,
            speakers=speakers_str,
            transcript=transcript_str,
        )

        md_path.write_text(content, encoding="utf-8")
        print(f"Markdown文件生成完成: {md_path}")

        return md_path

    def _format_chapters(self, chapters: list[dict]) -> str:
        """格式化章节列表"""
        if not chapters:
            return "- [00:00:00] 开场"

        lines = []
        for chapter in chapters:
            time = chapter.get("time", "00:00:00")
            title = chapter.get("title", "无标题")
            lines.append(f"- [{time}] {title}")

        return "\n".join(lines)

    def _format_speakers(self, speakers: list[dict]) -> str:
        """格式化发言人列表"""
        if not speakers:
            return ""

        lines = ["## 发言人", ""]
        for i, speaker in enumerate(speakers):
            name = speaker.get("name", f"Speaker {i + 1}")
            lines.append(f"- **{name}**")
        return "\n".join(lines)

    def _format_transcript(
        self, result: TranscriptionResult, speakers: Optional[list[dict]] = None
    ) -> str:
        """格式化转录文本"""
        if not result.transcript:
            return "（无转录内容）"

        if result.segments and result.segments[0].get("start") is not None:
            return self._format_timestamped_transcript(result, speakers)
        return f"\n{result.transcript}\n"

    def _format_timestamped_transcript(
        self, result: TranscriptionResult, speakers: Optional[list[dict]] = None
    ) -> str:
        """格式化带时间戳的转录文本"""
        lines = []
        speaker_map = {s["id"]: s["name"] for s in (speakers or [])}

        for segment in result.segments:
            start = segment.get("start", 0)
            text = segment.get("text", "").strip()
            speaker_id = segment.get("speaker", "")

            timestamp = self._format_timestamp(start)
            speaker_name = speaker_map.get(speaker_id, "")

            if speaker_name:
                lines.append(f"**[{timestamp}] {speaker_name}:** {text}")
            else:
                lines.append(f"**[{timestamp}]** {text}")

        return "\n".join(lines)

    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def generate_with_timestamps(
        self, result: TranscriptionResult, title: str, podcast: str, audio_source: str
    ) -> Path:
        """生成带时间戳的Markdown文件"""
        md_path = self.output_dir / f"{sanitize_filename(title)}_with_timestamps.md"

        duration_str = format_duration(result.duration)
        date_str = datetime.now().strftime("%Y-%m-%d")

        chapters_str = "- [00:00:00] 开场介绍\n"

        if result.segments:
            first_timestamp = result.segments[0].get("start", 0)
            chapters_str += f"- [{self._format_timestamp(first_timestamp)}] 开始\n"

        transcript_str = self._format_timestamped_transcript(result)

        content = f"""---
title: "{title}"
podcast: "{podcast}"
date: {date_str}
duration: "{duration_str}"
source: `{audio_source}`
audio: {Path(result.audio_file).name}
---

# {title}

## 基本信息

- **播客**: {podcast}
- **日期**: {date_str}
- **时长**: {duration_str}
- **语言**: {result.language or "Unknown"}

## 章节

{chapters_str}

## 转录文本（带时间戳）

{transcript_str}

---
*由 podcli 生成*
"""

        md_path.write_text(content, encoding="utf-8")
        print(f"带时间戳的Markdown文件生成完成: {md_path}")

        return md_path
