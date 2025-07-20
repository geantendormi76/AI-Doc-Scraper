# modules/config.py
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    """定义一个抓取任务所需的所有配置。"""
    project_name: str
    start_url: str
    base_url: str
    # AI决策的关键字段
    fetch_strategy: str  # 'static' 或 'dynamic'
    nav_selector: str
    content_selector: str
    elements_to_remove: List[str] = field(default_factory=list)
    output_dir: str = ""

    def __post_init__(self):
        """在对象创建后，自动根据项目名称生成输出目录的路径。"""
        self.output_dir = f"scraped_docs_{self.project_name}"