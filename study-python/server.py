# -*- coding: utf-8 -*-
"""Study Hub 后端：静态托管 + 热榜抓取 + 图片防盗链代理"""
import os, time, random, hashlib
import requests
from flask import Flask, Response, request, jsonify, send_from_directory

STATIC_DIR = os.environ.get("STATIC_DIR", "/srv/static")
HOT_BASE = "https://60s.viki.moe/v2/"
HOT_MAP = {"zhihu": "zhihu", "weibo": "weibo", "xhs": "douyin", "wechat": "toutiao"}
HOT_TTL = 600  # 热榜缓存 10 分钟

IMG_CACHE_DIR = os.environ.get("IMG_CACHE_DIR", "/tmp/imgcache")
os.makedirs(IMG_CACHE_DIR, exist_ok=True)

# 图片防盗链：按域名带对应 Referer
IMG_REFERS = {
    "zhimg.com": "https://www.zhihu.com/",
    "douyinpic.com": "https://www.douyin.com/",
    "toutiaoimg.com": "https://www.toutiao.com/",
    "byteimg.com": "https://www.toutiao.com/",
    "weibo": "https://weibo.com/",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

app = Flask(__name__, static_folder=None)

# ---------------- 热榜（服务端缓存） ----------------
_hot_cache = {}  # src -> (timestamp, json)

def get_hot(src):
    now = time.time()
    hit = _hot_cache.get(src)
    if hit and now - hit[0] < HOT_TTL:
        return hit[1]
    r = requests.get(HOT_BASE + src, timeout=10, headers={"User-Agent": UA})
    j = r.json()
    _hot_cache[src] = (now, j)
    return j

@app.get("/api/hot/<pf>")
def hot(pf):
    if pf not in HOT_MAP:
        return jsonify({"data": []})
    try:
        j = get_hot(HOT_MAP[pf])
    except Exception:
        return jsonify({"data": []})
    data = j.get("data") or []
    # 微博热榜本身没有配图：从抖音热榜封面池随机配新闻图，让微博帖子像真的图文微博
    if pf == "weibo" and data:
        try:
            dy = (get_hot("douyin").get("data") or [])
            covers = [x["cover"] for x in dy if x.get("cover")]
            if covers:
                for item in data:
                    item["images"] = random.sample(covers, min(random.randint(1, 3), len(covers)))
        except Exception:
            pass
    return jsonify({"data": data})

# ---------------- 图片防盗链代理（磁盘缓存） ----------------
@app.get("/img")
def img_proxy():
    url = (request.args.get("url") or "").strip()
    if not url.startswith("http"):
        return ("", 400)
    key = hashlib.md5(url.encode()).hexdigest()
    path = os.path.join(IMG_CACHE_DIR, key)
    if os.path.exists(path) and os.path.getsize(path) > 100:
        with open(path, "rb") as f:
            data = f.read()
        return Response(data, mimetype="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    referer = next((v for k, v in IMG_REFERS.items() if k in url), None)
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    try:
        r = requests.get(url, headers=headers, timeout=12)
    except Exception:
        return ("", 404)
    if r.status_code != 200 or len(r.content) < 100:
        return ("", 404)
    with open(path, "wb") as f:
        f.write(r.content)
    ct = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
    return Response(r.content, mimetype=ct,
                    headers={"Cache-Control": "public, max-age=86400"})

# ---------------- 静态托管 ----------------
@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

@app.get("/<path:p>")
def static_files(p):
    # 服务端代码不允许被当成静态文件下载
    if p.startswith("server.py") or p.startswith("Dockerfile") or "/study-python/" in "/" + p:
        return ("", 404)
    return send_from_directory(STATIC_DIR, p)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, threaded=True)
