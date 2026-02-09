# podcli - 极简播客转录工具

podcli是一个功能完整的播客处理命令行工具，提供iTunes播客搜索、音频下载和音频转译等功能。它可以将播客音频自动转录为Markdown格式的文本，支持多种语言和模型大小。

## 核心功能

- **播客搜索**：通过iTunes API搜索全球播客
- **单集列表**：获取并显示播客的所有单集信息
- **音频下载**：自动下载播客音频文件
- **音频转录**：使用Whisper模型将音频转录为文本
- **Markdown生成**：将转录结果格式化为标准Markdown文件
- **进度显示**：实时显示转录进度和预计剩余时间

## 环境要求

- Python 3.10 或更高版本
- FFmpeg（用于音频处理）
- CUDA（可选，用于GPU加速）

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd podcli
```

### 2. 安装依赖

使用pip安装：

```bash
pip install -e .
```

或使用uv安装：

```bash
uv sync
```

### 3. 安装FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
从[FFmpeg官网](https://ffmpeg.org/download.html)下载并安装。

### 4. 配置（可选）

创建配置文件 `~/.podcli/config.yaml`：

```yaml
whisper:
  model: base          # tiny/base/small/medium/large
  device: cpu          # cpu/cuda
  language: auto        # auto/en/zh 等

output:
  dir: ~/Podcasts      # 输出根目录
  save_audio: true     # 是否保留音频文件
```

## 使用方法

### 命令行参数

```bash
podcli [OPTIONS] COMMAND [ARGS]...
```

### 搜索播客

```bash
# 搜索播客
podcli search "python podcast"

# 搜索特定播客
podcli search "real python"
```

### 列出播客单集

```bash
# 列出所有单集
podcli episodes "https://realpython.com/podcasts/rpp/feed"

# 列出单集（显示前10个）
podcli episodes "https://feeds.fireside.fm/pythonoutloud/rss"
```

### 转录音频

```bash
# 转录网络音频
podcli transcribe "https://example.com/audio.mp3" \
  --title "播客标题" \
  --podcast "播客名称"

# 转录本地音频文件
podcli transcribe "/path/to/audio.mp3" \
  --title "播客标题" \
  --podcast "播客名称"
```

### 获取并转录单集

```bash
# 获取最新单集并转录
podcli get "https://realpython.com/podcasts/rpp/feed" --latest

# 选择特定单集并转录
podcli get "https://realpython.com/podcasts/rpp/feed"
```

## 命令详解

### search

搜索播客并显示结果。

```bash
podcli search <关键词>
```

**参数：**
- `keyword`：搜索关键词

**示例：**
```bash
podcli search "python"
podcli search "technology"
```

### episodes

列出播客的所有单集。

```bash
podcli episodes <feed-url>
```

**参数：**
- `feed_url`：播客的RSS订阅地址

**示例：**
```bash
podcli episodes "https://realpython.com/podcasts/rpp/feed"
```

### transcribe

转录音频文件为Markdown。

```bash
podcli transcribe <audio-source> [OPTIONS]
```

**参数：**
- `audio_source`：音频URL或本地文件路径

**选项：**
- `--title TEXT`：播客标题（可选）
- `--podcast TEXT`：播客名称（可选）

**示例：**
```bash
# 转录网络音频
podcli transcribe "https://example.com/audio.mp3" \
  --title "Episode 1" \
  --podcast "My Podcast"

# 转录本地文件
podcli transcribe "/path/to/audio.mp3"
```

### get

获取播客单集并转录。

```bash
podcli get <feed-url> [OPTIONS]
```

**参数：**
- `feed_url`：播客的RSS订阅地址

**选项：**
- `--latest`：获取最新单集（无需选择）

**示例：**
```bash
# 获取最新单集
podcli get "https://realpython.com/podcasts/rpp/feed" --latest

# 选择单集
podcli get "https://realpython.com/podcasts/rpp/feed"
```

## 配置说明

### Whisper模型配置

podcli支持多种Whisper模型大小：

| 模型 | 大小 | 速度 | 准确率 |
|------|------|------|--------|
| tiny | ~39MB | 最快 | 较低 |
| base | ~74MB | 快 | 中等 |
| small | ~244MB | 中等 | 较高 |
| medium | ~769MB | 慢 | 高 |
| large | ~1550MB | 最慢 | 最高 |

**配置示例：**

```yaml
whisper:
  model: base          # 选择模型大小
  device: cuda         # 使用GPU加速
  language: zh         # 指定语言（自动检测）
```

### 输出配置

```yaml
output:
  dir: ~/Podcasts      # 输出目录
  save_audio: true     # 保留音频文件
```

## 输出格式

转录结果会生成Markdown文件，包含以下结构：

```markdown
# [播客标题]

**播客名称**: [播客名称]  
**音频来源**: [音频URL或文件路径]  
**转录时间**: [时间戳]  
**语言**: [检测到的语言]  
**时长**: [音频时长]

## 转录内容

[转录的文本内容]
```

## 常见问题

### 1. FFmpeg未找到

**问题：** 运行时提示FFmpeg未找到

**解决方案：** 安装FFmpeg并确保其在PATH中

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# 从官网下载并添加到PATH
```

### 2. CUDA不可用

**问题：** 配置为CUDA但提示CUDA不可用

**解决方案：** 
- 确保安装了CUDA Toolkit
- 安装PyTorch的CUDA版本
- 或将配置改为使用CPU

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3. 转录速度慢

**问题：** 转录速度较慢

**解决方案：**
- 使用更小的Whisper模型（tiny或base）
- 使用GPU加速（如果可用）
- 减少音频分割时长

### 4. 内存不足

**问题：** 长音频转录时内存不足

**解决方案：**
- 使用更小的模型
- 增加音频分割时长
- 关闭其他占用内存的程序

### 5. 下载失败

**问题：** 音频下载失败

**解决方案：**
- 检查网络连接
- 确认音频URL有效
- 尝试使用本地文件

## 故障排除

### 查看详细日志

podcli使用loguru进行日志记录，如需查看详细日志，可以修改代码中的日志级别。

### 清理临时文件

临时文件存储在 `temp` 目录中，可以手动清理：

```bash
rm -rf temp/*
```

### 重置配置

删除配置文件以恢复默认设置：

```bash
rm ~/.podcli/config.yaml
```

## 项目结构

```
podcli/
├── src/
│   ├── cli.py              # CLI命令入口
│   ├── config.py           # 配置管理
│   ├── itunes.py           # iTunes搜索
│   ├── rss.py              # RSS解析
│   ├── download.py         # 音频下载
│   ├── transcribe.py       # 音频转录
│   └── markdown.py         # Markdown生成
├── pyproject.toml          # 项目配置
├── README.md               # 项目文档
├── downloads/              # 下载的音频
├── transcripts/            # 转录结果
└── temp/                   # 临时文件
```

## 贡献指南

欢迎贡献！请遵循以下步骤：

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 许可证

本项目采用MIT许可证。详见 [LICENSE](LICENSE) 文件。

## 致谢

- [Whisper](https://github.com/openai/whisper) - OpenAI的语音识别模型
- [Click](https://click.palletsprojects.com/) - Python命令行界面创建工具
- [iTunes Search API](https://affiliate.itunes.apple.com/resources/documentation/itunes-store-web-service-search-api/) - 播客搜索API

## 联系方式

如有问题或建议，请提交Issue或Pull Request。
