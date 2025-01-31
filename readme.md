# 粤语学习与字幕生成助手

这是一个专门为学习粤语的人设计的工具，主要提供两个核心功能：
1. 为粤语YouTube视频自动生成粤语字幕
2. 实时识别粤语对话并生成字幕，同时翻译成普通话（开发中）

## 功能特点

### YouTube视频粤语字幕生成
- 自动下载YouTube视频和音频
- 使用阿里云SenseVoice大模型进行粤语语音识别
- 生成准确的粤语字幕（持续优化中）

### 实时粤语识别与翻译（开发中）
- 使用OpenAI Whisper进行实时粤语语音识别
- 通过阿里云Qwen-Max大模型将粤语翻译成普通话
- 实时显示双语字幕

## 技术栈

- **视频处理**：
  - yt-dlp：YouTube视频下载工具

- **语音识别**：
  - 阿里云SenseVoice：用于视频的粤语识别
  - OpenAI Whisper：用于实时粤语识别

- **机器翻译**：
  - 阿里云Qwen-Max：粤语到普通话的翻译

- **存储服务**：
  - 阿里云OSS：音视文件存储

## 环境要求

1. Python 3.x
2. 相关依赖包（详见 requirements.txt）
3. 阿里云账号（用于SenseVoice和OSS服务）
4. OpenAI API密钥（用于Whisper服务）

## 快速开始

1. 克隆项目
```bash
git clone [项目地址]
cd [项目目录]
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，填入相应的API密钥和配置信息
```

## 使用说明

### YouTube视频字幕生成
```python
# 使用示例代码
python main.py
```

### 实时语音识别（开发中）
```python
# 使用示例代码
python openWisper.py
```

## 注意事项

- 目前粤语字幕的准确度还在持续优化中
- 实时识别功能仍在开发阶段
- 使用前请确保已正确配置所有必要的API密钥

## 贡献指南

欢迎提交Issue和Pull Request来帮助改进项目。


## 联系方式

如有问题或建议，请通过以下方式联系：
- GitHub Issues
- email: jasonzhouu@gmail.com
