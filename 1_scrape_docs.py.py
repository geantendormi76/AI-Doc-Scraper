# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import logging
import os
import re
from urllib.parse import urljoin, urlparse
from time import time
from tqdm.asyncio import tqdm

# --- 全局配置 ---
START_URL = "https://docs.isaacsim.omniverse.nvidia.com/4.5.0/index.html"
BASE_URL = "https://docs.isaacsim.omniverse.nvidia.com/4.5.0/"
OUTPUT_DIR = "isaac_sim_4.5_docs_md"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
CONCURRENT_REQUESTS = 20

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get_all_doc_urls(start_url, base_url):
    """从起始页面获取所有独立的文档页面URL。"""
    logging.info(f"步骤 1: 开始从 {start_url} 获取所有URL链接...")
    try:
        response = requests.get(start_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"无法获取入口页面 {start_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    urls = set()
    nav_container = soup.find('div', class_='bd-sidebar-primary')
    if not nav_container:
        logging.error("未找到导航容器 (class='bd-sidebar-primary')。请检查网页结构。")
        return []

    for link in nav_container.find_all('a', href=True):
        href = link['href']
        if href.startswith('#') or 'javascript:void(0)' in href:
            continue
        
        absolute_url = urljoin(base_url, href)
        page_url = absolute_url.split('#')[0].split('?')[0]
        
        if urlparse(page_url).netloc == urlparse(base_url).netloc and page_url.endswith('.html'):
            urls.add(page_url)
        
    logging.info(f"✅ 步骤 1 完成: 成功找到 {len(urls)} 个独立的URL。")
    return sorted(list(urls))

def generate_safe_filename(url):
    """从URL生成一个安全的文件名，将'/'和'-'都替换为'_'。"""
    path = urlparse(url).path
    path = path.replace('/4.5.0/', '')
    safe_name = path.replace('/', '_').replace('-', '_').replace('.html', '').strip('_')
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', safe_name)
    return f"{safe_name}.md"

def clean_and_convert_to_markdown(html_content):
    """清理HTML并将其转换为Markdown格式。"""
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content = soup.find('main', id='main-content')
    if not main_content:
        logging.warning("在HTML中未找到主内容区域 (id='main-content')。")
        return ""

    elements_to_remove_selectors = [
        'div.edit-this-page',
        'a.headerlink',
        'div.prev-next-area'
    ]
    for selector in elements_to_remove_selectors:
        for element in main_content.select(selector):
            element.decompose()

    return md(str(main_content), heading_style="ATX")

async def fetch_and_process(session, url, output_dir, semaphore):
    """异步抓取、处理并保存Markdown文件，同时在文件顶部嵌入原始URL。"""
    async with semaphore:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logging.warning(f"请求失败，状态码 {response.status} for {url}")
                    return
                
                html = await response.text()
                markdown_content = clean_and_convert_to_markdown(html)
                
                if not markdown_content:
                    logging.warning(f"在 {url} 未找到或无法提取主内容。")
                    return

                # --- 核心修正：在文件顶部添加URL元数据 ---
                final_content = f"<!-- Original URL: {url} -->\n\n{markdown_content}"

                filename = generate_safe_filename(url)
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(final_content)
                
        except Exception as e:
            logging.error(f"处理URL时发生错误 {url}: {e}")

async def main():
    start_time = time()
    
    doc_urls = get_all_doc_urls(START_URL, BASE_URL)
    if not doc_urls:
        return

    if os.path.exists(OUTPUT_DIR):
        import shutil
        shutil.rmtree(OUTPUT_DIR)
        logging.info(f"已清理旧的输出目录: {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR)
    logging.info(f"已创建输出目录: {OUTPUT_DIR}")

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        total_urls = len(doc_urls)
        logging.info(f"\n步骤 2: 开始从 {total_urls} 个URL中异步抓取并转换为Markdown...")
        tasks = [fetch_and_process(session, url, OUTPUT_DIR, semaphore) for url in doc_urls]
        await tqdm.gather(*tasks, desc="正在抓取文档")

    end_time = time()
    logging.info("\n🎉 全部处理完毕！ 🎉")
    logging.info(f"所有Markdown文件已保存在 '{OUTPUT_DIR}' 文件夹中。")
    logging.info(f"总耗时: {end_time - start_time:.2f} 秒。")

if __name__ == "__main__":
    asyncio.run(main())