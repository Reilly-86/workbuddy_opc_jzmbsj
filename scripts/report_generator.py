#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 报告生成模块
读取 projects.json → 用 Jinja2 模板渲染 → 输出 report.html
"""

import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import get, get_path


def load_projects(path: Path = None) -> list:
    """加载项目数据"""
    if path is None:
        path = get_path("paths.projects")
    if not path.exists():
        raise FileNotFoundError(f"项目数据文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_stats(projects: list) -> dict:
    """计算统计数据"""
    total = len(projects)
    new_count = sum(1 for p in projects if p.get("is_new"))
    active_count = total - new_count
    high = sum(1 for p in projects if p.get("bd_priority", 0) == 3)
    mid = sum(1 for p in projects if p.get("bd_priority", 0) == 2)
    low = total - high - mid

    # 按类别统计
    cat_counter = Counter(p.get("category", "其他") for p in projects)
    tech = cat_counter.get("科技产业", 0)
    social = cat_counter.get("社会民生", 0)

    # 筛选按钮用的分类列表
    cat_icons = {
        "科技产业": "🏭", "社会民生": "🏥", "城市基础设施": "🚇",
        "生态文明": "🌿", "城乡融合": "🏘️",
    }
    filter_categories = [
        {"name": name, "count": count, "icon": cat_icons.get(name, "📌")}
        for name, count in cat_counter.most_common()
        if count >= 1
    ]

    # 判断新开工项目的年份
    new_projects = [p for p in projects if p.get("is_new")]
    period = "2026年"
    for p in new_projects[:5]:
        sd = str(p.get("start_date", ""))
        if "2025" in sd:
            period = "2025-2026年"
            break

    return {
        "total": total,
        "new_count": new_count,
        "active_count": active_count,
        "high_priority": high,
        "mid_priority": mid,
        "low_priority": low,
        "tech_count": tech,
        "social_count": social,
        "period": period,
        "filter_categories": filter_categories,
    }


def generate_report(
    projects: list = None,
    output_path: Path = None,
    template_path: Path = None,
) -> Path:
    """
    生成 HTML 报告

    Args:
        projects: 项目数据列表，默认从 projects.json 加载
        output_path: 输出路径，默认 config 中配置的路径
        template_path: 模板路径，默认 config 中配置的路径

    Returns:
        输出文件路径
    """
    if projects is None:
        projects = load_projects()
    if output_path is None:
        output_path = get_path("paths.report_output")
    if template_path is None:
        template_path = get_path("paths.report_template")

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 计算 stats
    stats = compute_stats(projects)

    # Banner 信息
    today = datetime.now().strftime("%Y年%m月%d日")
    banner = {
        "title": f"{today} 日报更新",
        "description": (
            f"已筛选出 <strong>{stats['total']}个</strong> 与建材模板BD相关度高的在建项目，"
            f"其中 <strong>{stats['new_count']}个为{stats['period']}新开工</strong>，BD切入时机最佳。"
        ),
    }

    # Jinja2 渲染
    project_root = Path(__file__).parent.parent
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=False,
    )
    template = env.get_template(template_path.name)

    # 项目排序：新增在前，然后按优先级降序
    sorted_projects = sorted(
        projects,
        key=lambda p: (0 if p.get("is_new") else 1, -p.get("bd_priority", 0)),
    )

    html = template.render(
        title=get("project.region", "上海") + "在建工地商机日报",
        stats=stats,
        banner=banner,
        filter_categories=stats["filter_categories"],
        projects_json=json.dumps(sorted_projects, ensure_ascii=False),
        update_time=today,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] HTML 报告已生成: {output_path}")
    print(f"     项目总数: {stats['total']}, 新增: {stats['new_count']}, 高优先级: {stats['high_priority']}")
    return output_path


if __name__ == "__main__":
    generate_report()
