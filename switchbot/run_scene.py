#!/usr/bin/env python3
"""SwitchBot のシーン（手動シーン）を名前または ID で実行する。

SwitchBot API v1.1 を使う。標準ライブラリのみで動く。

使い方:
    SWITCHBOT_TOKEN=... SWITCHBOT_SECRET=... python3 run_scene.py --list
    SWITCHBOT_TOKEN=... SWITCHBOT_SECRET=... python3 run_scene.py --scene 下上
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

API_BASE = "https://api.switch-bot.com/v1.1"


def build_headers(token, secret):
    t = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    sign = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            (token + t + nonce).encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "sign": sign,
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json; charset=utf-8",
    }


def call(method, path, token, secret, retries=3):
    """API を叩いて body を返す。一時的な失敗は指数バックオフで再試行する。"""
    url = API_BASE + path
    last_error = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url, method=method, headers=build_headers(token, secret)
        )
        if method == "POST":
            req.data = b"{}"
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                body = json.loads(res.read().decode("utf-8"))
            if body.get("statusCode") == 100:
                return body
            # 190 などのサーバ側エラーは再試行の価値がある
            last_error = "API error: {} {}".format(
                body.get("statusCode"), body.get("message")
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = "{}: {}".format(type(exc).__name__, exc)
        if attempt < retries - 1:
            wait = 2 ** (attempt + 1)
            print("  失敗（{}）。{}秒後に再試行".format(last_error, wait), file=sys.stderr)
            time.sleep(wait)
    raise SystemExit("SwitchBot API 呼び出しに失敗: {}".format(last_error))


def list_scenes(token, secret):
    return call("GET", "/scenes", token, secret)["body"]


def main():
    parser = argparse.ArgumentParser(description="SwitchBot のシーンを実行する")
    parser.add_argument(
        "--scene",
        default=os.environ.get("SWITCHBOT_SCENE"),
        help="シーン名またはシーンID（環境変数 SWITCHBOT_SCENE でも指定可）",
    )
    parser.add_argument(
        "--list", action="store_true", help="登録されているシーンの一覧を表示して終了"
    )
    args = parser.parse_args()

    token = os.environ.get("SWITCHBOT_TOKEN")
    secret = os.environ.get("SWITCHBOT_SECRET")
    if not token or not secret:
        raise SystemExit(
            "環境変数 SWITCHBOT_TOKEN と SWITCHBOT_SECRET を設定してください"
        )

    scenes = list_scenes(token, secret)

    if args.list:
        if not scenes:
            print("手動シーンが1件もありません。")
            print("（アプリの「オートメーション」は API から実行できません。README を参照）")
            return
        print("登録されている手動シーン:")
        for scene in scenes:
            print("  {}\t{}".format(scene["sceneId"], scene["sceneName"]))
        return

    if not args.scene:
        raise SystemExit("--scene でシーン名かIDを指定してください")

    by_name = [s for s in scenes if s["sceneName"] == args.scene]
    by_id = [s for s in scenes if s["sceneId"] == args.scene]
    matched = by_name or by_id

    if not matched:
        names = ", ".join(s["sceneName"] for s in scenes) or "(なし)"
        raise SystemExit(
            "シーン「{}」が見つかりません。利用できるシーン: {}".format(args.scene, names)
        )
    if len(matched) > 1:
        raise SystemExit(
            "シーン名「{}」が複数あります。--scene にシーンIDを指定してください: {}".format(
                args.scene, ", ".join(s["sceneId"] for s in matched)
            )
        )

    scene = matched[0]
    print("実行: {} ({})".format(scene["sceneName"], scene["sceneId"]))
    call("POST", "/scenes/{}/execute".format(scene["sceneId"]), token, secret)
    print("実行しました。")


if __name__ == "__main__":
    main()
