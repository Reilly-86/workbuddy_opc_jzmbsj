#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 API 客户端
封装 Token 管理、知识库 CRUD、文档内容写入、Markdown→Block 转换
"""

import json
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import get, get_feishu_secret, get_path


class FeishuClient:
    """飞书 API 统一客户端"""

    def __init__(self):
        self._app_id = get("feishu.app_id")
        self._app_secret = get_feishu_secret("app_secret")
        self._token_cache_file = get_path("paths.token_cache")
        self._cached_uat: Optional[str] = None
        self._cached_uat_exp: float = 0

    # ─────────────────────────────────────────────
    # Token 管理
    # ─────────────────────────────────────────────

    @property
    def app_access_token(self) -> str:
        """获取 app_access_token（用于 OAuth 流程）"""
        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
            headers={"Content-Type": "application/json"},
            json={"app_id": self._app_id, "app_secret": self._app_secret},
            timeout=15,
        )
        result = resp.json()
        if result.get("code") == 0:
            return result.get("app_access_token", "")
        raise RuntimeError(f"获取 app_access_token 失败: {result}")

    @property
    def user_access_token(self) -> str:
        """获取有效的 user_access_token，自动续期"""
        # 内存缓存
        if self._cached_uat and datetime.now().timestamp() < self._cached_uat_exp - 300:
            return self._cached_uat

        # 文件缓存 + refresh
        cache = self._load_token_cache()
        uat = cache.get("user_access_token", "")
        rt = cache.get("refresh_token", "")
        exp = cache.get("expires_at", 0)

        if uat and datetime.now().timestamp() < exp - 300:
            self._cached_uat = uat
            self._cached_uat_exp = exp
            return uat

        # 尝试 refresh
        if rt:
            print("[INFO] user_access_token 过期，尝试 refresh_token 续期...")
            new_uat, new_rt = self._refresh_token(rt)
            if new_uat:
                return new_uat

        # 最后回退
        if uat:
            print("[WARN] 使用缓存 token（可能已过期），建议重新运行 feishu_oauth.py")
            return uat

        raise RuntimeError("无可用 Token，请先运行 python3 scripts/feishu_oauth.py 授权")

    def _refresh_token(self, rt: str) -> tuple:
        """用 refresh_token 续期，返回 (new_uat, new_rt)"""
        try:
            app_token = self.app_access_token
            resp = requests.post(
                "https://open.feishu.cn/open-apis/authen/v1/oidc/refresh_access_token",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {app_token}",
                },
                json={"grant_type": "refresh_token", "refresh_token": rt},
                timeout=30,
            )
            result = resp.json()
            data = result.get("data", {})
            if result.get("code") == 0 and data.get("access_token"):
                new_cache = {
                    "user_access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", rt),
                    "expires_at": datetime.now().timestamp() + data.get("expires_in", 7200),
                    "updated_at": datetime.now().isoformat(),
                }
                self._save_token_cache(new_cache)
                self._cached_uat = data["access_token"]
                self._cached_uat_exp = new_cache["expires_at"]
                print("[SUCCESS] Token 自动续期成功")
                return data["access_token"], data.get("refresh_token", rt)
        except Exception as e:
            print(f"[WARN] refresh_token 续期异常: {e}")
        return None, None

    def _load_token_cache(self) -> dict:
        if self._token_cache_file.exists():
            with open(self._token_cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_token_cache(self, data: dict):
        self._token_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._token_cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ─────────────────────────────────────────────
    # 知识库节点
    # ─────────────────────────────────────────────

    def create_wiki_node(self, title: str) -> tuple:
        """
        在知识库指定目录下创建文档节点
        返回 (node_token, obj_token)，失败返回 (None, None)
        """
        token = self.user_access_token
        space_id = get("feishu.wiki.space_id")
        parent_token = get("feishu.wiki.parent_node_token")

        url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "parent_node_token": parent_token,
            "obj_type": "docx",
            "node_type": "origin",
            "title": title,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            result = resp.json()
            if result.get("code") == 0:
                node = result.get("data", {}).get("node", {})
                return node.get("node_token", ""), node.get("obj_token", "")
            else:
                print(f"[ERROR] 知识库节点创建失败: {result}")
                return None, None
        except Exception as e:
            print(f"[ERROR] 知识库节点创建异常: {e}")
            return None, None

    # ─────────────────────────────────────────────
    # 文档内容写入
    # ─────────────────────────────────────────────

    def write_docx_content(self, doc_id: str, md_content: str):
        """将 Markdown 内容写入已创建的飞书文档"""
        token = self.user_access_token

        # 获取文档 root block
        try:
            root_resp = requests.get(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            root_result = root_resp.json()
            if root_result.get("code") != 0:
                print(f"[WARN] 获取文档信息失败: {root_result.get('msg')}")
                return
            document_block_id = root_result["data"]["document"]["document_id"]
        except Exception as e:
            print(f"[WARN] 获取文档 root block 异常: {e}")
            return

        blocks = self.md_to_blocks(md_content)
        if not blocks:
            return

        # 分批插入（每批最多 50 个 block）
        insert_url = (
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}"
            f"/blocks/{document_block_id}/children"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        for i in range(0, len(blocks), 50):
            batch = blocks[i : i + 50]
            try:
                resp = requests.post(
                    insert_url, headers=headers, json={"children": batch, "index": i}, timeout=30
                )
                if resp.json().get("code") != 0:
                    print(f"[WARN] 写入 blocks 失败 batch={i}: {resp.json().get('msg')}")
            except Exception as e:
                print(f"[WARN] 写入 blocks 异常 batch={i}: {e}")

        print(f"[INFO] 文档内容写入完成（共 {len(blocks)} 个 block）")

    # ─────────────────────────────────────────────
    # Markdown → Block 转换器
    # ─────────────────────────────────────────────

    @staticmethod
    def _parse_inline(text: str) -> list:
        """解析行内格式：加粗、斜体、行内代码"""
        pattern = re.compile(r"`([^`]+)`|\*\*([^\*]+)\*\*|\*([^\*]+)\*")
        elements = []
        last_end = 0

        for m in pattern.finditer(text):
            if m.start() > last_end:
                plain = text[last_end : m.start()]
                if plain:
                    elements.append(
                        {"type": "text_run", "text_run": {"content": plain}}
                    )
            if m.group(1) is not None:
                elements.append(
                    {
                        "type": "text_run",
                        "text_run": {
                            "content": m.group(1),
                            "text_element_style": {"inline_code": True},
                        },
                    }
                )
            elif m.group(2) is not None:
                elements.append(
                    {
                        "type": "text_run",
                        "text_run": {
                            "content": m.group(2),
                            "text_element_style": {"bold": True},
                        },
                    }
                )
            elif m.group(3) is not None:
                elements.append(
                    {
                        "type": "text_run",
                        "text_run": {
                            "content": m.group(3),
                            "text_element_style": {"italic": True},
                        },
                    }
                )
            last_end = m.end()

        if last_end < len(text):
            elements.append(
                {"type": "text_run", "text_run": {"content": text[last_end:]}}
            )
        if not elements:
            elements.append(
                {"type": "text_run", "text_run": {"content": ""}}
            )
        return elements

    def md_to_blocks(self, md: str) -> list:
        """将 Markdown 文本转换为飞书文档 Block 列表"""
        blocks = []
        for line in md.split("\n"):
            stripped = line.rstrip()
            if stripped.startswith("### "):
                blocks.append(
                    {
                        "block_type": 5,
                        "heading3": {
                            "elements": self._parse_inline(stripped[4:]),
                            "style": {},
                        },
                    }
                )
            elif stripped.startswith("## "):
                blocks.append(
                    {
                        "block_type": 4,
                        "heading2": {
                            "elements": self._parse_inline(stripped[3:]),
                            "style": {},
                        },
                    }
                )
            elif stripped.startswith("# "):
                blocks.append(
                    {
                        "block_type": 3,
                        "heading1": {
                            "elements": self._parse_inline(stripped[2:]),
                            "style": {},
                        },
                    }
                )
            elif stripped.startswith("> "):
                prefixed = [
                    {
                        "type": "text_run",
                        "text_run": {
                            "content": "> ",
                            "text_element_style": {"bold": True, "italic": True},
                        },
                    }
                ]
                for e in self._parse_inline(stripped[2:]):
                    s = e["text_run"].get("text_element_style", {})
                    e["text_run"]["text_element_style"] = {**s, "italic": True}
                    prefixed.append(e)
                blocks.append(
                    {"block_type": 2, "text": {"elements": prefixed, "style": {}}}
                )
            elif stripped == "---":
                blocks.append({"block_type": 22, "divider": {}})
            elif re.match(r"^[\-\*] ", stripped):
                blocks.append(
                    {
                        "block_type": 12,
                        "bullet": {
                            "elements": self._parse_inline(stripped[2:]),
                            "style": {},
                        },
                    }
                )
            elif re.match(r"^\d+\. ", stripped):
                m = re.match(r"^(\d+)\. (.*)", stripped)
                blocks.append(
                    {
                        "block_type": 13,
                        "ordered": {
                            "elements": self._parse_inline(m.group(2)),
                            "style": {"number": int(m.group(1))},
                        },
                    }
                )
            elif stripped:
                blocks.append(
                    {
                        "block_type": 2,
                        "text": {
                            "elements": self._parse_inline(stripped),
                            "style": {},
                        },
                    }
                )
            else:
                blocks.append(
                    {
                        "block_type": 2,
                        "text": {
                            "elements": [
                                {"type": "text_run", "text_run": {"content": ""}}
                            ],
                            "style": {},
                        },
                    }
                )
        return blocks
