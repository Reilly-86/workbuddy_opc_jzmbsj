#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 OAuth 授权助手 v2
用途：通过本地 HTTP 服务器自动接收 OAuth code，完成 user_access_token 获取
使用方法：
  python3 scripts/feishu_oauth.py
  → 自动打开浏览器 → 点授权 → 自动写入 token_cache.json
"""

import json
import sys
import time
import webbrowser
import threading
import requests
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode

from config import get, get_feishu_secret, PROJECT_ROOT

# ============ 配置区域（从 config.json 读取） ============
APP_ID       = get("feishu.app_id")
APP_SECRET   = get_feishu_secret()
REDIRECT_URI = "http://localhost:9999/callback"
TOKEN_CACHE  = PROJECT_ROOT / "scripts" / "token_cache.json"
# ==================================

_received_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _received_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/callback" and "code" in params:
            _received_code = params["code"][0]
            html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<title>授权成功</title>"
                "<style>body{font-family:sans-serif;text-align:center;padding:80px;background:#f0f9ff;}"
                "h1{color:#0ea5e9;}p{color:#64748b;font-size:16px;}</style></head>"
                "<body><h1>&#10003; 授权成功！</h1>"
                "<p>user_access_token 已自动保存，可以关闭此窗口了。</p>"
                "</body></html>"
            )
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid callback")

    def log_message(self, format, *args):
        pass


def load_token_cache() -> dict:
    if TOKEN_CACHE.exists():
        with open(TOKEN_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_token_cache(data: dict):
    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Token 已保存到: {TOKEN_CACHE}")


def try_refresh() -> bool:
    cache = load_token_cache()
    rt = cache.get("refresh_token", "")
    if not rt:
        return False

    print("[INFO] 检测到 refresh_token，尝试自动续期...")
    app_token_resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        headers={"Content-Type": "application/json"},
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=15,
    )
    app_token = app_token_resp.json().get("app_access_token", "")
    if not app_token:
        print("[WARN] 获取 app_access_token 失败，无法续期")
        return False

    url = "https://open.feishu.cn/open-apis/authen/v1/oidc/refresh_access_token"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {app_token}"}
    payload = {"grant_type": "refresh_token", "refresh_token": rt}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        result = resp.json()
        data = result.get("data", {})
        if result.get("code") == 0 and data.get("access_token"):
            cache.update({
                "user_access_token": data["access_token"],
                "refresh_token":     data.get("refresh_token", rt),
                "expires_at":        datetime.now().timestamp() + data.get("expires_in", 7200),
                "updated_at":        datetime.now().isoformat(),
            })
            save_token_cache(cache)
            print(f"[SUCCESS] 自动续期成功！有效期: {data.get('expires_in', 7200)//3600} 小时")
            return True
        else:
            print(f"[WARN] 续期失败 (code={result.get('code')}): {result.get('msg')} — 需要重新授权")
            return False
    except Exception as e:
        print(f"[WARN] 续期请求异常: {e}")
        return False


def _get_app_access_token() -> str:
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        headers={"Content-Type": "application/json"},
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=15,
    )
    result = resp.json()
    if result.get("code") == 0:
        return result.get("app_access_token", "")
    raise RuntimeError(f"获取 app_access_token 失败: {result}")


def exchange_code(code: str) -> bool:
    print(f"\n[INFO] 正在用 code 换取 token...")
    app_token = _get_app_access_token()
    url = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {app_token}"}
    payload = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        result = resp.json()
        data = result.get("data", {})

        if result.get("code") == 0 and data.get("access_token"):
            cache = {
                "user_access_token": data["access_token"],
                "refresh_token":     data.get("refresh_token", ""),
                "expires_at":        datetime.now().timestamp() + data.get("expires_in", 7200),
                "updated_at":        datetime.now().isoformat(),
            }
            save_token_cache(cache)
            print(f"[SUCCESS] 授权成功！")
            print(f"  有效期: {data.get('expires_in', 7200)//3600} 小时")
            refresh_tk = data.get("refresh_token", "")
            if refresh_tk:
                print(f"  refresh_token: ✅ 已保存（30天内可自动续期）")
            return True
        else:
            print(f"[ERROR] 换取 token 失败: code={result.get('code')} msg={result.get('msg')}")
            return False
    except Exception as e:
        print(f"[ERROR] 请求异常: {e}")
        return False


def main():
    global _received_code

    print("=" * 60)
    print("飞书 OAuth 授权助手 v2 — 建筑模版商机")
    print("=" * 60)

    if try_refresh():
        return

    print("\n[INFO] 需要重新授权，启动本地回调服务...")
    server = HTTPServer(("localhost", 9999), CallbackHandler)
    server.timeout = 1

    params = {
        "app_id":        APP_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "wiki:wiki docx:document auth:user.id:read",
    }
    auth_url = "https://open.feishu.cn/open-apis/authen/v1/authorize?" + urlencode(params)

    print(f"\n[INFO] 正在打开浏览器，请用飞书账号完成授权...")
    print(f"  授权链接（若浏览器未自动打开，请手动复制此链接）:\n  {auth_url}\n")

    def open_browser():
        time.sleep(1)
        webbrowser.open(auth_url)

    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    print("[INFO] 等待授权回调（最多 2 分钟）...")
    deadline = time.time() + 120
    while time.time() < deadline:
        server.handle_request()
        if _received_code:
            break

    server.server_close()

    if not _received_code:
        print("[ERROR] 超时未收到授权回调，请重试")
        sys.exit(1)

    print(f"[INFO] 收到授权 code: {_received_code[:10]}...")

    if not exchange_code(_received_code):
        sys.exit(1)

    print("\n✅ 授权完成！后续脚本会自动续期，30 天内无需重复操作。")


if __name__ == "__main__":
    main()
