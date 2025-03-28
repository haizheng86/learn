# 多模态内容助手

一款基于Python标准库和大模型API的智能内容分析与创意生成工具，集成了文本分析、图像识别、音视频处理等多种功能，帮助内容创作者提升创作效率和内容质量。

## 功能特点

### 1. 多模态内容分析
- **文本分析**
  - 关键词提取和主题识别
  - 情感倾向分析（积极/消极/中性）
  - 文本结构分析（段落、句子长度等）
  - 语言检测和统计信息
  - 基于大模型的深度内容理解
  - 时间戳提取与识别

- **图像分析**
  - 图像内容识别和场景分类
  - 物体检测和主题提取（集成YOLO模型）
  - 色彩分析和图像质量评估
  - OCR文字识别（支持中英文，集成Tesseract）
  - 基于Vision模型的智能描述
  - 图像格式与尺寸分析

- **音频分析**
  - 语音转文字（使用Whisper模型）
  - 音频波形和频谱分析
  - 音频质量评估与格式分析
  - 多语言支持
  - 音频内容理解和摘要
  - 音频时长与采样率分析

- **视频分析**
  - 关键帧提取和分析
  - 场景识别和分类
  - 视频内容摘要生成
  - 音视频分离处理
  - 智能内容推荐
  - 视频分辨率与码率分析

### 2. 智能建议生成
- 基于内容分析的个性化建议
- 创意优化和改进方向
- 内容质量评估报告
- 目标受众分析
- SEO优化建议
- 平台适配性建议

### 3. 系统架构

#### 整体架构设计
系统采用层次化模块设计，自底向上包括：
1. **基础分析层**：负责原始内容的处理与特征提取
2. **智能分析层**：集成AI模型，提供高级语义理解
3. **业务处理层**：协调多模态分析流程，聚合结果
4. **应用接口层**：提供Web服务与命令行接口

#### 核心模块
- **TextAnalyzer**: 文本分析引擎
  - 构建了完整的文本分析流水线，支持多种文本特征提取
  - 优雅降级机制：在无法访问NLTK或外部API时自动切换到本地简化分析
  - 支持中英文双语分析，可检测文本语言
  - 实现了关键词提取、情感分析、时间戳提取等多种功能
  - 提供全面的文本统计信息（字数、句长、单词长度等）

- **MediaProcessor**: 媒体处理引擎
  - 实现了自动文件类型检测，支持30+种文件格式
  - 针对不同媒体类型实现专用分析管道
  - 图像处理：支持色彩分析、格式识别、内容识别、OCR等功能
  - 音频处理：波形分析、频谱生成、语音转文本等功能
  - 视频处理：关键帧提取、场景分类、音视频分离等功能
  - 内置回退机制：当外部依赖不可用时提供基本功能

- **AIService**: AI服务集成
  - 统一的AI服务接口，支持文本、图像等多种内容分析
  - 可配置的API连接（支持自定义基础URL和模型选择）
  - 智能降级：API不可用时自动切换到本地处理模式
  - 支持OpenAI最新的模型，包含Vision和Chat Completion API
  - 实现了结构化结果解析，将AI响应转为标准格式
  - 提供智能建议生成功能，基于内容分析结果

- **ContentProcessor**: 内容处理协调器
  - 作为不同处理模块的调度中心，协调分析流程
  - 实现了统一的文件处理入口，自动路由到相应模块
  - 支持多种输出格式（JSON、HTML、文本）
  - 提供错误处理与恢复机制，确保分析流程稳定性
  - 结果聚合与格式化，提供标准化的输出接口

- **MultimodalAssistant**: 多模态助手主类
  - 系统的高层接口，整合所有核心功能
  - 提供批处理功能，支持多文件分析
  - 实现了内容生成功能，可基于参考资料创建内容
  - 提供状态管理，记录处理时间与过程信息
  - 统一的错误处理与日志记录

#### 处理流程
1. **内容输入**: 系统接收文本、图像、音频或视频输入
2. **类型检测**: 自动识别内容类型并路由到相应处理模块
3. **特征提取**: 根据内容类型提取相关特征与元数据
4. **AI分析**: 调用AI服务进行深度理解与分析
5. **结果聚合**: 将各模块分析结果整合为统一格式
6. **建议生成**: 基于分析结果生成改进建议
7. **结果输出**: 以指定格式（JSON/HTML/文本）输出分析结果

#### 技术栈
- **后端**: Python 3.8+, Flask, Flask-CORS
- **AI模型**: OpenAI GPT-3.5/4, Whisper, Vision
- **数据处理**: NLTK, NumPy, jieba
- **媒体处理**: PIL, OpenCV, ffmpeg
- **OCR**: Tesseract
- **Web服务**: Flask, JSON API

#### 扩展性设计
- 模块化结构允许轻松添加新的分析功能
- 接口统一，便于替换或升级底层组件
- 支持插件系统，可扩展分析能力
- 配置驱动，易于适应不同环境与需求

## 安装说明

### 环境要求
- Python 3.8+
- pip包管理工具
- ffmpeg（用于音视频处理）
- Tesseract（用于OCR，可选）

### 安装步骤

1. 克隆或下载项目
```bash
git clone <repository_url>
cd multimodal-assistant
```

2. 创建并激活虚拟环境（推荐）
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/MacOS
python3 -m venv venv
source venv/bin/activate
```

3. 安装依赖包
```bash
pip install -r requirements.txt
```

4. 安装额外依赖

- **ffmpeg安装**
  - Windows: 从官网下载并添加到PATH
  - Linux: `sudo apt-get install ffmpeg`
  - MacOS: `brew install ffmpeg`

- **Tesseract安装**（可选，用于OCR）
  - Windows: 从GitHub下载安装包
  - Linux: `sudo apt-get install tesseract-ocr`
  - MacOS: `brew install tesseract`

5. 配置环境变量

创建`.env`文件：
```
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-3.5-turbo
OPENAI_VISION_MODEL=gpt-4-vision-preview
WHISPER_MODEL_SIZE=base
```

## 使用指南

### 1. 启动应用

#### 开发模式
```bash
python app.py web --port 5000 --debug
```

#### 生产模式
```bash
python app.py web --port 5000
```

### 2. 命令行使用

本工具支持命令行操作，提供以下子命令：

#### 分析文件
```bash
python app.py analyze-file 文件路径 --output json
```

#### 分析文本
```bash
python app.py analyze-text "要分析的文本内容" --purpose general --output json
```

#### 生成内容
```bash
python app.py generate "生成提示" --references 参考文件.txt --output txt
```

#### 批量处理
```bash
python app.py batch 文件列表.txt --output txt
```

### 3. Web界面功能使用

#### 文本分析
1. 访问Web界面文本分析页面
2. 输入或粘贴文本内容
3. 选择分析类型（通用/学术/营销等）
4. 点击"分析"按钮
5. 查看分析结果，包括：
   - 关键词和主题
   - 情感倾向
   - 文本统计
   - AI建议

#### 图像分析
1. 选择图像分析页面
2. 上传图片文件（支持jpg/png/webp等）
3. 等待分析完成
4. 查看分析结果：
   - 内容识别
   - 场景分类
   - 物体检测
   - 色彩分析
   - OCR结果（如有文字）

#### 音频分析
1. 选择音频分析页面
2. 上传音频文件（支持mp3/wav等）
3. 等待处理完成
4. 查看分析结果：
   - 语音转文字
   - 波形分析
   - 频谱图
   - 内容理解

#### 视频分析
1. 选择视频分析页面
2. 上传视频文件（支持mp4/avi等）
3. 等待处理完成
4. 查看分析结果：
   - 关键帧分析
   - 场景识别
   - 音频内容
   - 综合报告

### 4. API使用

系统提供了完整的REST API，支持各种内容分析和处理：

#### 文本分析API
```bash
curl -X POST http://localhost:5000/api/analyze/text \
  -H "Content-Type: application/json" \
  -d '{"text": "your text here", "generate_suggestions": true}'
```

#### 文件分析API
```bash
curl -X POST http://localhost:5000/api/analyze-file \
  -F "file=@path/to/your/file"
```

#### 内容生成API
```bash
curl -X POST http://localhost:5000/api/generate-content \
  -H "Content-Type: application/json" \
  -d '{"prompt": "your prompt here", "references": []}'
```

#### 结果导出API
```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"results": {...}, "format": "json"}'
```

## 架构详解

### 处理流程与数据流
1. **输入层**：用户通过Web界面、API或命令行提供内容
2. **路由层**：`MultimodalAssistant`将请求路由到适当的处理器
3. **处理层**：
   - 文本内容 → `TextAnalyzer`
   - 媒体文件 → `MediaProcessor` → 根据类型分发到子处理器
4. **AI增强层**：`AIService`对基础分析结果进行增强处理
5. **聚合层**：`ContentProcessor`合并各模块结果
6. **输出层**：以用户指定格式返回结果

### 错误处理机制
- **多级降级**：当高级功能不可用时，自动降级到基础功能
- **异常隔离**：模块内部异常被捕获，不影响整体流程
- **详细日志**：各处理步骤记录详细日志，便于问题定位
- **重试机制**：API调用实现了自动重试，提高稳定性

### 可扩展性设计
- **模块松耦合**：各功能模块通过明确接口交互，易于替换
- **插件架构**：处理器可动态注册，支持扩展分析能力
- **配置驱动**：关键参数通过环境变量配置，易于适应不同环境

## 性能优化

### 本地处理优化
- NLTK资源本地缓存
- 图像处理批量化
- 音视频流式处理
- 多进程任务处理
- 惰性加载：只在需要时初始化大型组件

### API调用优化
- 请求队列管理
- 错误重试机制
- 结果缓存
- 并发请求限制
- 超时控制：避免长时间阻塞

### 内存管理
- 大文件流式处理
- 临时文件自动清理
- 资源使用限制
- 结果分页处理

## 常见问题

### 1. 安装问题
- NLTK资源下载失败：手动下载并放置到nltk_data目录
- ffmpeg未找到：检查环境变量PATH
- Tesseract配置：设置正确的安装路径
- 依赖冲突：使用虚拟环境隔离依赖

### 2. 运行问题
- 内存使用过高：调整批处理大小
- 处理超时：增加超时时间
- API错误：检查密钥和网络
- 权限问题：检查临时目录权限

### 3. 结果问题
- 分析不准确：尝试调整参数
- OCR识别率低：改善图像质量
- 音频转写错误：检查音频质量
- 响应缓慢：检查网络延迟和API状态

## 开发计划

### 近期计划
- [ ] 添加批量处理功能
- [ ] 优化音视频处理性能
- [ ] 增加更多AI模型支持
- [ ] 改进用户界面交互
- [ ] 增强报告生成功能
- [ ] 添加数据可视化组件

### 长期规划
- [ ] 支持更多文件格式
- [ ] 添加自定义模型接口
- [ ] 实现分布式处理
- [ ] 提供云端部署方案
- [ ] 开发移动应用客户端
- [ ] 构建内容分析数据库

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交更改
4. 发起Pull Request

## 许可证

MIT License

## 联系方式

- 项目主页：[GitHub Repository]
- 问题反馈：[Issues]
- 邮件支持：[Email] 