# whisper-toolkit

Windows 语音转文字工具：Whisper large-v3 文件转写、SenseVoice 快速转写、Fun-ASR-Nano 逐句修正，以及麦克风/电脑声音实时转写。默认面向 NVIDIA GPU，支持 CPU 模式。

实时输出保留时间前缀，正文不加序号；只更新当前识别行，定稿后追加到终端，避免反复清屏闪烁。实时记录保存到 `transcripts/`。

## 安装

准备 64 位 Python 3.14、Git、ffmpeg，并将它们加入 PATH。当前依赖版本与本项目原运行环境一致。

```powershell
git clone https://github.com/AO2233/whisper-toolkit.git
cd whisper-toolkit
.\setup.cmd
```

`setup.cmd` 创建 `sensevoice/.venv`、安装固定版本依赖，从上游下载权重并校验 SHA-256。所有模型约占 7.7 GiB；下载解包需要额外临时空间，建议留出 16 GiB。已有且校验通过的权重会复用，失败后可重新运行。

GPU 模式需要支持 CUDA 12 的 NVIDIA 驱动，Python 运行时所需的 CUDA/cuDNN DLL 由依赖包提供。仅使用 CPU 或只安装快速转写：

```powershell
.\setup.cmd -Cpu -Models sensevoice
.\sensevoice.cmd recording.mp3 --cpu
.\realtime.cmd --cpu
```

在 PowerShell 中选择多组模型：

```powershell
.\setup.ps1 -Models sensevoice,nano
```

### Whisper 编译

Whisper 的三个文件转写入口还需要 Visual Studio C++ Build Tools、CMake、Ninja，以及 GPU 模式的 CUDA Toolkit。原环境使用 VS 2026、CUDA 13.x、RTX 5080。

```powershell
.\build.cmd                  # CUDA，默认架构 sm_120
# CPU 编译：.\build.cmd cpu
# 其他 GPU：先设置 $env:CUDA_ARCHITECTURES = '89' 等对应架构
```

首次编译自动从 [whisper.cpp 上游](https://github.com/ggml-org/whisper.cpp) 拉取源码，并检出 `whisper-version.txt` 中记录的提交。已有源码目录会保留。第三方源码和编译产物不复制进本仓库。

## 选择入口

文件可以直接拖到对应 `.cmd`，也可以传入文件或文件夹路径。文件转写默认在源文件旁输出 `.srt` 和 `.txt`。

| 用途 | 入口 | 模型 |
|---|---|---|
| 多语言录音/视频转写 | `whisper.cmd` | Whisper large-v3 + Silero VAD |
| 简体中文字幕 | `subtitle-zh.cmd` | Whisper，固定中文和标点提示 |
| 外语语音翻译为英文字幕 | `translate-en.cmd` | Whisper 英文翻译 |
| 中/日/英/粤语逐句修正 | `funasr.cmd` | SenseVoice + Fun-ASR-Nano |
| 中/英/日/韩/粤快速转写 | `sensevoice.cmd` | SenseVoiceSmall |
| 麦克风实时转写 | `realtime.cmd` | SenseVoice + 可选 Nano |
| 电脑播放声音实时转写 | `realtime-system.cmd` | WASAPI loopback + 同上 |

```powershell
.\whisper.cmd meeting.m4a
.\whisper.cmd D:\videos -Lang zh
.\whisper.cmd talk.mp4 -Lang en -Format srt,vtt,json
.\whisper.cmd a.mp3 -Prompt "Kubernetes, Anthropic, 张三"
.\whisper.cmd a.wav -Cpu
.\sensevoice.cmd meeting.m4a --lang zh
.\sensevoice.cmd D:\audio --format srt,txt --outdir D:\out
.\funasr.cmd recording.mp3
.\realtime-system.cmd --lang ja
.\realtime.cmd --list-devices
.\realtime.cmd --device 13
.\realtime.cmd --silence 0.8
.\realtime.cmd --fast
```

Whisper 参数：`-Lang`、`-Format`（txt/srt/vtt/lrc/csv/json/words）、`-Prompt`、`-BeamSize`、`-OutDir`、`-NoVad`、`-Translate`、`-Cpu`。

SenseVoice/Fun-ASR 参数：`--lang`、`--format`、`--outdir`、`--cpu`、`--int8`、`--batch`。实时入口另支持 `--device`、`--list-devices`、`--silence`、`--outdir`、`--fast`；`realtime-system.cmd --device airpods` 按扬声器名称选择设备。

实时识别约每 0.2 秒更新一次当前句子；停顿后由 VAD 切句并定稿。过长的临时识别只显示末尾一行，定稿和记录保留完整句子。Nano 只修正中/日/英/粤，差异过大时保留 SenseVoice 结果；`--fast` 或 `--cpu` 关闭实时 Nano 修正。

## 权重下载与校验

权重不上传 GitHub，也不使用 Git LFS。下载地址、文件大小和 SHA-256 记录在 `scripts/models.json`。

```powershell
python scripts/download_models.py --list
python scripts/download_models.py --only sensevoice
python scripts/download_models.py --only nano       # 同时准备 SenseVoice 和 VAD
python scripts/download_models.py --only whisper
python scripts/download_models.py --check           # 仅校验，不下载
```

下载器只保留运行必需的权重、词表、分词器与模型许可证，不解包测试音频。校验失败不会覆盖原文件。

上游来源：[SenseVoice 模型](https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html)、[Fun-ASR-Nano 模型](https://k2-fsa.github.io/sherpa/onnx/funasr-nano/pretrained.html)、[Sherpa VAD](https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models)、[Whisper 权重](https://huggingface.co/ggerganov/whisper.cpp)、[Whisper VAD](https://huggingface.co/ggml-org/whisper-vad)。各模型和第三方项目的许可证以各自上游为准。

## 维护与验证

`update.cmd` 将本地 whisper.cpp 快进到上游最新 master，更新 `whisper-version.txt` 后重新编译。CPU 编译使用 `update.cmd cpu`。

```powershell
python -m unittest discover -s sensevoice -p "test_*.py" -v
python -m unittest discover -s scripts -p "test_*.py" -v
```

测试无需模型或第三方 Python 依赖；GitHub Actions 运行同样的测试。

仓库仅保存入口脚本、Python 源码、依赖清单、测试、模型下载清单和文档。`models/`、`.venv/`、`whisper.cpp/`、缓存和个人转写记录均被忽略；本地清理保留已安装运行环境及现有转写记录。
