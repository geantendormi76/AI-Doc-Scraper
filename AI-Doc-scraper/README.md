# 🧠 人工智能驱动的文档抓取工具

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个由AI驱动的、能自我配置和自我修正的通用文档抓取引擎。您只需提供一个URL，它就能自动分析网站结构，并将完整的官方文档抓取为一系列干净、结构化的Markdown文件，为您的AI提供最新鲜的“养料”。

## 💡 缘起：弥合AI的知识鸿沟

我们都惊叹于大语言模型（LLM）的强大，但它们并非全知全能。它们的核心弱点在于——**知识的滞后性**。

由于训练数据的截止日期限制，AI的知识库与现实世界存在着一条难以逾越的鸿沟，这个鸿沟有时长达一年半之久。当我们与AI交互时，这种滞后性会带来巨大的困扰：
> AI可能会自信地告诉我们，最新的YOLO版本是v8，而现实世界早已迭代至v12；它也无法感知到某个库已经更换了全新的API、修改了核心依赖，或者废弃了某个关键类。

对于需要精准、前沿信息的开发者和学习者而言，这种过时的信息不仅毫无用处，甚至会造成误导。

**这个项目，正是为了解决这一根本性问题而生。**

我们的目标是打造一座桥梁，跨越这条知识鸿沟。通过智能地抓取最新的官方文档——这个世界上最准确、最前沿的知识源——我们可以为AI提供持续更新的、来自“第一现场”的“地面实况”信息，从而让每一次与AI的交互都变得更加精准、高效和可靠。

## ✨ 核心功能

-   **AI自动规划**: 无需手动编写或寻找CSS选择器。AI会自动分析渲染后的DOM，生成最佳抓取策略。
-   **自我修正能力**: 当AI的初次规划失败时，系统会自动启动“B计划”，让AI分析失败原因并生成一个修正后的新计划，再次尝试。
-   **动态网站(SPA)支持**: 内置`Playwright`，能够完美处理使用React/Vue/Angular等框架构建的现代单页应用，确保获取到100%渲染后的真实内容。
-   **智能内容清洗**: 自动移除广告、警告横幅、多余图标等无关元素，产出纯净的Markdown。
-   **AI驱动的语义验证**: 附带独立的验证脚本，可调用AI来从语义层面比较抓取内容与实时官网内容的一致性，提供高置信度的质量报告。

## 📂 项目结构

```
├── .gitignore             # 忽略不必要文件
├── README.md              # 项目说明
├── requirements.in        # 声明直接依赖
├── requirements.txt       # 锁定的完整依赖
├── main.py                # 唯一的、总的程序入口
├── validate_ai.py         # (可选) 独立的AI验证脚本
├── .env.example           # 环境变量模板
└── modules/               # 核心逻辑模块
    ├── ai_planner.py      # AI规划与自我修正模块
    ├── config.py          # Config数据结构定义
    └── scraper.py         # 抓取执行引擎模块
```

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/geantendormi76/AI-Powered-Docs-Scraper.git
cd AI-Powered-Docs-Scraper
```

### 2. 创建并激活虚拟环境

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

本项目遵循现代Python依赖管理最佳实践。

```bash
# 首先，安装pip-tools
pip install pip-tools

# 然后，同步环境，确保与锁定文件完全一致
pip-sync requirements.txt
```

### 4. 安装浏览器核心

本项目使用`Playwright`来处理动态网站，需要下载浏览器核心文件。

```bash
playwright install
```

### 5. 设置环境变量

要使用AI规划和验证功能，您需要一个Google Gemini API密钥。

```bash
# 1. 将模板文件复制为 .env 文件
cp .env.example .env

# 2. 编辑 .env 文件，填入您的真实API密钥
# GEMINI_API_KEY="AIzaSy...your...key..."
```

## 🛠️ 使用方法

整个流程被设计得极其简单，只需一到两个命令。

### 步骤 1: 运行主程序进行抓取

打开您的终端，运行`main.py`，并提供您想抓取的网站的`--url`和您想为这个项目指定的`--name`。

```bash
python main.py --url https://fastapi.tiangolo.com/ --name fastapi_docs
```

或者，抓取ROS官方文档：

```bash
python main.py --url https://docs.ros.org/en/humble/index.html --name ros_humble_docs
```

程序将自动执行所有阶段：动态渲染 -> AI规划 -> (可能的自我修正) -> 执行抓取。成功后，您会在项目根目录下看到一个名为`scraped_docs_[您的项目名]`的文件夹。

### 步骤 2: (可选) 运行AI验证

抓取完成后，您可以运行验证脚本来抽样检查内容质量。

首先，您可以直接运行脚本来查看所有已成功抓取的、可供验证的项目：

```bash
python validate_ai.py
```

然后，根据提示，选择您想要验证的项目名作为参数再次运行：

```bash
python validate_ai.py fastapi_docs
```

脚本会自动找到对应的文件夹和URL，并启动由AI驱动的语义内容验证。

## 🤝 贡献

欢迎提交PR或提出Issue！我们共同打造的这个智能体仍有巨大的进化空间。

## 📄 许可证

本项目采用 [MIT License](LICENSE)。
