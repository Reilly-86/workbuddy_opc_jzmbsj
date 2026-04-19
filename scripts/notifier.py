#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知模块
统一管理飞书卡片通知，预留其他通知渠道扩展
"""

import requests
from typing import Optional

from config import get


class Notifier:
    """飞书 Webhook 通知"""

    def __init__(self):
        self.webhook_url = get("feishu.webhook")
        self.github_url = get("github_pages.url")

    def send_card(
        self,
        title: str,
        summary_lines: list[str],
        wiki_url: Optional[str] = None,
    ) -> bool:
        """
        发送飞书互动卡片

        Args:
            title: 卡片标题
            summary_lines: 摘要内容行（列表，每行一个要点）
            wiki_url: 飞书知识库文档链接（可选）
        """
        elements = []

        # 摘要内容
        content_md = "\n".join(f"**{line}**" for line in summary_lines)
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content_md}})

        # 知识库链接
        if wiki_url:
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📚 飞书日报**：[点击查看]({wiki_url})",
                    },
                }
            )

        # GitHub Pages 链接
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🌐 完整报告**：[点击查看]({self.github_url})",
                },
            }
        )

        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": "⚡ 建筑模板商机系统 · 每日自动更新"}
                ],
            }
        )

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": elements,
            },
        }

        try:
            resp = requests.post(self.webhook_url, json=card, timeout=30)
            result = resp.json()
            ok = result.get("code") == 0 or result.get("StatusCode") == 0
            if ok:
                print("[OK] 飞书卡片通知发送成功")
            else:
                print(f"[WARN] 飞书通知响应异常: {result}")
            return ok
        except Exception as e:
            print(f"[ERROR] 飞书通知发送异常: {e}")
            return False
