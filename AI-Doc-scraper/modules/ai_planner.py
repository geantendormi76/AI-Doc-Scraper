# modules/ai_planner.py
import google.generativeai as genai
import json
import logging
import re
from .config import Config

# --- 模块级配置 ---
GENERATIVE_MODEL = "gemini-1.5-flash-latest"

async def plan_from_html(project_name: str, start_url: str, rendered_html: str) -> Config | None:
    """
    接收一个【已经完全渲染好】的HTML内容，调用AI进行战略决策和规划，并返回一个Config对象。
    """
    logging.info("HTML已由Playwright渲染，正在请求AI进行分析以生成配置...")
    
    model = genai.GenerativeModel(GENERATIVE_MODEL)
    
    # --- 最终毕业版Prompt，增加了对“通用性”的强调 ---
    prompt = f"""
    作为一名顶尖的前端开发与数据抓取专家，请分析下面提供的【已经由浏览器完全渲染好】的HTML代码。
    你的任务是为我的Python抓取脚本生成一个精确且【通用】的配置。

    请分两步进行分析：
    1.  **战略判断**: 判断这个网站是“静态/SSR”还是“单页应用(SPA)”。对于现代文档（如使用React/Vue/MkDocs），请优先考虑【dynamic】。
    
    2.  **提取通用选择器**: 根据HTML结构，找出以下CSS选择器。**重要提示**：你提供的选择器必须足够通用，既能匹配当前这个入口页面，也能大概率匹配网站的其他内容子页面。
        -   `nav_selector`: 找到包裹【整个导航链接树】的最外层容器。一个好的选择器通常是唯一的，如 `nav.side-bar` 或 `#main-navigation`。
        -   `content_selector`: 找到包裹【正文所有内容（标题、段落、代码块）】的那个最主要的容器。一个好的选择器通常是 `main`、`article` 或带有 `role="main"` 属性的 `div`，或者是带有 `id="content"` 或 `class="post-body"` 的 `div`。请避免使用过于复杂的组合选择器。

    **重要指令**: 你必须用你分析得出的【真实选择器】来替换掉JSON示例中的值。

    HTML内容预览 (前8000个字符):
    ```html
    {rendered_html[:8000]}
    ```

    请严格按照以下JSON格式返回你的答案，不要添加任何额外的解释。这是一个格式示例，你必须填充真实数据：
    {{
        "fetch_strategy": "dynamic",
        "nav_selector": "nav.md-nav",
        "content_selector": ".md-content",
        "elements_to_remove": ["a.headerlink"]
    }}
    """
    
    try:
        response = await model.generate_content_async(prompt)
        ai_response_text = response.text

        match = re.search(r'\{[\s\S]*\}', ai_response_text)
        
        if not match:
            logging.error(f"AI响应中未找到有效的JSON块。AI原始响应: {ai_response_text}")
            return None
        
        json_text = match.group(0)
        config_data = json.loads(json_text)
        
        if not start_url.endswith('/'):
            base_url = start_url + '/'
        else:
            base_url = start_url
        
        return Config(
            project_name=project_name,
            start_url=start_url,
            base_url=base_url,
            fetch_strategy=config_data['fetch_strategy'],
            nav_selector=config_data['nav_selector'],
            content_selector=config_data['content_selector'],
            elements_to_remove=config_data['elements_to_remove']
        )
        
    except json.JSONDecodeError as e:
        logging.error(f"解析AI响应中的JSON失败: {e}")
        logging.error(f"尝试解析的文本: '{json_text}'")
        return None
    except Exception as e:
        logging.error(f"AI规划失败: {e}")
        return None

async def refine_and_correct_plan(failed_config: Config, error_info: dict) -> Config | None:
    """
    接收失败的配置和错误信息，调用AI进行分析，并返回一个修正后的新配置。
    """
    logging.warning("AI初次规划失败，启动自我修正程序...")
    
    model = genai.GenerativeModel(GENERATIVE_MODEL)
    
    elements_to_remove_json_string = json.dumps(failed_config.elements_to_remove)

    prompt = f"""
    作为一名顶尖的Web开发调试专家，你之前的抓取计划失败了。
    
    **失败诊断报告:**
    - **失败的选择器**: `{error_info['selector']}`
    - **错误信息**: "在下面的HTML片段中找不到该选择器对应的元素。"

    **失败时对应的HTML片段 (前2000字符):**
    ```html
    {error_info['html_snippet']}
    ```

    **你的任务:**
    1.  仔细分析上面的HTML片段。
    2.  找出为什么选择器 `{error_info['selector']}` 会失败。
    3.  提供一个**修正后的、更精确、更健壮**的新选择器。
    4.  保持其他配置项不变，除非你认为它们也有问题。

    请严格按照以下JSON格式返回你修正后的完整配置方案：
    {{
        "fetch_strategy": "{failed_config.fetch_strategy}",
        "nav_selector": "YOUR_CORRECTED_SELECTOR_HERE",
        "content_selector": "{failed_config.content_selector}",
        "elements_to_remove": {elements_to_remove_json_string}
    }}
    """
    
    try:
        response = await model.generate_content_async(prompt)
        ai_response_text = response.text
        match = re.search(r'\{[\s\S]*\}', ai_response_text)
        if not match:
            logging.error("AI修正响应中未找到有效的JSON块。")
            return None
        
        json_text = match.group(0)
        config_data = json.loads(json_text)
        
        failed_config.nav_selector = config_data['nav_selector']
        failed_config.content_selector = config_data['content_selector']
        failed_config.elements_to_remove = config_data['elements_to_remove']
        
        logging.info("✅ AI已生成修正计划。")
        return failed_config
        
    except Exception as e:
        logging.error(f"AI修正计划失败: {e}")
        return None