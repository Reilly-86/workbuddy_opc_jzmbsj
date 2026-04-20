#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书知识库日报同步脚本（重构版）
职责：幂等检查 → 创建文档 → 写入内容 → 发送通知
- Token 管理和 API 调用委托给 feishu_client
- 通知发送委托给 notifier
- 日报 Markdown 内容由外部传入（Agent 生成）
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import get_path
from feishu_client import FeishuClient
from notifier import Notifier


# ─────────────────────────────────────────────
# 幂等保护
# ─────────────────────────────────────────────

def load_state() -> dict:
    state_file = get_path("paths.notify_state")
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    state_file = get_path("paths.notify_state")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def already_synced(today: str) -> bool:
    return load_state().get("last_notify_date") == today


def mark_synced(today: str, node_token: str):
    state = load_state()
    state["last_notify_date"] = today
    state["last_node_token"] = node_token
    save_state(state)


# ─────────────────────────────────────────────
# 核心同步逻辑
# ─────────────────────────────────────────────

def sync_wiki(
    md_content: str,
    title: Optional[str] = None,
    force: bool = False,
) -> Optional[str]:
    """
    将 Markdown 内容同步到飞书知识库

    Args:
        md_content: 日报 Markdown 内容（由 Agent 生成）
        title: 文档标题，默认自动生成日期标题
        force: 是否强制同步（忽略幂等检查）

    Returns:
        知识库文档 URL，失败返回 None
    """
    today = datetime.now().strftime("%Y-%m-%d")
    if not title:
        title = f"上海建材商机日报 · {today}"

    # 1. 幂等检查
    if not force and already_synced(today):
        print(f"[SKIP] 今日 ({today}) 已同步过，跳过")
        state = load_state()
        node_token = state.get("last_node_token", "")
        return f"https://liusong.feishu.cn/wiki/{node_token}" if node_token else None

    # 2. 创建知识库文档
    client = FeishuClient()
    node_token, obj_token = client.create_wiki_node(title)
    if not node_token or not obj_token:
        print("[ERROR] 知识库文档创建失败")
        return None

    wiki_url = f"https://liusong.feishu.cn/wiki/{node_token}"
    print(f"[INFO] 文档创建成功: {wiki_url}")

    # 3. 写入文档内容
    client.write_docx_content(obj_token, md_content)

    # 4. 发送通知
    return wiki_url


# ─────────────────────────────────────────────
# CLI 入口（向后兼容旧调用方式）
# ─────────────────────────────────────────────

def main():
    """
    独立运行模式：读取 projects.json 生成摘要并同步
    注意：推荐方式是通过 main.py 调用 sync_wiki()，传入 Agent 生成的 Markdown
    """
    import re

    print("=" * 52)
    print("飞书知识库日报同步 — 建筑模版商机")
    print("=" * 52)

    today = datetime.now().strftime("%Y-%m-%d")

    # 读取项目数据
    projects_file = get_path("paths.projects")
    if not projects_file.exists():
        print(f"[ERROR] 数据文件不存在: {projects_file}")
        sys.exit(1)

    with open(projects_file, "r", encoding="utf-8") as f:
        projects = json.load(f)
    print(f"[INFO] 读取 {len(projects)} 个项目")

    # 生成简要摘要（兼容旧模式，新流程应通过 main.py 传入 Agent 生成的 MD）
    total = len(projects)
    new_projects = [p for p in projects if p.get("is_new")]
    high_priority = [p for p in projects if p.get("bd_priority", 0) == 3]

    md = f"# 上海建材模板商机日报 · {today}\n\n"
    md += "## 今日概览\n\n"
    md += f"- **项目总数**：{total} 个跟踪项目\n"
    md += f"- **今日新增**：{len(new_projects)} 个项目\n"
    md += f"- **高优先级**（⭐⭐⭐）：{len(high_priority)} 个项目\n"
    md += f"\n> 详细内容请查看 HTML 完整报告\n"

    # 同步
    wiki_url = sync_wiki(md)
    if not wiki_url:
        sys.exit(1)

    # 发送通知
    notifier = Notifier()
    notifier.send_card(
        title=f"📊 上海建材商机日报 · {today}",
        summary_lines=[
            f"🆕 今日新增：{len(new_projects)} 个项目",
            f"🏗️ 累计跟踪：{total} 个项目",
            f"⭐⭐⭐ 高优先级：{len(high_priority)} 个项目",
        ],
        wiki_url=wiki_url,
    )

    # 标记完成
    state = load_state()
    node_token = wiki_url.split("/")[-1]
    mark_synced(today, node_token)

    print("=" * 52)
    print("同步完成!")
    print("=" * 52)


if __name__ == "__main__":
    main()
