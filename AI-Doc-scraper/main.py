# main.py
import asyncio
import argparse
import logging
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from playwright.async_api import async_playwright

# --- 导入我们的模块和配置 ---
from modules.ai_planner import plan_from_html, refine_and_correct_plan
from modules.scraper import execute_scrape, SelectorNotFoundError
from modules.config import Config

# --- 尝试导入手动配置文件 ---
try:
    import manual_configs
    ALL_MANUAL_CONFIGS = {name: obj for name, obj in vars(manual_configs).items() if isinstance(obj, Config)}
except ImportError:
    ALL_MANUAL_CONFIGS = {}

# --- 初始化与配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY: raise ValueError("错误: GEMINI_API_KEY 未在 .env 文件中设置！")
genai.configure(api_key=GEMINI_API_KEY)
MAX_ATTEMPTS = 2

# --- 修正：将被遗忘的辅助函数加回到这里 ---
async def get_html_with_playwright(url: str) -> str | None:
    """使用Playwright无条件获取动态渲染后的HTML。"""
    logging.info(f"正在使用Playwright完全渲染页面: {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logging.error(f"Playwright渲染页面失败: {e}")
        return None

async def main():
    """
    主协调器：负责根据用户指令，选择AI自动模式或专家手动模式。
    """
    parser = argparse.ArgumentParser(
        description="AI驱动的文档抓取引擎，支持AI自动规划和专家手动配置。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--auto", nargs=2, metavar=('URL', 'NAME'), help="AI自动模式: 提供起始URL和项目名称。")
    group.add_argument("-m", "--manual", choices=ALL_MANUAL_CONFIGS.keys(), help="专家手动模式: 使用在manual_configs.py中预定义的配置名称。")
    
    args = parser.parse_args()
    config = None
    rendered_html = None

    if args.manual:
        # --- 手动模式 ---
        config_name = args.manual
        logging.info("="*50 + f"\n正在以【专家手动模式】运行，使用配置: {config_name}\n" + "="*50)
        config = ALL_MANUAL_CONFIGS.get(config_name)
        # 手动模式也需要渲染首页以提取链接
        rendered_html = await get_html_with_playwright(config.start_url)
        if not rendered_html: return

    elif args.auto:
        # --- AI自动模式 ---
        url, name = args.auto
        logging.info("="*50 + "\n正在以【AI自动模式】运行...\n" + "="*50)
        
        logging.info("阶段 1: 正在动态渲染初始页面以获取最完整HTML...")
        rendered_html = await get_html_with_playwright(url)
        if not rendered_html: return

        logging.info("阶段 2: AI 正在分析【已渲染】的HTML并生成抓取计划...")
        config = await plan_from_html(name, url, rendered_html)
        if not config: return

    if not config or not rendered_html:
        logging.error("未能获取有效配置或HTML内容，程序终止。")
        return

    # --- 阶段 3: 执行与自我修正循环 ---
    for attempt in range(MAX_ATTEMPTS):
        try:
            logging.info("="*50 + f"\n阶段 3 (尝试 {attempt + 1}/{MAX_ATTEMPTS}): 抓取器正在根据当前计划执行任务...\n" + "="*50)
            logging.info("✅ 当前执行的计划如下:")
            logging.info(f"   - 项目名称: {config.project_name}")
            logging.info(f"   - 抓取策略: {config.fetch_strategy.upper()}")
            logging.info(f"   - 导航选择器: {config.nav_selector}")
            logging.info(f"   - 内容选择器: {config.content_selector}")
            logging.info(f"   - 待移除元素: {config.elements_to_remove}")

            await execute_scrape(rendered_html, config)
            
            save_project_metadata(config)
            logging.info("="*50 + "\n✅ 抓取成功，工作流程完成！\n" + "="*50)
            return

        except SelectorNotFoundError as e:
            if args.auto and attempt < MAX_ATTEMPTS - 1:
                logging.error(f"执行失败: {e}")
                logging.info("="*50 + "\n阶段 2.1: AI正在根据失败信息进行自我修正...\n" + "="*50)
                error_info = {"selector": e.selector, "html_snippet": e.html_snippet}
                corrected_config = await refine_and_correct_plan(config, error_info)
                if corrected_config: config = corrected_config
                else:
                    logging.error("AI未能生成修正计划，程序终止。")
                    break
            else:
                logging.error("执行失败，已达到最大尝试次数或处于手动模式，程序终止。")
                return

def save_project_metadata(config: Config):
    """在项目文件夹中保存一个包含起始URL的元数据文件。"""
    meta_path = os.path.join(config.output_dir, ".project_meta.json")
    meta_data = {
        "project_name": config.project_name,
        "start_url": config.start_url
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=4)
    logging.info(f"项目元数据已保存到: {meta_path}")

if __name__ == "__main__":
    asyncio.run(main())