#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载模块
从项目根目录的 config.json 读取配置，支持环境变量覆盖敏感信息
"""

import json
import os
from pathlib import Path
from typing import Any

# 项目根目录（scripts/ 的上一级）
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"

_cache: dict = {}


def load() -> dict:
    """加载配置文件，带缓存"""
    if _cache:
        return _cache

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        _cache.update(json.load(f))

    return _cache


def get(key: str, default: Any = None) -> Any:
    """获取配置项，支持点号路径，如 'feishu.app_id'"""
    cfg = load()
    keys = key.split(".")
    node = cfg
    for k in keys:
        if isinstance(node, dict) and k in node:
            node = node[k]
        else:
            return default
    return node


def get_path(key: str) -> Path:
    """获取路径配置项，自动拼接项目根目录"""
    relative = get(key)
    if not relative:
        raise KeyError(f"路径配置项不存在: {key}")
    return PROJECT_ROOT / relative


def get_feishu_secret(field: str = "app_secret") -> str:
    """
    获取飞书敏感配置，优先从环境变量读取
    环境变量名: FEISHU_APP_SECRET
    """
    env_key = f"FEISHU_{field.upper()}"
    env_val = os.environ.get(env_key, "")
    if env_val:
        return env_val

    # 从 feishu_oauth.py 的 token_cache 旁边的旧脚本中可能硬编码了
    # 但配置文件里不应该明文存储，优先环境变量
    val = get(f"feishu.{field}", "")
    if val:
        return val

    raise ValueError(
        f"飞书配置 '{field}' 未设置。请设置环境变量 {env_key} "
        f"或在 config.json 的 feishu.{field} 中配置"
    )


def reload():
    """清除缓存，强制重新加载"""
    _cache.clear()
    return load()
