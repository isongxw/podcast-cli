#!/usr/bin/env python3
"""
音频转录模块 - 使用 WhisperX

特性：
- 批量推理，70倍实时速度
- 精确的词级时间戳对齐
- VAD预处理，减少幻觉
- 可选说话人分离
- 自动语言检测
"""

import gc
import os
from collections.abc import Callable
from pathlib import Path

# 修复 PyTorch 2.6+ 的 weights_only 兼容性问题
# 参考: https://github.com/m-bain/whisperX/issues/1525
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"

import torch
import whisperx
from pydantic import BaseModel, Field
from pydub import AudioSegment
from rich.console import Console

from config import config
from utils import format_duration

console = Console()


class TranscriptionResult(BaseModel):
    """转录结果数据类"""

    audio_file: str
    transcript: str
    language: str | None = None
    duration: float | None = None
    error: str | None = None
    segments: list[dict] = Field(default_factory=list)
    speakers: list[dict] = Field(default_factory=list)
    word_segments: list[dict] = Field(default_factory=list)


class ModelCacheManager:
    """模型缓存管理器"""

    def __init__(self, cache_dir: str | None = None):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "whisperx"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_size(self) -> str:
        """获取缓存大小"""
        total_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*") if f.is_file())
        for unit in ["B", "KB", "MB", "GB"]:
            if total_size < 1024:
                return f"{total_size:.1f} {unit}"
            total_size /= 1024
        return f"{total_size:.1f} TB"

    def cleanup_all(self) -> int:
        """清理所有模型缓存

        Returns:
            int: 清理的文件数量
        """
        count = 0
        for cache_file in self.cache_dir.rglob("*"):
            if cache_file.is_file():
                try:
                    cache_file.unlink()
                    count += 1
                except Exception:
                    pass

        # 清理空目录
        for cache_dir in sorted(self.cache_dir.rglob("*"), reverse=True):
            if cache_dir.is_dir():
                try:
                    cache_dir.rmdir()
                except Exception:
                    pass

        console.print(f"[green]已清理 {count} 个缓存文件[/green]")
        return count


class WhisperXTranscriber:
    """WhisperX转录器"""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        language: str | None = None,
        initial_prompt: str | None = None,
        chunk_length: int | None = None,
        compute_type: str | None = None,
        batch_size: int | None = None,
        enable_alignment: bool | None = None,
        align_model: str | None = None,
        diarize: bool | None = None,
        hf_token: str | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ):
        self.model_size = model_size or config.whisper.model
        self.device = device or config.whisper.device
        self.language = language or config.whisper.language
        self.initial_prompt = initial_prompt or config.whisper.initial_prompt
        self.chunk_length = chunk_length or config.whisper.chunk_length
        self.compute_type = compute_type or config.whisper.compute_type
        self.batch_size = batch_size or config.whisper.batch_size
        self.enable_alignment = enable_alignment if enable_alignment is not None else config.whisper.enable_alignment
        self.align_model = align_model or config.whisper.align_model
        self.diarize = diarize if diarize is not None else config.whisper.diarize
        self.hf_token = hf_token or config.whisper.hf_token
        self.min_speakers = min_speakers or config.whisper.min_speakers
        self.max_speakers = max_speakers or config.whisper.max_speakers

        self.model = None
        self.align_model_obj = None
        self.align_metadata = None
        self.diarize_model = None
        self.cache_manager = ModelCacheManager()

    def load_model(self) -> bool:
        """加载WhisperX模型

        Returns:
            bool: 是否加载成功
        """
        try:
            console.print(f"[cyan]加载WhisperX模型: {self.model_size}[/cyan]")

            if self.device == "cuda" and not torch.cuda.is_available():
                console.print("[yellow]CUDA不可用，使用CPU[/yellow]")
                self.device = "cpu"

            self.model = whisperx.load_model(
                self.model_size,
                self.device,
                compute_type=self.compute_type,
                download_root=str(self.cache_manager.cache_dir),
            )

            console.print("[green]WhisperX模型加载成功[/green]")
            return True

        except Exception as e:
            console.print(f"[red]加载WhisperX模型失败: {e}[/red]")
            return False

    def _load_align_model(self, language_code: str) -> bool:
        """加载对齐模型

        Args:
            language_code: 语言代码

        Returns:
            bool: 是否加载成功
        """
        try:
            console.print(f"[cyan]加载对齐模型 (语言: {language_code})...[/cyan]")

            self.align_model_obj, self.align_metadata = whisperx.load_align_model(
                language_code=language_code,
                device=self.device,
                model_name=self.align_model if self.align_model else None,
            )

            console.print("[green]对齐模型加载成功[/green]")
            return True

        except Exception as e:
            console.print(f"[yellow]加载对齐模型失败: {e}[/yellow]")
            console.print("[yellow]将使用原始转录结果（无词级时间戳）[/yellow]")
            return False

    def _load_diarize_model(self) -> bool:
        """加载说话人分离模型

        Returns:
            bool: 是否加载成功
        """
        try:
            if not self.hf_token:
                console.print("[yellow]警告: 未设置HuggingFace Token，说话人分离功能不可用[/yellow]")
                console.print("[yellow]请在配置中设置 hf_token 或环境变量 HUGGINGFACE_TOKEN[/yellow]")
                return False

            console.print("[cyan]加载说话人分离模型...[/cyan]")

            self.diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=self.hf_token,
                device=self.device,
            )

            console.print("[green]说话人分离模型加载成功[/green]")
            return True

        except Exception as e:
            console.print(f"[yellow]加载说话人分离模型失败: {e}[/yellow]")
            return False

    def _get_audio_duration(self, audio_file: Path) -> float:
        """获取音频时长"""
        try:
            audio = AudioSegment.from_file(audio_file)
            return len(audio) / 1000.0
        except Exception:
            return 0.0

    def transcribe_audio(
        self,
        audio_file: str | Path,
        progress_callback: Callable | None = None,
    ) -> TranscriptionResult:
        """转录音频文件

        Args:
            audio_file: 音频文件路径
            progress_callback: 进度回调函数

        Returns:
            TranscriptionResult: 转录结果
        """
        audio_path = Path(audio_file)

        try:
            if not self.model:
                if not self.load_model():
                    return TranscriptionResult(
                        audio_file=str(audio_file),
                        transcript="",
                        error="无法加载语音识别模型",
                    )

            duration = self._get_audio_duration(audio_path)

            console.print(f"[cyan]开始转录: {audio_path.name} (时长: {format_duration(duration)})[/cyan]")

            # 1. 加载音频
            console.print("[cyan]加载音频...[/cyan]")
            audio = whisperx.load_audio(str(audio_path))

            # 2. 转录
            console.print(f"[cyan]执行转录 (batch_size={self.batch_size})...[/cyan]")

            language = None if self.language == "auto" else self.language

            result = self.model.transcribe(
                audio,
                batch_size=self.batch_size,
                language=language,
            )

            detected_language = result.get("language", "unknown")
            console.print("[green]转录完成[/green]")
            console.print(f"[cyan]检测到的语言: {detected_language}[/cyan]")

            # 3. 对齐（获取词级时间戳）
            if self.enable_alignment and result.get("segments"):
                if self._load_align_model(detected_language):
                    console.print("[cyan]执行词级时间戳对齐...[/cyan]")
                    try:
                        result = whisperx.align(
                            result["segments"],
                            self.align_model_obj,
                            self.align_metadata,
                            audio,
                            self.device,
                            return_char_alignments=False,
                        )
                        console.print("[green]对齐完成[/green]")
                    except Exception as e:
                        console.print(f"[yellow]对齐失败: {e}[/yellow]")

            # 4. 说话人分离
            speakers = []
            if self.diarize and self.hf_token:
                if self._load_diarize_model():
                    console.print("[cyan]执行说话人分离...[/cyan]")
                    try:
                        diarize_segments = self.diarize_model(
                            audio,
                            min_speakers=self.min_speakers,
                            max_speakers=self.max_speakers,
                        )

                        result = whisperx.assign_word_speakers(diarize_segments, result)

                        speakers = diarize_segments.to_dict("records")
                        console.print(
                            f"[green]检测到 {len(set(s['speaker'] for s in result.get('segments', []) if 'speaker' in s))} 个说话人[/green]"
                        )

                    except Exception as e:
                        console.print(f"[yellow]说话人分离失败: {e}[/yellow]")

            # 构建转录文本
            transcript = " ".join(segment.get("text", "").strip() for segment in result.get("segments", [])).strip()

            console.print(f"[cyan]转录文本长度: {len(transcript)} 字符[/cyan]")

            # 提取词级时间戳（如果有）
            word_segments = []
            for segment in result.get("segments", []):
                for word in segment.get("words", []):
                    word_segments.append(
                        {
                            "word": word.get("word", ""),
                            "start": word.get("start"),
                            "end": word.get("end"),
                            "speaker": word.get("speaker"),
                        }
                    )

            return TranscriptionResult(
                audio_file=str(audio_file),
                transcript=transcript,
                language=detected_language,
                duration=duration,
                segments=result.get("segments", []),
                speakers=speakers,
                word_segments=word_segments,
            )

        except Exception as e:
            console.print(f"[red]音频转录失败: {e}[/red]")
            return TranscriptionResult(audio_file=str(audio_file), transcript="", error=str(e))

        finally:
            # 清理GPU内存
            if torch.cuda.is_available():
                gc.collect()
                torch.cuda.empty_cache()

    def cleanup(self):
        """清理资源"""
        self.model = None
        self.align_model_obj = None
        self.align_metadata = None
        self.diarize_model = None

        if torch.cuda.is_available():
            gc.collect()
            torch.cuda.empty_cache()

        console.print("[yellow]转录模块资源已清理[/yellow]")


def transcribe_audio(
    audio_source: str,
    title: str | None = None,
    podcast: str | None = None,
    enable_speaker: bool = False,
) -> Path | None:
    """便捷的音频转录函数

    Args:
        audio_source: 音频URL或文件路径
        title: 标题
        podcast: 播客名称
        enable_speaker: 是否启用发言人识别

    Returns:
        Optional[Path]: Markdown文件路径
    """
    from core.downloader import download_audio
    from core.markdown import MarkdownGenerator

    console.print(f"[cyan]转录音频: {audio_source}[/cyan]")

    audio_file = Path(audio_source)

    if audio_source.startswith("http"):
        downloaded = download_audio(audio_source, title)
        if not downloaded:
            console.print("[red]音频下载失败[/red]")
            return None
        audio_file = downloaded

    if not audio_file.exists():
        console.print("[red]音频文件不存在[/red]")
        return None

    transcriber = WhisperXTranscriber(
        model_size=config.whisper.model,
        device=config.whisper.device,
        language=config.whisper.language,
        initial_prompt=config.whisper.initial_prompt,
        batch_size=config.whisper.batch_size,
        enable_alignment=config.whisper.enable_alignment,
        align_model=config.whisper.align_model,
        diarize=enable_speaker or config.whisper.diarize,
        hf_token=config.whisper.hf_token,
        min_speakers=config.whisper.min_speakers,
        max_speakers=config.whisper.max_speakers,
    )

    if not transcriber.load_model():
        console.print("[red]模型加载失败[/red]")
        return None

    result = transcriber.transcribe_audio(audio_file)

    if result.error:
        console.print(f"[red]转录失败: {result.error}[/red]")
        return None

    generator = MarkdownGenerator(config.output.dir)
    md_file = generator.generate(
        result=result,
        title=title or audio_file.stem,
        podcast=podcast or "未知播客",
        audio_source=audio_source,
    )

    console.print("[green]转录完成！[/green]")
    console.print(f"[bold]Markdown文件:[/bold] {md_file}")

    if audio_source.startswith("http") and not config.output.save_audio:
        try:
            from core.downloader import DownloadManager

            downloader = DownloadManager()
            downloader.cleanup(audio_file)
        except Exception:
            pass

    return md_file
