#!/usr/bin/env python3
"""
转录模块
"""

import os
import time
import torch
from pathlib import Path
from pydub import AudioSegment
from datetime import datetime
from rich.console import Console
from rich.progress import Progress

# 创建控制台实例
console = Console()

class TranscriptionResult:
    def __init__(self, audio_file, transcript, language=None, duration=None, error=None):
        self.audio_file = audio_file
        self.transcript = transcript
        self.language = language
        self.duration = duration
        self.error = error

class WhisperTranscriber:
    def __init__(self, model_size="base", device="cpu", language="auto"):
        self.model_size = model_size
        self.device = device
        self.language = language
        self.model = None
    
    def load_model(self):
        """加载Whisper模型"""
        try:
            import whisper
            import os
            
            console.print(f"[cyan]加载Whisper模型: {self.model_size}[/cyan]")
            
            # 检测设备
            if self.device == "cuda" and not torch.cuda.is_available():
                console.print("[yellow]CUDA不可用，使用CPU[/yellow]")
                self.device = "cpu"
            
            # 尝试清理缓存的模型文件
            cache_dir = os.path.expanduser("~/.cache/whisper")
            model_file = os.path.join(cache_dir, f"{self.model_size}.pt")
            
            if os.path.exists(model_file):
                try:
                    console.print("[yellow]检测到缓存的模型文件，尝试清理...[/yellow]")
                    os.remove(model_file)
                    console.print("[green]已清理缓存的模型文件[/green]")
                except Exception as e:
                    console.print(f"[yellow]清理缓存失败: {e}[/yellow]")
            
            # 加载模型
            self.model = whisper.load_model(
                self.model_size,
                device=self.device,
                download_root=os.path.expanduser("~/.cache/whisper")
            )
            
            console.print("[green]Whisper模型加载成功[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]加载Whisper模型失败: {e}[/red]")
            return False
    
    def split_audio(self, audio_file, segment_duration=60):
        """将音频文件分割成小段"""
        try:
            audio = AudioSegment.from_file(audio_file)
            duration = len(audio) / 1000.0  # 转换为秒
            
            segments = []
            segment_count = int(duration / segment_duration) + 1
            
            console.print(f"[cyan]将音频分割为 {segment_count} 段，每段 {segment_duration} 秒[/cyan]")
            
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            with Progress() as progress:
                task = progress.add_task("[cyan]分割音频[/cyan]", total=segment_count)
                
                for i in range(segment_count):
                    start_time = i * segment_duration * 1000  # 转换为毫秒
                    end_time = min((i + 1) * segment_duration * 1000, len(audio))
                    
                    if end_time <= start_time:
                        break
                    
                    segment = audio[start_time:end_time]
                    segment_file = temp_dir / f"temp_segment_{Path(audio_file).stem}_{i}.wav"
                    segment.export(segment_file, format="wav")
                    segments.append(str(segment_file))
                    progress.update(task, advance=1)
            
            return segments
            
        except Exception as e:
            console.print(f"[red]分割音频失败: {e}[/red]")
            return []
    
    def transcribe_audio(self, audio_file):
        """转译单个音频文件"""
        try:
            if not self.model:
                if not self.load_model():
                    return TranscriptionResult(
                        audio_file=str(audio_file),
                        transcript="",
                        error="无法加载语音识别模型"
                    )
            
            # 获取音频时长
            audio = AudioSegment.from_file(audio_file)
            duration = len(audio) / 1000.0  # 转换为秒
            
            console.print(f"[cyan]开始转译音频: {audio_file} (时长: {duration:.2f}秒)[/cyan]")
            
            # 分割音频避免OOM
            if duration > 120:  # 超过2分钟的音频进行分割
                segments = self.split_audio(audio_file)
                
                if not segments:
                    return TranscriptionResult(
                        audio_file=str(audio_file),
                        transcript="",
                        error="音频分割失败"
                    )
                
                # 逐段转译并合并结果
                full_transcript = ""
                detected_language = None
                
                console.print(f"[cyan]开始转译 {len(segments)} 个音频片段...[/cyan]")
                
                # 使用rich的进度条
                start_time = time.time()
                
                with Progress() as progress:
                    task = progress.add_task("[cyan]转译进度[/cyan]", total=len(segments))
                    
                    for i, segment_file in enumerate(segments):
                        try:
                            segment_start = time.time()
                            
                            result = self.model.transcribe(
                                segment_file,
                                language=self.language if self.language != "auto" else None,
                                fp16=torch.cuda.is_available(),
                                initial_prompt="以下是普通话的句子"
                            )
                            
                            segment_transcript = result["text"].strip()
                            full_transcript += segment_transcript + " "
                            
                            if not detected_language:
                                detected_language = result.get("language")
                            
                            # 计算处理时间
                            segment_time = time.time() - segment_start
                            elapsed = time.time() - start_time
                            remaining = (elapsed / (i + 1)) * (len(segments) - i - 1)
                            
                            # 更新进度条
                            progress.update(
                                task,
                                advance=1,
                                description=f"[cyan]转译进度 | 已处理: {i+1}/{len(segments)} | 本段耗时: {segment_time:.1f}s | 预计剩余: {remaining:.1f}s[/cyan]"
                            )
                            
                        except Exception as e:
                            console.print(f"[red]转译片段 {i+1} 失败: {e}[/red]")
                            progress.update(task, advance=1)
                        finally:
                            # 清理临时文件
                            if os.path.exists(segment_file):
                                os.remove(segment_file)
                
                transcript = full_transcript.strip()
            else:
                # 短音频直接转译
                console.print("[cyan]转译中...[/cyan]")
                result = self.model.transcribe(
                    audio_file,
                    language=self.language if self.language != "auto" else None,
                    fp16=torch.cuda.is_available(),
                    initial_prompt="以下是普通话的句子，这是一段关于人工智能和机器学习的对话。"
                )
                
                transcript = result["text"].strip()
                detected_language = result.get("language")
            
            console.print(f"[green]音频转译完成: {audio_file}[/green]")
            console.print(f"[cyan]检测到的语言: {detected_language}[/cyan]")
            console.print(f"[cyan]转录文本长度: {len(transcript)} 字符[/cyan]")
            
            return TranscriptionResult(
                audio_file=str(audio_file),
                transcript=transcript,
                language=detected_language,
                duration=duration,
            )
            
        except Exception as e:
            console.print(f"[red]音频转译失败: {audio_file}, 错误: {e}[/red]")
            return TranscriptionResult(
                audio_file=str(audio_file),
                transcript="",
                error=str(e),
            )
    
    def cleanup(self):
        """清理资源"""
        self.model = None
        console.print("[yellow]转录模块资源已清理[/yellow]")


