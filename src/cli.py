#!/usr/bin/env python3
"""
podcli - 极简播客转录工具

命令：
  search <关键词>              # 搜索播客
  search <关键词> --episode    # 搜索单集名称
  episodes <feed-url>          # 列出单集
  transcribe <音频URL或文件>    # 转录为 Markdown
  get <feed-url> --latest      # 下载最新单集并转录
  download <feed-url>          # 批量下载单集
  subscribe <feed-url>         # 订阅播客
  list                         # 列出已下载
  cache                        # 管理模型缓存
"""

import sys
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import config
from core import (
    DownloadManager,
    Episode,
    MarkdownGenerator,
    ModelCacheManager,
    RSSParser,
    WhisperXTranscriber,
    download_audio,
)
from core.llm_structurer import EpisodeMetadata, LLMStructurer
from utils import sanitize_filename

console = Console()


def interactive_select(items, title="选择", limit=5):
    """交互式选择函数"""
    import termios
    import tty

    from rich import get_console

    console = get_console()
    selected_index = 0
    items = items[:limit]

    if not items:
        console.print("[yellow]没有找到匹配的结果[/yellow]")
        return None

    def getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def render():
        console.clear()
        title_panel = Panel(
            Text(title, style="bold cyan"), border_style="green", box=box.ROUNDED
        )
        console.print(title_panel)

        options_text = Text()
        for i, item in enumerate(items):
            if i == selected_index:
                options_text.append(f"▶ {i + 1}. {item}", style="bold reverse")
                options_text.append("\n")
            else:
                options_text.append(f"  {i + 1}. {item}\n")

        options_text.append("\n")
        options_text.append("使用 ↑↓ 键导航，Enter 键选择，Esc 键取消", style="cyan")

        options_panel = Panel(options_text, border_style="blue", box=box.ROUNDED)
        console.print(options_panel)

    try:
        while True:
            render()
            ch = getch()

            if ch == "\x1b":
                ch2 = getch()
                if ch2 == "[":
                    ch3 = getch()
                    if ch3 == "A":
                        selected_index = (selected_index - 1) % len(items)
                    elif ch3 == "B":
                        selected_index = (selected_index + 1) % len(items)
                else:
                    console.print("[yellow]取消选择[/yellow]")
                    return None
            elif ch == "\r":
                console.clear()
                console.print(f"[green]已选择: {items[selected_index]}[/green]")
                return items[selected_index]
            elif ch == "q" or ch == "Q":
                console.print("[yellow]取消选择[/yellow]")
                return None
    except KeyboardInterrupt:
        console.print("[yellow]取消选择[/yellow]")
        return None


def format_episode_for_display(episode: Episode, index: int = 0) -> str:
    """格式化单集显示"""
    title = episode.title or "无标题"
    pub_date = episode.pub_date or "未知日期"
    return f"{title} - {pub_date}"


def format_podcast_for_display(podcast) -> str:
    """格式化播客显示"""
    name = podcast.collection_name or "未知名称"
    artist = podcast.artist_name or "未知作者"
    return f"{name} - {artist}"


@click.group()
@click.version_option(version="1.1.0")
def cli():
    """podcli - 极简播客转录工具

    搜索、下载、转录播客内容。

    常用命令:
      \b
      podcli search "python"          # 搜索播客
      podcli episodes <url>            # 列出单集
      podcli get <url> --latest       # 下载并转录最新单集
      podcli download <url>            # 批量下载
    """
    pass


@cli.command()
@click.argument("keyword")
@click.option("--limit", default=5, help="限制搜索结果数量")
@click.option("--episode", is_flag=True, help="搜索单集名称")
def search(keyword, limit, episode):
    """搜索播客或单集"""
    from core.itunes_search import iTunesSearch

    if episode:
        console.print(f"[cyan]搜索单集: {keyword}[/cyan]")

        with console.status("[bold cyan]正在搜索单集...[/bold cyan]"):
            searcher = iTunesSearch()
            results = searcher.search_podcasts(keyword)

        if not results:
            console.print("[yellow]未找到匹配的播客[/yellow]")
            return

        all_episodes = []
        podcast_names = []

        with console.status("[bold cyan]正在获取单集信息...[/bold cyan]"):
            for result in results[:limit]:
                feed_url = result.feed_url
                if feed_url:
                    parser = RSSParser()
                    episodes = parser.get_episodes(feed_url)
                    podcast_name = result.collection_name or "未知名称"

                    for ep in episodes:
                        title = (
                            ep.title
                            if isinstance(ep, Episode)
                            else (ep.title or "无标题")
                        )
                        if keyword.lower() in title.lower():
                            all_episodes.append(ep)
                            podcast_names.append(podcast_name)

        if not all_episodes:
            console.print("[yellow]未找到匹配的单集[/yellow]")
            return

        select_items = [
            format_episode_for_display(ep, i) for i, ep in enumerate(all_episodes)
        ]
        selected_item = interactive_select(
            select_items, title="单集搜索结果", limit=limit
        )

        if not selected_item:
            return

        selected_index = select_items.index(selected_item)
        selected_episode = all_episodes[selected_index]

        console.print("\n[green]已选择单集:[/green]")
        console.print(f"  [bold]标题:[/bold] {selected_episode.title}")
        audio_url = None
        if isinstance(selected_episode, Episode):
            audio_url = selected_episode.audio_url or None
        else:
            audio_url = getattr(selected_episode, "audio_url", None) or None
        if not audio_url:
            if isinstance(selected_episode, Episode):
                enclosure = selected_episode.model_dump().get("enclosure") or {}
            else:
                enclosure = getattr(selected_episode, "enclosure", {}) or {}
            if isinstance(enclosure, dict):
                audio_url = enclosure.get("url")
        if not audio_url:
            console.print("[red]该单集没有音频链接[/red]")
            return

        console.print(f"  [bold]音频链接:[/bold] {audio_url}")

        # 获取播客信息并直接执行pipeline
        with console.status("[bold cyan]获取播客信息...[/bold cyan]"):
            from core.rss_parser import RSSParser

            parser = RSSParser()
            podcast = parser.get_podcast(feed_url) if feed_url else None

        # 创建Episode对象
        episode_obj = selected_episode
        if not isinstance(selected_episode, Episode):
            from core.rss_parser import Episode

            episode_obj = Episode(
                title=selected_episode.title or "未知标题",
                description=getattr(selected_episode, "description", "") or "",
                pub_date=getattr(selected_episode, "pubDate", "") or "",
                audio_url=audio_url,
                audio_type="audio/mpeg",
                audio_length="0",
                artwork_url=getattr(selected_episode, "artwork_url", "") or "",
                guid=getattr(selected_episode, "guid", "") or "",
                episode_number=0,
            )

        # 执行自动化pipeline
        _execute_pipeline(
            audio_url=audio_url,
            episode=episode_obj,
            podcast=podcast,
            feed_url=feed_url if feed_url else "",
            title=selected_episode.title
            if isinstance(selected_episode, Episode)
            else (selected_episode.title or "未知标题"),
        )
    else:
        console.print(f"[cyan]搜索播客: {keyword}[/cyan]")

        with console.status("[bold cyan]正在搜索播客...[/bold cyan]"):
            searcher = iTunesSearch()
            results = searcher.search_podcasts(keyword)

        if not results:
            console.print("[yellow]未找到匹配的播客[/yellow]")
            return

        select_items = [format_podcast_for_display(r) for r in results[:limit]]
        selected_item = interactive_select(select_items, title="搜索结果", limit=limit)

        if not selected_item:
            return

        selected_index = select_items.index(selected_item)
        selected_podcast = results[selected_index]

        console.print("\n[green]已选择播客:[/green]")
        console.print(
            f"  [bold]名称:[/bold] {selected_podcast.collection_name or '未知名称'}"
        )
        console.print(
            f"  [bold]作者:[/bold] {selected_podcast.artist_name or '未知作者'}"
        )

        feed_url = selected_podcast.feed_url
        if not feed_url:
            console.print("[red]该播客没有订阅地址[/red]")
            return

        console.print(f"  [bold]订阅地址:[/bold] {feed_url}")
        console.print("\n[cyan]正在获取播客单集...[/cyan]")

        _episodes_logic(feed_url, limit=limit)


@cli.command()
@click.argument("feed_url")
@click.option("--limit", default=10, help="限制单集数量")
def episodes(feed_url, limit):
    """列出播客单集"""
    _episodes_logic(feed_url, limit)


def _episodes_logic(feed_url, limit=5):
    """单集管理逻辑"""
    console.print(f"[cyan]获取播客单集: {feed_url}[/cyan]")

    with console.status("[bold cyan]正在获取单集信息...[/bold cyan]"):
        parser = RSSParser()
        podcast = parser.get_podcast(feed_url)

    if not podcast or not podcast.episodes:
        console.print("[yellow]未找到播客单集[/yellow]")
        return

    select_items = [
        format_episode_for_display(ep, i)
        for i, ep in enumerate(podcast.episodes[:limit])
    ]
    selected_item = interactive_select(select_items, title="播客单集", limit=limit)

    if not selected_item:
        return

    selected_index = select_items.index(selected_item)
    selected_episode = podcast.episodes[selected_index]

    console.print("\n[green]已选择单集:[/green]")
    console.print(f"  [bold]标题:[/bold] {selected_episode.title}")
    console.print(f"  [bold]发布日期:[/bold] {selected_episode.pub_date}")
    audio_url = selected_episode.audio_url
    if not audio_url:
        console.print("[red]该单集没有音频链接[/red]")
        return

    console.print(f"  [bold]音频链接:[/bold] {audio_url}")

    # 直接执行自动化pipeline
    _execute_pipeline(
        audio_url=audio_url,
        episode=selected_episode,
        podcast=podcast,
        feed_url=feed_url,
        title=selected_episode.title,
    )


@cli.command()
@click.argument("feed_url")
@click.option("--limit", default=5, help="限制下载数量")
@click.option("--transcribe/--no-transcribe", default=False, help="下载后转录")
@click.option("--parallel", "-p", is_flag=True, help="启用并行下载")
def download(feed_url, limit, transcribe, parallel):
    """批量下载播客单集"""
    console.print(f"[cyan]获取播客: {feed_url}[/cyan]")

    with console.status("[bold cyan]正在解析RSS...[/bold cyan]"):
        parser = RSSParser()
        podcast = parser.get_podcast(feed_url)

    if not podcast or not podcast.episodes:
        console.print("[yellow]未找到播客单集[/yellow]")
        return

    target_episodes = podcast.episodes[:limit]

    console.print(f"\n[green]播客: {podcast.title}[/green]")
    console.print(f"[green]将下载 {len(target_episodes)} 个单集[/green]")

    download_items = []
    for ep in target_episodes:
        if ep.audio_url:
            download_items.append({"url": ep.audio_url, "title": ep.title})

    if not download_items:
        console.print("[yellow]没有可下载的音频[/yellow]")
        return

    download_manager = DownloadManager(
        download_dir=config.output.dir,
        max_retries=config.download.max_retries,
        retry_delay=config.download.retry_delay,
        chunk_size=config.download.chunk_size,
        timeout=config.download.timeout,
        resume_enabled=config.download.resume_download,
        max_concurrent=config.download.max_concurrent if parallel else 1,
    )

    downloaded = download_manager.download_batch(download_items)

    if transcribe:
        for audio_file in downloaded:
            if audio_file and audio_file.exists():
                _do_transcribe(str(audio_file), audio_file.stem)

    console.print(
        f"[green]批量下载完成: {len(downloaded)}/{len(download_items)}[/green]"
    )


@cli.command()
@click.argument("feed_url")
@click.option("--latest", is_flag=True, help="获取最新单集")
@click.option("--limit", default=5, help="限制单集数量")
def get(feed_url, latest, limit):
    """获取播客单集并转录"""
    console.print(f"[cyan]获取播客: {feed_url}[/cyan]")

    with console.status("[bold cyan]正在解析RSS...[/bold cyan]"):
        parser = RSSParser()
        podcast = parser.get_podcast(feed_url)

    if not podcast or not podcast.episodes:
        console.print("[yellow]未找到播客单集[/yellow]")
        return

    if latest:
        target_episode = podcast.episodes[0]
        console.print(f"\n[green]获取最新单集:[/green] {target_episode.title}")
    else:
        select_items = [
            format_episode_for_display(ep, i)
            for i, ep in enumerate(podcast.episodes[:limit])
        ]
        selected_item = interactive_select(select_items, title="播客单集", limit=limit)

        if not selected_item:
            return

        selected_index = select_items.index(selected_item)
        target_episode = podcast.episodes[selected_index]
        console.print(f"\n[green]已选择单集:[/green] {target_episode.title}")

    audio_url = target_episode.audio_url
    if not audio_url:
        console.print("[red]未找到音频链接[/red]")
        return

    # 执行自动化pipeline
    _execute_pipeline(
        audio_url=audio_url,
        episode=target_episode,
        podcast=podcast,
        feed_url=feed_url,
        title=target_episode.title,
    )


def _check_config_requirements():
    """检查配置是否满足自动执行要求

    Returns:
        tuple: (是否满足, 错误信息列表)
    """
    errors = []

    # 检查转录配置
    if config.workflow.auto_transcribe:
        # WhisperX模型配置检查 - 主要检查是否能正常使用
        try:
            import whisperx
        except ImportError:
            errors.append("WhisperX未安装，请运行: uv sync")

    # 检查LLM结构化配置
    if config.workflow.auto_structure:
        if not config.openai.api_key:
            errors.append(
                "未配置OpenAI API密钥，请在 ~/.podcli/config.yaml 中配置 openai.api_key"
            )
        if not config.structured.enable:
            errors.append(
                "LLM结构化已禁用(structured.enable=false)，无法执行自动结构化"
            )

    return len(errors) == 0, errors


def _save_intermediate_result(content: str, filename: str, suffix: str) -> Path:
    """保存中间结果

    Args:
        content: 内容
        filename: 文件名
        suffix: 后缀标识(如 _transcript, _raw 等)

    Returns:
        Path: 保存的文件路径
    """
    if not config.workflow.save_intermediate:
        return None

    output_dir = config.output.dir / "intermediate"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 使用工具函数清理文件名
    clean_filename = sanitize_filename(filename)

    file_path = output_dir / f"{clean_filename}{suffix}.txt"
    file_path.write_text(content, encoding="utf-8")

    return file_path


def _execute_pipeline(
    audio_url: str, episode, podcast, feed_url: str, title: str = None
):
    """执行完整的pipeline：下载 -> 转录 -> LLM结构化

    Args:
        audio_url: 音频URL
        episode: 单集对象
        podcast: 播客对象
        feed_url: RSS feed URL
        title: 标题(可选)
    """
    episode_title = title or episode.title
    console.print(f"\n[cyan]开始执行自动化Pipeline: {episode_title}[/cyan]")

    # 检查配置
    config_ok, errors = _check_config_requirements()
    if not config_ok:
        console.print("[red]配置检查失败，无法执行自动Pipeline:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        console.print(
            "\n[yellow]提示: 修改配置文件 ~/.podcli/config.yaml 或禁用相关功能[/yellow]"
        )
        return

    downloaded_file = None
    transcript_result = None
    structured_file = None

    # 步骤1: 下载
    if config.workflow.auto_download:
        console.print(f"\n[cyan]步骤1/3: 下载音频...[/cyan]")
        downloaded_file = download_audio(audio_url, episode_title)
        if not downloaded_file:
            console.print("[red]下载失败，Pipeline中断[/red]")
            return
        console.print(f"[green]下载完成: {downloaded_file}[/green]")
    else:
        console.print("[yellow]自动下载已禁用，跳过下载步骤[/yellow]")
        # 尝试使用已存在的文件
        potential_file = config.output.dir / f"{episode_title}.mp3"
        if potential_file.exists():
            downloaded_file = potential_file
            console.print(f"[cyan]使用已存在的文件: {downloaded_file}[/cyan]")
        else:
            console.print("[red]未找到音频文件，Pipeline中断[/red]")
            return

    # 步骤2: 转录
    if config.workflow.auto_transcribe:
        console.print(f"\n[cyan]步骤2/3: 转录音频...[/cyan]")

        audio_file = Path(downloaded_file)
        if not audio_file.exists():
            console.print("[red]音频文件不存在[/red]")
            return

        transcriber = WhisperXTranscriber(
            model_size=config.whisper.model,
            device=config.whisper.device,
            language=config.whisper.language,
            initial_prompt=config.whisper.initial_prompt,
        )

        if not transcriber.load_model():
            console.print("[red]模型加载失败[/red]")
            return

        result = transcriber.transcribe_audio(audio_file)

        if result.error:
            console.print(f"[red]转录失败: {result.error}[/red]")
            return

        # 生成基础Markdown
        generator = MarkdownGenerator(config.output.dir)
        md_file = generator.generate(
            result=result,
            title=episode_title,
            podcast=podcast.title if podcast else "未知播客",
            audio_source=str(downloaded_file),
        )
        console.print(f"[green]转录完成: {md_file}[/green]")

        # 保存中间结果 - 转录文本
        if config.workflow.save_intermediate:
            _save_intermediate_result(result.transcript, episode_title, "_transcript")

        transcript_result = result
    else:
        console.print("[yellow]自动转录已禁用，跳过转录步骤[/yellow]")

    # 步骤3: LLM结构化
    if config.workflow.auto_structure and transcript_result:
        console.print(f"\n[cyan]步骤3/3: LLM结构化处理...[/cyan]")

        metadata = EpisodeMetadata(
            feed_url=feed_url,
            audio_url=audio_url,
            podcast_title=podcast.title if podcast else "未知播客",
            podcast_description=podcast.description if podcast else "",
            episode_title=episode_title,
            episode_description=episode.description
            if hasattr(episode, "description")
            else "",
            pub_date=episode.pub_date if hasattr(episode, "pub_date") else "",
        )

        structurer = LLMStructurer()
        structured_result = structurer.structure_transcript(
            transcript_result.transcript, metadata
        )

        if structured_result:
            structured_file = structurer.save_result(
                structured_result, config.output.dir
            )
            console.print(f"[green]LLM结构化完成: {structured_file}[/green]")
        else:
            console.print("[yellow]LLM结构化处理失败[/yellow]")
    elif config.workflow.auto_structure and not transcript_result:
        console.print("[yellow]没有转录结果，跳过LLM结构化[/yellow]")
    else:
        console.print("[yellow]自动LLM结构化已禁用，跳过结构化步骤[/yellow]")

    # 总结
    console.print("\n" + "=" * 50)
    console.print("[bold green]Pipeline执行完成！[/bold green]")
    if downloaded_file:
        console.print(f"[cyan]音频文件:[/cyan] {downloaded_file}")
    if transcript_result:
        console.print(f"[cyan]转录文件:[/cyan] {md_file}")
    if structured_file:
        console.print(f"[cyan]结构化文件:[/cyan] {structured_file}")
    console.print("=" * 50)


def _do_transcribe(audio_source, title, podcast=None):
    """执行转录"""
    console.print(f"\n[cyan]开始转录: {title}[/cyan]")

    audio_file = Path(audio_source)
    if not audio_file.exists():
        console.print("[red]音频文件不存在[/red]")
        return

    transcriber = WhisperXTranscriber(
        model_size=config.whisper.model,
        device=config.whisper.device,
        language=config.whisper.language,
        initial_prompt=config.whisper.initial_prompt,
    )

    if not transcriber.load_model():
        console.print("[red]模型加载失败[/red]")
        return

    result = transcriber.transcribe_audio(audio_file)

    if result.error:
        console.print(f"[red]转录失败: {result.error}[/red]")
        return

    generator = MarkdownGenerator(config.output.dir)
    md_file = generator.generate(
        result=result,
        title=title,
        podcast=podcast or "未知播客",
        audio_source=str(audio_source),
    )

    console.print("\n[green]转录完成！[/green]")
    console.print(f"[bold]Markdown文件:[/bold] {md_file}")


def _do_struct(audio_source, episode, podcast, feed_url):
    """执行LLM结构化处理"""
    console.print(f"\n[cyan]开始LLM结构化处理: {episode.title}[/cyan]")

    if not config.structured.enable:
        console.print("[yellow]LLM结构化已禁用，跳过处理[/yellow]")
        return

    audio_file = Path(audio_source)
    if not audio_file.exists():
        console.print("[red]音频文件不存在[/red]")
        return

    transcriber = WhisperXTranscriber(
        model_size=config.whisper.model,
        device=config.whisper.device,
        language=config.whisper.language,
        initial_prompt=config.whisper.initial_prompt,
    )

    if not transcriber.load_model():
        console.print("[red]模型加载失败[/red]")
        return

    result = transcriber.transcribe_audio(audio_file)

    if result.error:
        console.print(f"[red]转录失败: {result.error}[/red]")
        return

    metadata = EpisodeMetadata(
        feed_url=feed_url,
        audio_url=episode.audio_url,
        podcast_title=podcast.title,
        podcast_description=podcast.description,
        episode_title=episode.title,
        episode_description=episode.description,
        pub_date=episode.pub_date,
    )

    structurer = LLMStructurer()
    structured_result = structurer.structure_transcript(result.transcript, metadata)

    if structured_result:
        md_file = structurer.save_result(structured_result, config.output.dir)
        console.print("\n[green]LLM结构化处理完成！[/green]")
        console.print(f"[bold]结构化Markdown文件:[/bold] {md_file}")
    else:
        console.print("[yellow]LLM结构化处理失败[/yellow]")


@cli.command()
@click.argument("audio_source")
@click.option("--title", default=None, help="播客标题")
@click.option("--podcast", default=None, help="播客名称")
def transcribe(audio_source, title, podcast):
    """转录音频为Markdown"""
    _do_transcribe(audio_source, title or Path(audio_source).stem, podcast)


@cli.command()
@click.argument("feed_url")
@click.option("--name", default=None, help="订阅名称")
def subscribe(feed_url, name):
    """订阅播客（保存订阅信息）"""
    from pathlib import Path

    sub_dir = Path.home() / ".podcli" / "subscriptions"
    sub_dir.mkdir(parents=True, exist_ok=True)

    sub_file = sub_dir / "subscriptions.yaml"

    import yaml

    subs = {}
    if sub_file.exists():
        with open(sub_file) as f:
            subs = yaml.safe_load(f) or {}

    sub_name = name or feed_url
    subs[sub_name] = {
        "feed_url": feed_url,
        "added_at": str(Path.home()),
    }

    with open(sub_file, "w") as f:
        yaml.dump(subs, f, default_flow_style=False)

    console.print(f"[green]已添加订阅: {sub_name}[/green]")


@cli.command(name="list")
def list_downloads():
    """列出已下载的播客"""

    output_dir = config.output.dir

    if not output_dir.exists():
        console.print("[yellow]没有已下载的文件[/yellow]")
        return

    md_files = list(output_dir.glob("*.md"))
    audio_files = list(output_dir.glob("*.mp3")) + list(output_dir.glob("*.m4a"))

    table = Table(title="已下载内容")
    table.add_column("类型", style="cyan")
    table.add_column("文件名", style="green")

    for f in md_files[:20]:
        table.add_row("📝", f.name)

    for f in audio_files[:20]:
        table.add_row("🎵", f.name)

    if len(md_files) > 20:
        table.add_row("...", f"... 还有 {len(md_files) - 20} 个文件")

    console.print(table)

    console.print(f"\n总计: {len(md_files)} 个转录, {len(audio_files)} 个音频")


@cli.command()
def cache():
    """管理模型缓存"""
    from core.transcriber import ModelCacheManager

    manager = ModelCacheManager()

    table = Table(title="模型缓存")
    table.add_column("操作", style="cyan")
    table.add_column("状态", style="green")

    cache_size = manager.get_cache_size()
    table.add_row("查看缓存大小", cache_size)

    console.print(table)

    if click.confirm("是否清理所有模型缓存？"):
        count = manager.cleanup_all()
        console.print(f"[green]已清理 {count} 个缓存文件[/green]")


@cli.command(name="config")
@click.option("--show", is_flag=True, help="显示当前配置")
@click.option("--reset", is_flag=True, help="重置为默认配置")
@click.option(
    "--set", "set_values", multiple=True, help="设置配置项 (格式: section.key=value)"
)
def config_command(show, reset, set_values):
    """查看或修改配置

    设置配置示例:
        podcli config --set whisper.hf_token=your_token_here
        podcli config --set whisper.diarize=true
        podcli config --set whisper.batch_size=8
    """
    if set_values:
        for item in set_values:
            if "=" not in item:
                console.print(
                    f"[red]错误格式: {item}，请使用 section.key=value 格式[/red]"
                )
                continue

            key_path, value = item.split("=", 1)
            parts = key_path.split(".")

            if len(parts) != 2:
                console.print(
                    f"[red]错误格式: {item}，请使用 section.key=value 格式[/red]"
                )
                continue

            section, key = parts

            # 转换布尔值
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.lower() == "none" or value == "":
                value = None
            elif value.isdigit():
                value = int(value)

            if config.update(section, key, value):
                console.print(f"[green]已设置: {section}.{key} = {value}[/green]")
            else:
                console.print(f"[red]设置失败: {section}.{key}[/red]")
        return

    if show:
        table = Table(title="当前配置")
        table.add_column("设置", style="cyan")
        table.add_column("值", style="green")

        table.add_row("Whisper模型", config.whisper.model)
        table.add_row("设备", config.whisper.device)
        table.add_row("语言", config.whisper.language)
        table.add_row("输出目录", str(config.output.dir))
        table.add_row("保留音频", str(config.output.save_audio))
        table.add_row("断点续传", str(config.download.resume_download))
        table.add_row("并发下载数", str(config.download.max_concurrent))
        table.add_row("OpenAI API", "已配置" if config.openai.api_key else "未配置")
        table.add_row("LLM模型", config.openai.model)
        table.add_row("LLM结构化", "启用" if config.structured.enable else "禁用")
        table.add_row("WhisperX批大小", str(config.whisper.batch_size))
        table.add_row("词级对齐", "启用" if config.whisper.enable_alignment else "禁用")
        table.add_row("说话人分离", "启用" if config.whisper.diarize else "禁用")
        table.add_row(
            "HuggingFace Token", "已配置" if config.whisper.hf_token else "未配置"
        )

        console.print(table)
        console.print("\n[cyan]配置文件路径:[/cyan]", config.get_config_path())

    if reset:
        config_file = Path.home() / ".podcli" / "config.yaml"
        if config_file.exists():
            config_file.unlink()
        console.print("[green]配置已重置，请重新运行命令[/green]")


@cli.command()
@click.argument("feed_url")
@click.option("--latest", is_flag=True, help="获取最新单集")
@click.option("--limit", default=5, help="限制单集数量")
def struct(feed_url, latest, limit):
    """获取播客单集，使用LLM生成结构化Markdown"""
    console.print(f"[cyan]LLM结构化处理: {feed_url}[/cyan]")

    if not config.openai.api_key:
        console.print("[red]请先配置OpenAI API密钥: podcli config[/red]")
        return

    with console.status("[bold cyan]正在解析RSS...[/bold cyan]"):
        parser = RSSParser()
        podcast = parser.get_podcast(feed_url)

    if not podcast or not podcast.episodes:
        console.print("[yellow]未找到播客单集[/yellow]")
        return

    if latest:
        target_episode = podcast.episodes[0]
        console.print(f"\n[green]选择最新单集:[/green] {target_episode.title}")
    else:
        select_items = [
            format_episode_for_display(ep, i)
            for i, ep in enumerate(podcast.episodes[:limit])
        ]
        selected_item = interactive_select(select_items, title="播客单集", limit=limit)

        if not selected_item:
            return

        selected_index = select_items.index(selected_item)
        target_episode = podcast.episodes[selected_index]
        console.print(f"\n[green]已选择单集:[/green] {target_episode.title}")

    audio_url = target_episode.audio_url
    if not audio_url:
        console.print("[red]未找到音频链接[/red]")
        return

    downloaded = download_audio(audio_url, target_episode.title)
    if not downloaded:
        console.print("[red]下载失败[/red]")
        return

    _do_struct(downloaded, target_episode, podcast, feed_url)


@cli.command()
def status():
    """显示系统状态"""
    table = Table(title="系统状态")
    table.add_column("组件", style="cyan")
    table.add_column("状态", style="green")

    import torch

    table.add_row("PyTorch版本", torch.__version__)
    table.add_row("CUDA可用", str(torch.cuda.is_available()))
    if torch.cuda.is_available():
        table.add_row("GPU", torch.cuda.get_device_name(0))

    try:
        import whisperx

        table.add_row("WhisperX", "已安装")
    except ImportError:
        table.add_row("WhisperX", "未安装")

    try:
        import ffmpeg

        table.add_row("FFmpeg", "已安装")
    except ImportError:
        table.add_row("FFmpeg", "未安装")

    cache_manager = ModelCacheManager()
    table.add_row("模型缓存", cache_manager.get_cache_size())

    console.print(table)


if __name__ == "__main__":
    cli()
