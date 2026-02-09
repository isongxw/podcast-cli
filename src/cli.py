#!/usr/bin/env python3
"""
podcli - 极简播客转录工具

命令：
  search <关键词>              # 搜索播客
  search <关键词> --episode    # 搜索单集名称
  episodes <feed-url>          # 列出单集
  transcribe <音频URL或文件>    # 转录为 Markdown
  get <feed-url> --latest      # 下载最新单集并转录
"""

import click
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from itunes import iTunesSearch
from rss import RSSParser
from download import AudioDownloader
from transcribe import WhisperTranscriber
from markdown import MarkdownGenerator

# Rich库导入
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.progress import Progress
from rich.prompt import Prompt
from rich import box
from rich.style import Style

# 全局控制台实例
console = Console()

# 交互式选择函数
def interactive_select(items, title="选择", limit=5):
    """
    交互式选择函数
    :param items: 可选择的项目列表
    :param title: 选择标题
    :param limit: 限制显示数量
    :return: 选择的项目或None
    """
    from rich import get_console
    from rich.text import Text
    from rich.panel import Panel
    import sys
    import tty
    import termios
    
    console = get_console()
    selected_index = 0
    items = items[:limit]  # 限制显示数量
    
    if not items:
        console.print("[yellow]没有找到匹配的结果[/yellow]")
        return None
    
    def getch():
        """获取单个字符输入"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    
    def render():
        """渲染选择界面"""
        # 清除屏幕
        console.clear()
        
        # 标题面板
        title_panel = Panel(
            Text(title, style="bold cyan"),
            border_style="green",
            box=box.ROUNDED
        )
        console.print(title_panel)
        
        # 选项面板
        options_text = Text()
        for i, item in enumerate(items):
            if i == selected_index:
                # 选中项 - 使用append方法并传入style参数
                options_text.append(f"▶ {i+1}. {item}", style="bold reverse")
                options_text.append("\n")
            else:
                # 未选中项
                options_text.append(f"  {i+1}. {item}\n")
        
        # 提示信息
        options_text.append("\n")
        options_text.append("使用 ↑↓ 键导航，Enter 键选择，Esc 键取消", style="cyan")
        
        options_panel = Panel(
            options_text,
            border_style="blue",
            box=box.ROUNDED
        )
        console.print(options_panel)
    
    try:
        while True:
            render()
            
            # 获取用户输入
            ch = getch()
            
            # 处理方向键
            if ch == '\x1b':  # ESC
                # 方向键前缀
                ch2 = getch()
                if ch2 == '[':
                    ch3 = getch()
                    if ch3 == 'A':  # 上箭头
                        selected_index = (selected_index - 1) % len(items)
                    elif ch3 == 'B':  # 下箭头
                        selected_index = (selected_index + 1) % len(items)
                else:
                    # ESC键
                    console.print("[yellow]取消选择[/yellow]")
                    return None
            elif ch == '\r':  # Enter键
                # 选择当前项
                console.clear()
                console.print(f"[green]已选择: {items[selected_index]}[/green]")
                return items[selected_index]
            elif ch == 'q' or ch == 'Q':
                # 退出
                console.print("[yellow]取消选择[/yellow]")
                return None
    except KeyboardInterrupt:
        console.print("[yellow]取消选择[/yellow]")
        return None

@click.group()
def cli():
    """podcli - 极简播客转录工具"""
    pass

@cli.command()
@click.argument('keyword')
@click.option('--limit', default=5, help='限制搜索结果数量')
@click.option('--episode', is_flag=True, help='搜索单集名称')
def search(keyword, limit, episode):
    """搜索播客或单集"""
    if episode:
        # 搜索单集
        console.print(f"[cyan]搜索单集: {keyword}[/cyan]")
        
        # 显示加载状态
        with console.status("[bold cyan]正在搜索单集...[/bold cyan]"):
            searcher = iTunesSearch()
            results = searcher.search_podcasts(keyword)
        
        if not results:
            console.print("[yellow]未找到匹配的播客[/yellow]")
            return
        
        # 获取所有播客的单集
        all_episodes = []
        podcast_names = []
        
        with console.status("[bold cyan]正在获取单集信息...[/bold cyan]"):
            for result in results[:limit]:
                feed_url = result.get('feedUrl')
                if feed_url:
                    parser = RSSParser()
                    episodes = parser.get_episodes(feed_url)
                    podcast_name = result.get('collectionName', '未知名称')
                    
                    for ep in episodes:
                        title = ep.get('title', '无标题')
                        # 检查是否包含关键词
                        if keyword.lower() in title.lower():
                            all_episodes.append(ep)
                            podcast_names.append(podcast_name)
        
        if not all_episodes:
            console.print("[yellow]未找到匹配的单集[/yellow]")
            return
        
        # 准备选择列表
        select_items = []
        for i, episode in enumerate(all_episodes[:limit]):
            title = episode.get('title', '无标题')
            podcast_name = podcast_names[i]
            select_items.append(f"{title} - {podcast_name}")
        
        # 交互式选择
        selected_item = interactive_select(select_items, title="单集搜索结果", limit=limit)
        
        if not selected_item:
            return
        
        # 找到对应的单集
        selected_index = select_items.index(selected_item)
        selected_episode = all_episodes[selected_index]
        
        # 显示选中的单集信息
        console.print(f"\n[green]已选择单集:[/green]")
        console.print(f"  [bold]标题:[/bold] {selected_episode.get('title', '无标题')}")
        console.print(f"  [bold]播客:[/bold] {podcast_names[selected_index]}")
        
        # 检查是否有音频链接
        audio_url = selected_episode.get('enclosure', {}).get('url')
        if not audio_url:
            console.print("[red]该单集没有音频链接[/red]")
            return
        
        console.print(f"  [bold]音频链接:[/bold] {audio_url}")
        
        # 提供操作选项
        action_items = [
            "下载音频",
            "转录音频",
            "下载并转录",
            "返回"
        ]
        
        action = interactive_select(action_items, title="选择操作")
        
        if not action:
            return
        
        # 执行相应操作
        if action == "下载音频":
            download_audio(audio_url, selected_episode.get('title', '未知标题'))
        elif action == "转录音频":
            transcribe_audio(audio_url, selected_episode.get('title', '未知标题'))
        elif action == "下载并转录":
            download_audio(audio_url, selected_episode.get('title', '未知标题'))
            transcribe_audio(audio_url, selected_episode.get('title', '未知标题'))
    else:
        # 搜索播客
        console.print(f"[cyan]搜索播客: {keyword}[/cyan]")
        
        # 显示加载状态
        with console.status("[bold cyan]正在搜索播客...[/bold cyan]"):
            searcher = iTunesSearch()
            results = searcher.search_podcasts(keyword)
        
        if not results:
            console.print("[yellow]未找到匹配的播客[/yellow]")
            return
        
        # 准备选择列表
        select_items = []
        for result in results[:limit]:
            collection_name = result.get('collectionName', '未知名称')
            artist_name = result.get('artistName', '未知作者')
            select_items.append(f"{collection_name} - {artist_name}")
        
        # 交互式选择
        selected_item = interactive_select(select_items, title="搜索结果", limit=limit)
        
        if not selected_item:
            return
        
        # 找到对应的播客结果
        selected_index = select_items.index(selected_item)
        selected_podcast = results[selected_index]
        
        # 显示选中的播客信息
        console.print(f"\n[green]已选择播客:[/green]")
        console.print(f"  [bold]名称:[/bold] {selected_podcast.get('collectionName', '未知名称')}")
        console.print(f"  [bold]作者:[/bold] {selected_podcast.get('artistName', '未知作者')}")
        
        # 获取feedUrl
        feed_url = selected_podcast.get('feedUrl')
        if not feed_url:
            console.print("[red]该播客没有订阅地址[/red]")
            return
        
        console.print(f"  [bold]订阅地址:[/bold] {feed_url}")
        
        # 自动执行episodes命令
        console.print("\n[cyan]正在获取播客单集...[/cyan]")
        # 直接调用逻辑函数而不是Click命令
        _episodes_logic(feed_url, limit=limit)

def _episodes_logic(feed_url, limit=5):
    """
    单集管理逻辑
    :param feed_url: 播客订阅地址
    :param limit: 限制单集数量
    """
    console.print(f"[cyan]获取播客单集: {feed_url}[/cyan]")
    
    # 显示加载状态
    with console.status("[bold cyan]正在获取单集信息...[/bold cyan]"):
        parser = RSSParser()
        episodes = parser.get_episodes(feed_url)
    
    if not episodes:
        console.print("[yellow]未找到播客单集[/yellow]")
        return
    
    # 准备选择列表
    select_items = []
    for episode in episodes[:limit]:
        title = episode.get('title', '无标题')
        pub_date = episode.get('pubDate', '未知日期')
        select_items.append(f"{title} - {pub_date}")
    
    # 交互式选择
    selected_item = interactive_select(select_items, title="播客单集", limit=limit)
    
    if not selected_item:
        return
    
    # 找到对应的单集
    selected_index = select_items.index(selected_item)
    selected_episode = episodes[selected_index]
    
    # 显示选中的单集信息
    console.print(f"\n[green]已选择单集:[/green]")
    console.print(f"  [bold]标题:[/bold] {selected_episode.get('title', '无标题')}")
    console.print(f"  [bold]发布日期:[/bold] {selected_episode.get('pubDate', '未知日期')}")
    
    # 检查是否有音频链接
    audio_url = selected_episode.get('enclosure', {}).get('url')
    if not audio_url:
        console.print("[red]该单集没有音频链接[/red]")
        return
    
    console.print(f"  [bold]音频链接:[/bold] {audio_url}")
    
    # 提供操作选项
    action_items = [
        "下载音频",
        "转录音频",
        "下载并转录",
        "返回"
    ]
    
    action = interactive_select(action_items, title="选择操作")
    
    if not action:
        return
    
    # 执行相应操作
    if action == "下载音频":
        download_audio(audio_url, selected_episode.get('title', '未知标题'))
    elif action == "转录音频":
        transcribe_audio(audio_url, selected_episode.get('title', '未知标题'))
    elif action == "下载并转录":
        download_audio(audio_url, selected_episode.get('title', '未知标题'))
        transcribe_audio(audio_url, selected_episode.get('title', '未知标题'))
    # "返回"选项则直接结束

@cli.command()
@click.argument('feed_url')
@click.option('--limit', default=5, help='限制单集数量')
def episodes(feed_url, limit):
    """列出播客单集"""
    _episodes_logic(feed_url, limit)

def download_audio(audio_url, title):
    """
    下载音频
    :param audio_url: 音频URL
    :param title: 音频标题
    """
    console.print(f"\n[cyan]开始下载音频: {title}[/cyan]")
    
    config = Config()
    downloader = AudioDownloader(config.output_dir)
    
    with console.status("[bold cyan]正在下载音频...[/bold cyan]"):
        audio_file = downloader.download_audio(audio_url)
    
    if audio_file:
        console.print(f"[green]下载完成: {audio_file}[/green]")
    else:
        console.print("[red]音频下载失败[/red]")

def transcribe_audio(audio_source, title):
    """
    转录音频
    :param audio_source: 音频源（URL或文件路径）
    :param title: 音频标题
    """
    console.print(f"\n[cyan]开始转录音频: {title}[/cyan]")
    
    config = Config()
    
    # 下载音频（如果是URL）
    downloader = AudioDownloader(config.output_dir)
    if audio_source.startswith('http'):
        with console.status("[bold cyan]正在下载音频...[/bold cyan]"):
            audio_file = downloader.download_audio(audio_source)
        if not audio_file:
            console.print("[red]音频下载失败[/red]")
            return
    else:
        audio_file = Path(audio_source)
        if not audio_file.exists():
            console.print("[red]音频文件不存在[/red]")
            return
    
    # 转录音频
    transcriber = WhisperTranscriber(
        model_size=config.whisper_model,
        device=config.whisper_device,
        language=config.whisper_language
    )
    
    console.print("[cyan]加载模型...[/cyan]")
    if not transcriber.load_model():
        console.print("[red]模型加载失败[/red]")
        return
    
    console.print("[cyan]开始转录...[/cyan]")
    result = transcriber.transcribe_audio(audio_file)
    
    if result.error:
        console.print(f"[red]转录失败: {result.error}[/red]")
        return
    
    # 生成Markdown
    generator = MarkdownGenerator(config.output_dir)
    md_file = generator.generate(
        result=result,
        title=title,
        podcast="未知播客",
        audio_source=audio_source
    )
    
    console.print(f"\n[green]转录完成！[/green]")
    console.print(f"[bold]Markdown文件:[/bold] {md_file}")
    
    # 清理临时文件
    if audio_source.startswith('http') and not config.save_audio:
        downloader.cleanup(audio_file)

@cli.command()
@click.argument('audio_source')
@click.option('--title', default=None, help='播客标题')
@click.option('--podcast', default=None, help='播客名称')
def transcribe(audio_source, title, podcast):
    """转录音频为Markdown"""
    console.print(f"[cyan]转录音频: {audio_source}[/cyan]")
    
    # 初始化配置
    config = Config()
    
    # 下载音频文件（如果是URL）
    downloader = AudioDownloader(config.output_dir)
    if audio_source.startswith('http'):
        with console.status("[bold cyan]正在下载音频...[/bold cyan]"):
            audio_file = downloader.download_audio(audio_source)
        if not audio_file:
            console.print("[red]音频下载失败[/red]")
            return
    else:
        audio_file = Path(audio_source)
        if not audio_file.exists():
            console.print("[red]音频文件不存在[/red]")
            return
    
    # 转录音频
    transcriber = WhisperTranscriber(
        model_size=config.whisper_model,
        device=config.whisper_device,
        language=config.whisper_language
    )
    
    console.print("[cyan]加载模型...[/cyan]")
    if not transcriber.load_model():
        console.print("[red]模型加载失败[/red]")
        return
    
    console.print("[cyan]开始转录...[/cyan]")
    result = transcriber.transcribe_audio(audio_file)
    
    if result.error:
        console.print(f"[red]转录失败: {result.error}[/red]")
        return
    
    # 生成Markdown
    generator = MarkdownGenerator(config.output_dir)
    md_file = generator.generate(
        result=result,
        title=title or Path(audio_file).stem,
        podcast=podcast or "未知播客",
        audio_source=audio_source
    )
    
    console.print(f"\n[green]转录完成！[/green]")
    console.print(f"[bold]Markdown文件:[/bold] {md_file}")
    
    # 清理临时文件
    if audio_source.startswith('http') and not config.save_audio:
        downloader.cleanup(audio_file)

@cli.command()
@click.argument('feed_url')
@click.option('--latest', is_flag=True, help='获取最新单集')
@click.option('--limit', default=5, help='限制单集数量')
def get(feed_url, latest, limit):
    """获取播客单集并转录"""
    console.print(f"[cyan]获取播客: {feed_url}[/cyan]")
    
    # 初始化配置
    config = Config()
    
    # 解析RSS
    with console.status("[bold cyan]正在解析RSS...[/bold cyan]"):
        parser = RSSParser()
        episodes = parser.get_episodes(feed_url)
    
    if not episodes:
        console.print("[yellow]未找到播客单集[/yellow]")
        return
    
    # 获取最新单集
    if latest:
        target_episode = episodes[0]
        console.print(f"\n[green]获取最新单集:[/green] {target_episode.get('title', '无标题')}")
    else:
        # 显示单集列表供选择
        select_items = []
        for episode in episodes[:limit]:
            title = episode.get('title', '无标题')
            pub_date = episode.get('pubDate', '未知日期')
            select_items.append(f"{title} - {pub_date}")
        
        # 交互式选择
        selected_item = interactive_select(select_items, title="播客单集", limit=limit)
        
        if not selected_item:
            return
        
        # 找到对应的单集
        selected_index = select_items.index(selected_item)
        target_episode = episodes[selected_index]
        
        console.print(f"\n[green]已选择单集:[/green] {target_episode.get('title', '无标题')}")
    
    # 下载音频
    audio_url = target_episode.get('enclosure', {}).get('url')
    if not audio_url:
        console.print("[red]未找到音频链接[/red]")
        return
    
    downloader = AudioDownloader(config.output_dir)
    with console.status("[bold cyan]正在下载音频...[/bold cyan]"):
        audio_file = downloader.download_audio(audio_url)
    
    if not audio_file:
        console.print("[red]音频下载失败[/red]")
        return
    
    # 转录音频
    transcriber = WhisperTranscriber(
        model_size=config.whisper_model,
        device=config.whisper_device,
        language=config.whisper_language
    )
    
    console.print("[cyan]加载模型...[/cyan]")
    if not transcriber.load_model():
        console.print("[red]模型加载失败[/red]")
        return
    
    console.print("[cyan]开始转录...[/cyan]")
    result = transcriber.transcribe_audio(audio_file)
    
    if result.error:
        console.print(f"[red]转录失败: {result.error}[/red]")
        return
    
    # 生成Markdown
    generator = MarkdownGenerator(config.output_dir)
    md_file = generator.generate(
        result=result,
        title=target_episode.get('title', Path(audio_file).stem),
        podcast=parser.get_podcast_title(feed_url) or "未知播客",
        audio_source=audio_url
    )
    
    console.print(f"\n[green]完成！[/green]")
    console.print(f"[bold]Markdown文件:[/bold] {md_file}")
    
    # 清理临时文件
    if not config.save_audio:
        downloader.cleanup(audio_file)

if __name__ == '__main__':
    cli()
