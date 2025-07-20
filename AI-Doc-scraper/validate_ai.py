# validate_ai.py
import asyncio
import logging
import os
import random
import json
from dotenv import load_dotenv
import google.generativeai as genai
from time import time
import argparse
from urllib.parse import urljoin 

# --- 导入我们所有的模块和配置 ---
from modules.config import Config
from modules.ai_planner import plan_from_html
from modules.scraper import clean_and_convert
from main import get_html_with_playwright # 从主程序导入渲染函数

# --- 初始化与配置 ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY: raise ValueError("错误: GEMINI_API_KEY 未在 .env 文件中设置！")
genai.configure(api_key=GEMINI_API_KEY)

# --- 脚本配置 ---
SAMPLE_SIZE = 5

# ==============================================================================
# 核心验证逻辑
# ==============================================================================

def find_available_projects() -> list[str]:
    """扫描当前目录，找到所有已抓取的项目名称。"""
    projects = []
    for item in os.listdir('.'):
        if os.path.isdir(item) and item.startswith('scraped_docs_'):
            projects.append(item.replace('scraped_docs_', '', 1))
    return projects

def load_project_metadata(project_name: str) -> dict | None:
    """从项目文件夹加载元数据。"""
    meta_path = os.path.join(f"scraped_docs_{project_name}", ".project_meta.json")
    if not os.path.exists(meta_path):
        logging.error(f"错误: 找不到项目 '{project_name}' 的元数据文件。请确保该项目已成功抓取。")
        return None
    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def reconstruct_url_from_filename(filename: str, config: Config) -> str:
    """根据文件名和【指定的配置】，反向推导出原始URL。"""
    # 示例: 'tutorial_first-steps.md' -> 'tutorial/first-steps'
    # 注意：FastAPI的URL没有.html后缀，所以我们直接替换
    path_part = filename.replace('.md', '').replace('_', '/')
    # 现在这个调用可以正常工作了
    return urljoin(config.base_url, path_part)

async def validate_content_with_gemini(local_md: str, live_md: str) -> dict:
    """使用Gemini API比较两个Markdown文档的语义内容。"""
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    prompt = f"""
    作为一名严谨的文档质量保证(QA)工程师，你的任务是比较下面提供的两个Markdown文档。

    - **[文档A]** 是从本地文件系统读取的已抓取版本。
    - **[文档B]** 是从实时官方网站刚刚抓取并转换的版本。

    请对它们进行语义层面的比较，并判断它们的核心内容是否一致。你需要忽略微小的格式差异、空格或换行符的不同。你的重点是：
    1.  **核心主题**：它们是否在讲述同一件事？
    2.  **关键信息**：代码块、关键指令、重要概念是否在两者中都存在且一致？
    3.  **内容完整性**：是否有任何重要段落或部分在文档A中缺失了？

    请以JSON格式返回你的分析结果，包含以下字段：
    - "is_match": 布尔值，如果内容核心一致则为 true，否则为 false。
    - "confidence": 浮点数，你对结论的信心度 (0.0 到 1.0)。
    - "reason": 字符串，简要解释你判断的理由。

    ---
    [文档A: 本地文件]
    ```markdown
    {local_md[:4000]} 
    ```
    ---
    [文档B: 实时网站]
    ```markdown
    {live_md[:4000]}
    ```
    """
    try:
        response = await model.generate_content_async(prompt)
        json_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_text)
    except Exception as e:
        return {"is_match": False, "confidence": 0.0, "reason": f"API调用异常: {e}"}

async def process_and_validate_file(filename: str, config: Config):
    """完整的单个文件验证流程：获取实时数据 -> AI对比 -> 输出结果。"""
    try:
        filepath = os.path.join(config.output_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            local_md_content = f.read()

        url = reconstruct_url_from_filename(filename, config)
        logging.info(f"正在验证: {filename} (AI-powered)")
        
        # --- 修正：对于所有验证，都使用Playwright获取实时内容，确保准确性 ---
        live_html = await get_html_with_playwright(url)
        if not live_html:
            raise ConnectionError(f"无法获取实时URL内容: {url}")
            
        live_md_content = clean_and_convert(live_html, config)

        result = await validate_content_with_gemini(local_md_content, live_md_content)

        status = "✅ PASS" if result.get("is_match") else "❌ FAIL"
        logging.info(f"  -> AI结论: {status} | 置信度: {result.get('confidence', 0):.0%} | 理由: {result.get('reason', 'N/A')}\n")
        return result.get("is_match", False)
    except Exception as e:
        logging.error(f"处理文件时发生未知错误 {filename}: {e}\n")
        return False

async def main():
    """主执行函数，运行可配置的、用户友好的验证流程。"""
    available_projects = find_available_projects()
    parser = argparse.ArgumentParser(
        description="使用AI验证已抓取的Markdown文档与实时官网内容的一致性。",
        epilog=f"可用的项目: {', '.join(available_projects) if available_projects else '无 (请先运行main.py抓取一个项目)'}"
    )
    parser.add_argument("project_name", help="要验证的项目名称。", choices=available_projects or [None])
    args = parser.parse_args()
    project_name = args.project_name
    
    start_time = time()
    logging.info(f"--- 开始为项目 '{project_name}' 进行AI自动化抽样验证 ---")
    
    metadata = load_project_metadata(project_name)
    if not metadata: return
    start_url = metadata['start_url']

    logging.info("正在重新运行AI规划以获取最新、最准确的配置...")
    rendered_html = await get_html_with_playwright(start_url)
    if not rendered_html: return
    config = await plan_from_html(project_name, start_url, rendered_html)
    if not config: return
    logging.info("✅ AI配置已实时生成。")

    markdown_dir = config.output_dir
    all_md_files = [f for f in os.listdir(markdown_dir) if f.endswith('.md') and not f.startswith('.')]
    if not all_md_files:
        logging.error(f"错误: 在 '{markdown_dir}' 中没有找到Markdown文件。")
        return

    sample_files = random.sample(all_md_files, min(len(all_md_files), SAMPLE_SIZE))
    logging.info(f"从 {len(all_md_files)} 个文件中随机抽取 {len(sample_files)} 个进行AI验证...\n")
    
    tasks_results = []
    for filename in sample_files:
        # 串行执行验证，避免同时启动多个浏览器实例
        result = await process_and_validate_file(filename, config)
        tasks_results.append(result)

    success_count = sum(1 for res in tasks_results if res)
    
    end_time = time()
    logging.info("--- 验证完成 ---")
    logging.info(f"成功通过AI验证的样本数: {success_count} / {len(sample_files)}")
    logging.info(f"总耗时: {end_time - start_time:.2f} 秒。")

if __name__ == "__main__":
    asyncio.run(main())