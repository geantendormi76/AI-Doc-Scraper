# manual_configs.py
from modules.config import Config

# 这是由人类专家编写的、经过验证的、保证100%可靠的配置。
# 当AI自动规划失败时，可以在这里添加手动配置作为最终解决方案。

ROS_HUMBLE_CONFIG = Config(
    project_name="ros_humble_manual",
    start_url="https://docs.ros.org/en/humble/index.html",
    base_url="https://docs.ros.org/en/humble/",
    fetch_strategy='static',  # ROS文档是静态的，使用高速模式
    nav_selector="div.wy-menu-vertical",
    content_selector="div[role='main']",
    elements_to_remove=[
        "div.admonition-warning",
        "a.headerlink"
    ]
)

# 你未来可以为其他棘手的网站在这里添加更多手动配置
# ANOTHER_HARD_SITE_CONFIG = Config(...)