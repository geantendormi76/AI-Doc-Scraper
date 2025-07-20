# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import logging
import os
import random
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai
from time import time
from tqdm.asyncio import tqdm

# --- 配置 ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("错误: GEMINI_API_KEY 未在 .env 文件中设置！")
genai.configure(api_key=GEMINI_API_KEY)

MARKDOWN_DIR = "isaac_sim_4.5_docs_md" 
SAMPLE_SIZE = 5
GENERATIVE_MODEL = "gemini-1.5-flash-latest"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
CONCURRENT_REQUESTS = 5

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# ==============================================================================
# 核心验证逻辑
# ==============================================================================

def extract_url_from_md(file_content):
    """从Markdown文件的注释中提取原始URL。"""
    match = re.search(r"<!-- Original URL: (.*) -->", file_content)
    if match:
        return match.group(1).strip()
    return None

def clean_and_convert_to_markdown(html_content):
    """清理HTML并将其转换为Markdown。与抓取脚本中的逻辑保持一致。"""
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content = soup.find('main', id='main-content')
    if not main_content: return ""
    
    elements_to_remove_selectors = [
        'div.edit-this-page',
        'a.headerlink',
        'div.prev-next-area'
    ]
    for selector in elements_to_remove_selectors:
        for element in main_content.select(selector):
            element.decompose()
        
    return md(str(main_content), heading_style="ATX")

async def validate_content_with_gemini(local_md, live_md):
    """使用Gemini API比较两个Markdown文档的语义内容。"""
    model = genai.GenerativeModel(GENERATIVE_MODEL)
    prompt = f"""
    作为一名严谨的文档QA工程师，请以JSON格式，语义上比较[文档A]和[文档B]。
    判断核心主题、关键信息和完整性是否一致，忽略微小格式差异。
    返回包含 "is_match": bool, "confidence": float, "reason": str 的JSON。

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
        logging.error(f"Gemini API 调用失败: {e}")
        return {"is_match": False, "confidence": 0.0, "reason": f"API调用异常: {e}"}

async def process_and_validate_file(session, filename, semaphore):
    """完整的单个文件验证流程：读取URL -> 获取实时数据 -> AI对比 -> 输出结果。"""
    async with semaphore:
        try:
            filepath = os.path.join(MARKDOWN_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                local_md_content = f.read()

            # --- 核心修正: 不再重建URL，而是直接从文件中读取 ---
            url = extract_url_from_md(local_md_content)
            if not url:
                logging.warning(f"  -> 在文件中未找到URL元数据: {filename}\n")
                return False

            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                live_md_content = clean_and_convert_to_markdown(html)

            if not live_md_content:
                logging.warning(f"  -> 无法从实时URL提取内容: {url}\n")
                return False

            result = await validate_content_with_gemini(local_md_content, live_md_content)

            status = "✅ PASS" if result.get("is_match") else "❌ FAIL"
            logging.info(f"[{filename}] -> AI结论: {status} | 置信度: {result.get('confidence', 0):.0%} | 理由: {result.get('reason', 'N/A')}")
            return result.get("is_match", False)

        except aiohttp.ClientResponseError as e:
            logging.error(f"处理文件时发生HTTP错误 {filename} (URL: {url}): {e.status}, message='{e.message}'\n")
            return False
        except Exception as e:
            logging.error(f"处理文件时发生未知错误 {filename} (URL: {url}): {e}\n")
            return False

async def main():
    start_time = time()
    logging.info("--- 开始AI驱动的自动化抽样验证 ---")
    
    if not os.path.isdir(MARKDOWN_DIR):
        logging.error(f"错误: 目录 '{MARKDOWN_DIR}' 未找到！")
        return

    all_md_files = [f for f in os.listdir(MARKDOWN_DIR) if f.endswith('.md')]
    if not all_md_files:
        logging.error(f"错误: 在 '{MARKDOWN_DIR}' 中没有找到Markdown文件。")
        return

    sample_files = random.sample(all_md_files, min(len(all_md_files), SAMPLE_SIZE))
    logging.info(f"从 {len(all_md_files)} 个文件中随机抽取 {len(sample_files)} 个进行AI验证...\n")
    
    success_count = 0
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [process_and_validate_file(session, filename, semaphore) for filename in sample_files]
        results = await tqdm.gather(*tasks, desc="正在验证样本")
        success_count = sum(1 for res in results if res)

    logging.info("\n--- 验证完成 ---")
    logging.info(f"成功通过AI验证的样本数: {success_count} / {len(sample_files)}")
    logging.info(f"总耗时: {time() - start_time:.2f} 秒。")

if __name__ == "__main__":
    asyncio.run(main())