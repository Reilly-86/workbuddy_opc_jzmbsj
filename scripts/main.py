#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 主入口
编排：数据对比 → 历史快照 → HTML报告 → 飞书知识库 → 通知 → Git推送
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import get_path, get


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def project_hash(name: str) -> str:
    """生成项目稳定 ID（名称 MD5 前 8 位）"""
    normalized = name.strip().replace(" ", "").replace("\u3000", "")
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]


# ─────────────────────────────────────────────
# 数据对比 & 历史快照
# ─────────────────────────────────────────────

def save_history_snapshot(projects: list, date_str: str):
    """保存当日数据快照"""
    history_dir = get_path("paths.history_dir")
    history_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = history_dir / f"{date_str}.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)
    print(f"[OK] 历史快照已保存: {snapshot_file}")


def load_yesterday_snapshot(date_str: str) -> Optional[list]:
    """加载最近一个历史快照（不一定昨天，取最近日期）"""
    history_dir = get_path("paths.history_dir")
    if not history_dir.exists():
        return None

    snapshots = sorted(history_dir.glob("*.json"))
    # 排除今天
    today_file = history_dir / f"{date_str}.json"
    snapshots = [s for s in snapshots if s != today_file]
    if not snapshots:
        return None

    latest = snapshots[-1]
    with open(latest, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_diff(current: list, previous: Optional[list]) -> tuple:
    """
    增量对比：标记新增项目，分配稳定 ID
    返回 (updated_projects, new_count)
    """
    if not previous:
        # 首次运行，所有项目标记为新增
        for p in current:
            p["id"] = project_hash(p.get("name", ""))
            p["is_new"] = True
            if not p.get("first_seen"):
                p["first_seen"] = datetime.now().strftime("%Y-%m-%d")
        return current, len(current)

    # 构建历史 ID 集合
    old_ids = set()
    for p in previous:
        # 兼容旧格式（整数 ID）和新格式（哈希 ID）
        pid = p.get("id")
        name = p.get("name", "")
        if pid and isinstance(pid, str) and len(pid) == 8:
            old_ids.add(pid)
        elif name:
            old_ids.add(project_hash(name))

    new_count = 0
    for p in current:
        p["id"] = project_hash(p.get("name", ""))
        if p["id"] not in old_ids:
            p["is_new"] = True
            p["first_seen"] = datetime.now().strftime("%Y-%m-%d")
            new_count += 1
        else:
            p["is_new"] = False
            # 保留原有的 first_seen
            for old in previous:
                old_id = old.get("id")
                if not old_id or isinstance(old_id, int):
                    if old.get("name") == p.get("name"):
                        p["first_seen"] = old.get("first_seen", p.get("first_seen"))
                        break
                elif old_id == p["id"]:
                    p["first_seen"] = old.get("first_seen", p.get("first_seen"))
                    break

    return current, new_count


# ─────────────────────────────────────────────
# Git 推送
# ─────────────────────────────────────────────

def git_push(date_str: str):
    """Git commit + push 更新 GitHub Pages"""
    project_root = Path(__file__).parent.parent
    try:
        subprocess.run(
            ["git", "add", "report.html", "data/projects.json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"日报更新: {date_str}"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("[OK] Git push 成功")
        else:
            print(f"[WARN] Git push 失败（Token 可能过期）: {result.stderr[:200]}")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Git 操作异常: {e}")
    except Exception as e:
        print(f"[WARN] Git push 超时或异常: {e}")


# ─────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────

def run(
    report_md: Optional[str] = None,
    skip_git: bool = False,
    force_wiki: bool = False,
):
    """
    执行完整 Pipeline

    Args:
        report_md: Agent 生成的飞书日报 Markdown 内容（可选）
        skip_git: 是否跳过 Git 推送
        force_wiki: 是否强制同步飞书知识库（忽略幂等）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    print("=" * 52)
    print(f"Pipeline 开始运行 · {today}")
    print("=" * 52)

    # Step 1: 加载数据
    projects_file = get_path("paths.projects")
    if not projects_file.exists():
        print(f"[ERROR] 数据文件不存在: {projects_file}")
        print("[INFO] 请先通过 AI Agent 完成数据采集和 projects.json 写入")
        sys.exit(1)

    with open(projects_file, "r", encoding="utf-8") as f:
        projects = json.load(f)
    print(f"[INFO] 加载 {len(projects)} 个项目")

    # Step 2: 增量对比 & ID 稳定化
    previous = load_yesterday_snapshot(today)
    projects, new_count = compute_diff(projects, previous)
    print(f"[INFO] 增量对比完成: 新增 {new_count} 个项目")

    # Step 3: 保存数据 & 历史快照
    with open(projects_file, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)
    save_history_snapshot(projects, today)

    # Step 4: 生成 HTML 报告
    from report_generator import generate_report
    generate_report(projects)

    # Step 5: 飞书知识库同步
    wiki_url = None
    if report_md:
        from feishu_wiki_sync import sync_wiki
        try:
            wiki_url = sync_wiki(report_md, force=force_wiki)
        except Exception as e:
            print(f"[WARN] 飞书知识库同步失败: {e}")
    else:
        print("[INFO] 未提供日报 Markdown，跳过飞书知识库同步")

    # Step 6: 发送通知
    if new_count > 0 or report_md:
        from notifier import Notifier
        try:
            notifier = Notifier()
            high_count = sum(1 for p in projects if p.get("bd_priority", 0) == 3)
            notifier.send_card(
                title=f"📊 建材商机日报 · {today}",
                summary_lines=[
                    f"🆕 今日新增：{new_count} 个项目",
                    f"🏗️ 累计跟踪：{len(projects)} 个项目",
                    f"⭐⭐⭐ 高优先级：{high_count} 个项目",
                ],
                wiki_url=wiki_url,
            )
        except Exception as e:
            print(f"[WARN] 通知发送失败: {e}")

    # Step 7: Git push
    if not skip_git:
        git_push(today)

    print("=" * 52)
    print("Pipeline 运行完成!")
    print("=" * 52)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="建筑模版商机系统 Pipeline")
    parser.add_argument("--report-md", type=str, help="Agent 生成的飞书日报 Markdown 文件路径")
    parser.add_argument("--skip-git", action="store_true", help="跳过 Git push")
    parser.add_argument("--force-wiki", action="store_true", help="强制同步飞书知识库")
    parser.add_argument("--gen-report-only", action="store_true", help="仅生成 HTML 报告")
    args = parser.parse_args()

    if args.gen_report_only:
        from report_generator import generate_report
        generate_report()
        return

    report_md = None
    if args.report_md:
        md_path = Path(args.report_md)
        if md_path.exists():
            report_md = md_path.read_text(encoding="utf-8")
        else:
            print(f"[WARN] Markdown 文件不存在: {args.report_md}")

    run(
        report_md=report_md,
        skip_git=args.skip_git,
        force_wiki=args.force_wiki,
    )


if __name__ == "__main__":
    main()
