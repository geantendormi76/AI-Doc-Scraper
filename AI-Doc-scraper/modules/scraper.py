# modules/scraper.py
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import logging
import os
import re
from urllib.parse import urljoin, urlparse
from time import time
from playwright.async_api import async_playwright
from .config import Config

# --- 新增的自定义异常，这是解决问题的关键 ---
class SelectorNotFoundError(Exception):
    """当AI提供的选择器找不到元素时抛出。"""
    def __init__(self, message, selector, html_snippet):
        super().__init__(message)
        self.selector = selector
        self.html_snippet = html_snippet

# --- 模块级配置 ---
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
CONCURRENT_REQUESTS = 20

# --- 核心抓取逻辑 ---

def get_all_doc_urls_from_html(rendered_html: str, config: Config) -> list[str]:
    """
    直接从【已渲染】的HTML中提取所有文档URL。
    """
    logging.info("正在从已渲染的HTML中提取所有URL链接...")
    soup = BeautifulSoup(rendered_html, 'html.parser')
    urls = set()
    nav_container = soup.select_one(config.nav_selector)

    if not nav_container:
        # --- 现在这个异常可以被正确地抛出和捕获了 ---
        raise SelectorNotFoundError(
            f"未找到导航容器",
            selector=config.nav_selector,
            html_snippet=rendered_html[:2000] # 附带HTML片段用于调试
        )
    
    for link in nav_container.find_all('a', href=True):
        href = link['href']
        if href.startswith('#'): continue
        absolute_url = urljoin(config.base_url, href)
        page_url = absolute_url.split('#')[0]
        if page_url.startswith(config.base_url):
            urls.add(page_url)
    
    logging.info(f"成功找到 {len(urls)} 个独立的URL。")
    return sorted(list(urls))

def generate_safe_filename(url: str, config: Config) -> str:
    """从URL生成安全的文件名。"""
    path = urlparse(url).path.replace(urlparse(config.base_url).path, "", 1)
    safe_name = path.replace('/', '_').replace('.html', '').strip('_')
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', safe_name)
    return f"{safe_name or 'index'}.md"

def clean_and_convert(html_content: str, config: Config) -> str:
    """清理HTML并转换为Markdown。"""
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content = soup.select_one(config.content_selector)
    if not main_content:
        logging.warning(f"在HTML中未找到主内容区域 (选择器: {config.content_selector})")
        return ""
    
    for selector in config.elements_to_remove:
        for element in main_content.select(selector):
            element.decompose()
            
    return md(str(main_content), heading_style="ATX")

async def fetch_and_save_static(session: aiohttp.ClientSession, url: str, config: Config, semaphore: asyncio.Semaphore):
    """静态策略：使用aiohttp并发抓取单个页面。"""
    async with semaphore:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                markdown_content = clean_and_convert(html, config)
                if not markdown_content: return
                filename = generate_safe_filename(url, config)
                filepath = os.path.join(config.output_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f: f.write(markdown_content)
        except Exception as e:
            logging.warning(f"处理静态URL时发生错误 {url}: {e}")

async def fetch_and_save_dynamic(page, url: str, config: Config):
    """动态策略：使用同一个Playwright页面实例，导航到新URL并保存。"""
    try:
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        markdown_content = clean_and_convert(html, config)
        if not markdown_content:
            logging.warning(f"内容为空，跳过文件写入: {url}")
            return
        filename = generate_safe_filename(url, config)
        filepath = os.path.join(config.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f: f.write(markdown_content)
    except Exception as e:
        logging.error(f"处理动态URL时发生错误 {url}: {e}")

async def execute_scrape(rendered_html: str, config: Config):
    """根据AI制定的策略（静态或动态），执行相应的抓取流程。"""
    start_time = time()
    logging.info(f"--- 开始为项目 '{config.project_name}' 进行抓取 ---")
    if not os.path.exists(config.output_dir):
        os.makedirs(config.output_dir)
        logging.info(f"已创建输出目录: {config.output_dir}")

    doc_urls = get_all_doc_urls_from_html(rendered_html, config)
    if not doc_urls:
        # 这个函数现在会抛出异常，所以这里的检查实际上是第二道防线
        logging.error("未能获取任何URL，抓取流程终止。")
        return

    logging.info(f"开始从 {len(doc_urls)} 个URL中异步抓取并转换为Markdown...")
    
    if config.fetch_strategy == 'dynamic':
        logging.info("检测到动态网站策略，将为所有页面启用Playwright。")
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            for i, url in enumerate(doc_urls):
                logging.info(f"动态抓取进度: {i+1}/{len(doc_urls)} - {url}")
                await fetch_and_save_dynamic(page, url, config)
            await browser.close()
    else: # 默认为 'static'
        logging.info("检测到静态网站策略，将使用高速的aiohttp并发抓取。")
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            tasks = [fetch_and_save_static(session, url, config, semaphore) for url in doc_urls]
            await asyncio.gather(*tasks)

    end_time = time()
    logging.info(f"\n抓取任务完成！")
    logging.info(f"所有Markdown文件已保存在 '{config.output_dir}' 文件夹中。")
    logging.info(f"总耗时: {end_time - start_time:.2f} 秒。")