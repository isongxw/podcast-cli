#!/usr/bin/env python3
"""
LLM结构化Markdown生成模块

功能：
- 将转录文本发送到LLM进行结构化处理
- 自动分段、生成小标题
- 修正错别字和专业术语
- 生成结构化的Markdown文档
"""

import json
import re
from datetime import datetime
from pathlib import Path

import requests
from pydantic import BaseModel, Field
from rich.console import Console
from rich.live import Live
from rich.text import Text

from config import config
from utils import sanitize_filename

console = Console()


class EpisodeMetadata(BaseModel):
    """单集元数据"""

    feed_url: str = ""
    audio_url: str = ""
    podcast_title: str = ""
    podcast_description: str = ""
    episode_title: str = ""
    episode_description: str = ""
    pub_date: str = ""
    artwork_url: str = ""


class StructuredResult(BaseModel):
    """结构化结果"""

    title: str = ""
    domain: str = ""
    full_summary: str = ""
    sections: list[dict] = Field(default_factory=list)
    terminology_corrections: dict = Field(default_factory=dict)
    original_transcript: str = ""
    structured_markdown: str = ""


class LLMStructurer:
    """LLM结构化处理器"""

    SYSTEM_PROMPT = """你是一个专业的播客内容整理助手。你的任务是：

1. **自动分析并标记内容领域**：仔细阅读转录文本，分析讨论的主题和涉及的专业领域（如：人工智能、编程、医学、法律、商业、科技、历史、心理学等），将检测到的领域填写到 domain 字段
2. **生成全文总结**：写一篇500-800字的详细总结，概括播客的主要观点、讨论内容、核心结论和亮点，让读者快速了解全文内容
3. **严格保持原文**：对转录文本只做最少量的修改，**禁止总结、删减或改写原文内容**，仅修正明显的错别字和语法错误
4. **提升可读性**：仅在必要处添加适当的标点符号，保持原有的段落结构，不要重新组织内容
5. **合理分段**：仅在有明显话题转换或自然停顿处才增加小标题，**不要过度细分**，每个段落应保持较大的内容块（建议至少300-500字）
6. **识别并修正专业术语**（根据内容领域）
7. **保留说话人信息**：如果转录文本中包含说话人标签（如 [SPEAKER_00]），请在输出中保留这些标签，以便区分不同说话人
8. 生成结构化的Markdown文档

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{
    "title": "生成的文章标题",
    "domain": "内容领域（如：人工智能、编程、医学、法律、商业、科技等）- 请根据内容自动分析填写",
    "full_summary": "500-800字的详细全文总结，概括主要观点、讨论内容和核心结论",
    "sections": [
        {
            "heading": "章节标题",
            "content": "该章节的完整内容（保持原意，仅修正错别字和标点，保留说话人标签如 [SPEAKER_00]）"
        }
    ]
}
```

## 重要规则

1. **自动检测领域**：必须根据转录文本内容自动分析并填写 domain 字段，不要留空
2. **全文总结**：full_summary 字段必须包含500-800字的详细总结，概括播客的主要内容和观点
3. **严禁改写原文**：保持原始转录文本的完整性，**禁止总结、删减、扩写或重新表述**，仅修正明显的错别字和增加标点符号，进行文章分段提升可读性
4. **保持核心内容**：保留原文的细节和具体内容
5. **保留说话人标签**：如果输入文本包含 [SPEAKER_XX] 格式的说话人标签，请在输出中保留这些标签
6. **小标题精简**：小标题2-5个字，准确概括段落内容，**仅在必要的话题转换处添加**，避免过度细分
7. **段落长度**：每个 section 的内容应保持较大块，**至少300-500字**，不要频繁分段
8. **JSON格式**：确保输出严格为有效JSON格式
9. **不要输出markdown代码块**，直接输出JSON字符串
"""

    def __init__(self):
        self.openai_config = config.openai
        self.structured_config = config.structured

    def _build_user_prompt(
        self,
        transcript: str,
        metadata: EpisodeMetadata,
    ) -> str:
        """构建用户提示词"""
        return f"""## 播客信息
- **播客名称**: {metadata.podcast_title}
- **播客介绍**: {metadata.podcast_description}
- **单集标题**: {metadata.episode_title}
- **单集介绍**: {metadata.episode_description}
- **RSS链接**: {metadata.feed_url}
- **音频链接**: {metadata.audio_url}
- **发布日期**: {metadata.pub_date}

## 转录文本

{transcript}

请对上述转录文本进行结构化处理，按照要求的JSON格式输出。"""

    def _call_llm(self, prompt: str) -> str | None:
        """调用LLM API (流式输出)"""
        headers = {
            "Authorization": f"Bearer {self.openai_config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.openai_config.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.openai_config.max_tokens,
            "temperature": self.openai_config.temperature,
            "stream": True,
        }

        try:
            console.print("[cyan]正在调用LLM...[/cyan]")
            full_response = []

            # 使用 Live 组件来正确显示流式内容
            with (
                Live(
                    Text("", style="dim"), console=console, refresh_per_second=10
                ) as live,
                requests.post(
                    f"{self.openai_config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.openai_config.request_timeout,
                    stream=True,
                ) as response,
            ):
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue

                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                full_response.append(content)

                                # 只保留最近的20个字符用于显示
                                current_text = "".join(full_response)
                                display_text = (
                                    current_text[-20:]
                                    if len(current_text) > 20
                                    else current_text
                                )
                                live.update(Text(display_text, style="dim"))
                        except (json.JSONDecodeError, KeyError):
                            continue

            console.print("\n[green]LLM响应完成[/green]")
            return "".join(full_response)

        except requests.exceptions.Timeout:
            console.print("[red]LLM请求超时[/red]")
            return None
        except requests.exceptions.HTTPError as e:
            console.print(f"[red]LLM请求失败: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]LLM调用错误: {e}[/red]")
            return None

    def _parse_response(self, response: str) -> dict | None:
        """解析LLM响应"""
        if not response:
            console.print("[red]LLM响应为空[/red]")
            return None

        try:
            response = response.strip()
            response = re.sub(r"^```json\s*", "", response)
            response = re.sub(r"\s*```$", "", response)
            response = response.strip()
            return json.loads(response)
        except json.JSONDecodeError as e:
            console.print(f"[yellow]JSON解析失败: {e}[/yellow]")
            console.print("[yellow]尝试提取有效JSON...[/yellow]")
            try:
                # 尝试找到最外层的大括号
                start = response.find("{")
                end = response.rfind("}")
                if start != -1 and end != -1 and end > start:
                    json_str = response[start : end + 1]
                    return json.loads(json_str)
            except Exception as e2:
                console.print(f"[red]修复失败: {e2}[/red]")

            console.print("[red]无法解析LLM响应，返回原始文本[/red]")
            return None

    def _generate_markdown(
        self,
        parsed: dict,
        metadata: EpisodeMetadata,
        original_transcript: str,
    ) -> str:
        """生成Markdown文档"""
        lines = [
            "---",
            f'title: "{parsed.get("title", metadata.episode_title)}"',
            f'podcast: "{metadata.podcast_title}"',
            f"date: {datetime.now().strftime('%Y-%m-%d')}",
            f'domain: "{parsed.get("domain", "未知领域")}"',
            f'rss_url: "{metadata.feed_url}"',
            f'audio_url: "{metadata.audio_url}"',
            f"original_transcript_length: {len(original_transcript)} 字符",
            "---",
            "",
            f"# {parsed.get('title', metadata.episode_title)}",
            "",
            "## 基本信息",
            "",
            f"- **播客**: [{metadata.podcast_title}]({metadata.feed_url})",
            f"- **单集**: {metadata.episode_title}",
            f"- **发布日期**: {metadata.pub_date}",
            f"- **RSS**: [订阅链接]({metadata.feed_url})",
            f"- **音频**: [下载链接]({metadata.audio_url})",
            f"- **内容领域**: {parsed.get('domain', '未知领域')}",
            "",
            "## 全文总结",
            "",
            parsed.get("full_summary", "（未生成全文总结）"),
            "",
            "## 播客介绍",
            "",
            metadata.podcast_description or "（无介绍）",
            "",
            "## 单集介绍",
            "",
            metadata.episode_description or "（无介绍）",
            "",
            "## 章节内容",
            "",
        ]

        for i, section in enumerate(parsed.get("sections", []), 1):
            lines.append(f"### {section.get('heading', f'第{i}节')}")
            lines.append("")
            lines.append(section.get("content", ""))
            lines.append("")

        if parsed.get("terminology_corrections"):
            lines.append("## 术语修正")
            lines.append("")
            lines.append("| 原文 | 修正后 |")
            lines.append("|------|--------|")
            for original, corrected in parsed.get(
                "terminology_corrections", {}
            ).items():
                lines.append(f"| {original} | {corrected} |")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 原始转录文本")
        lines.append("")
        lines.append(original_transcript)
        lines.append("")

        return "\n".join(lines)

    def _split_transcript(self, transcript: str) -> list[str]:
        """分割长转录文本为多个段落，每段不超过 segment_length"""
        # 如果文本较短，直接返回
        if len(transcript) <= self.structured_config.segment_length:
            return [transcript]

        segments = []
        current = ""
        # 按句子边界分割（保留标点），\s* 支持句末有或没有空格的情况
        sentences = re.split(r"(?<=[。！？.!?])\s*", transcript)

        for sentence in sentences:
            if not sentence.strip():
                continue

            # 如果当前句子本身超过限制，直接作为一个段
            if len(sentence) > self.structured_config.segment_length:
                if current:
                    segments.append(current.strip())
                    current = ""
                segments.append(sentence.strip())
            # 如果加入当前句子会超过限制，先保存当前段
            elif len(current) + len(sentence) >= self.structured_config.segment_length:
                if current:
                    segments.append(current.strip())
                current = sentence
            else:
                current += sentence

        # 处理最后剩余的文本
        if current.strip():
            segments.append(current.strip())

        return segments

    def structure_transcript(
        self,
        transcript: str,
        metadata: EpisodeMetadata,
    ) -> StructuredResult | None:
        """结构化转录文本

        Args:
            transcript: 转录文本
            metadata: 单集元数据

        Returns:
            StructuredResult: 结构化结果
        """
        if not self.openai_config.api_key:
            console.print("[red]未配置OpenAI API密钥[/red]")
            return None

        if not transcript or len(transcript.strip()) < 100:
            console.print("[yellow]转录文本太短，跳过结构化处理[/yellow]")
            return None

        console.print("[cyan]开始LLM结构化处理...[/cyan]")

        result = StructuredResult(original_transcript=transcript)

        segments = self._split_transcript(transcript)
        all_sections = []
        terminology_corrections = {}

        for i, segment in enumerate(segments, 1):
            console.print(f"[cyan]处理第 {i}/{len(segments)} 段...[/cyan]")

            if len(segments) > 1:
                segment_metadata = EpisodeMetadata(
                    **{
                        **metadata.model_dump(),
                        "episode_description": f"（第{i}段，共{len(segments)}段）{metadata.episode_description}",
                    }
                )
            else:
                segment_metadata = metadata

            prompt = self._build_user_prompt(segment, segment_metadata)
            response = self._call_llm(prompt)
            with open("debug.text", "w") as f:
                f.write(response)

            if not response:
                console.print(f"[yellow]第{i}段处理失败，使用原始文本[/yellow]")
                all_sections.append({"heading": f"第{i}部分", "content": segment})
                continue

            parsed = self._parse_response(response)

            if not parsed:
                console.print(f"[yellow]第{i}段解析失败，使用原始文本[/yellow]")
                all_sections.append({"heading": f"第{i}部分", "content": segment})
                continue

            full_summary = parsed.get("full_summary", "")

            for section in parsed.get("sections", []):
                section["content"] = re.sub(
                    r"^\s*\d+\.\s*", "", section.get("content", "")
                )
                all_sections.append(section)

            terminology_corrections.update(parsed.get("terminology_corrections", {}))

        result.title = metadata.episode_title
        result.domain = parsed.get("domain", "通用领域") if parsed else "通用领域"
        result.full_summary = full_summary
        result.sections = all_sections
        result.terminology_corrections = terminology_corrections

        result.structured_markdown = self._generate_markdown(
            result.model_dump(), metadata, transcript
        )

        console.print("[green]LLM结构化处理完成[/green]")

        return result

    def save_result(
        self,
        result: StructuredResult,
        output_dir: Path | None = None,
    ) -> Path | None:
        """保存结构化结果

        Args:
            result: 结构化结果
            output_dir: 输出目录

        Returns:
            Path: 保存的文件路径
        """
        if not result or not result.structured_markdown:
            return None

        output_dir = Path(output_dir) if output_dir else config.output.dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = sanitize_filename(result.title)
        file_path = output_dir / f"{filename}_structured.md"

        file_path.write_text(result.structured_markdown, encoding="utf-8")
        console.print(f"[green]结构化文档已保存: {file_path}[/green]")

        return file_path


def structure_transcript(
    transcript: str,
    feed_url: str = "",
    audio_url: str = "",
    podcast_title: str = "",
    podcast_description: str = "",
    episode_title: str = "",
    episode_description: str = "",
    pub_date: str = "",
    output_dir: Path | None = None,
) -> Path | None:
    """便捷的结构化函数

    Args:
        transcript: 转录文本
        feed_url: RSS链接
        audio_url: 音频链接
        podcast_title: 播客标题
        podcast_description: 播客介绍
        episode_title: 单集标题
        episode_description: 单集介绍
        pub_date: 发布日期
        output_dir: 输出目录

    Returns:
        Path: 保存的文件路径
    """
    metadata = EpisodeMetadata(
        feed_url=feed_url,
        audio_url=audio_url,
        podcast_title=podcast_title,
        podcast_description=podcast_description,
        episode_title=episode_title,
        episode_description=episode_description,
        pub_date=pub_date,
    )

    structurer = LLMStructurer()
    result = structurer.structure_transcript(transcript, metadata)

    if result:
        return structurer.save_result(result, output_dir)

    return None
