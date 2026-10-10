# -*- coding: utf-8 -*-
"""
B 站数据客户端（Day 17）

为什么需要这个文件：
    B 站的搜索接口有两道门槛，直接 curl 拿不到数据：
      ① 风控：不带 buvid3 指纹会被返回 412；
      ② wbi 签名：x/web-interface/wbi/search/type 要求 URL 带 w_rid 签名，
         否则返回的是一张 HTML 错误页而不是 JSON。

    这个文件把两道门槛都封装掉，对外只暴露 search_video() 一个函数，
    server.js 和 sync_hot.py 都复用它（用 Node 跑时走逻辑一致的 server 版实现）。

wbi 签名原理（一句话）：
    从 nav 接口拿到 img_key / sub_key 两个字符串 → 拼起来按一张固定的
    64 项混淆表重排、取前 32 位，得到 mixin_key → 把请求参数按 key 排序后
    urlencode，末尾接上 mixin_key，整体做 md5，结果就是 w_rid。
    B 站服务端用同样的算法验签，对得上才返回真数据。
"""
import hashlib
import json
import time
import urllib.parse
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# wbi 混淆表：B 站前端硬编码的常量，顺序不能改（改了算出来的 w_rid 就错）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

# 缓存 busvid3 指纹与 wbi 密钥，避免每次请求都多打一次接口
_buvid3 = None
_wbi_keys = None
_wbi_fetched_at = 0
_WBI_TTL = 3600  # wbi 密钥每天轮换，缓存 1 小时足够安全


def _get(url, headers=None, timeout=25):
    """带统一 UA / Referer 的 GET，返回 (bytes, headers)。"""
    h = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com/'}
    if _buvid3:
        h['Cookie'] = f'buvid3={_buvid3}'
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers


def _fetch_json(url, headers=None):
    raw, _ = _get(url, headers)
    return json.loads(raw.decode('utf-8'))


def ensure_buvid3():
    """拿一次 buvid3 指纹并缓存。不带的请求会被风控返回 412。"""
    global _buvid3
    if _buvid3:
        return _buvid3
    try:
        raw, hdrs = _get('https://www.bilibili.com/')
        for sc in hdrs.get_all('Set-Cookie') or []:
            if sc.startswith('buvid3='):
                _buvid3 = sc.split(';')[0].split('=', 1)[1]
                break
    except Exception:
        # 拿不到也不致命，有些接口不校验；失败就让后续请求裸奔试试
        pass
    return _buvid3


def get_wbi_keys(force=False):
    """从 nav 接口拿 img_key / sub_key（带缓存，1 小时过期）。"""
    global _wbi_keys, _wbi_fetched_at
    if _wbi_keys and not force and (time.time() - _wbi_fetched_at) < _WBI_TTL:
        return _wbi_keys
    d = _fetch_json('https://api.bilibili.com/x/web-interface/nav')
    w = (d.get('data') or {}).get('wbi_img') or {}
    img_url, sub_url = w.get('img_url'), w.get('sub_url')
    if not img_url or not sub_url:
        raise RuntimeError(f'拿不到 wbi 密钥，nav 返回：{json.dumps(d, ensure_ascii=False)[:200]}')
    img_key = img_url.rsplit('/', 1)[1].split('.')[0]
    sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
    _wbi_keys = (img_key, sub_key)
    _wbi_fetched_at = time.time()
    return _wbi_keys


def _mixin_key(orig):
    """按混淆表重排后取前 32 位。"""
    return ''.join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def wbi_sign(params):
    """给参数字典加上 wts 时间戳与 w_rid 签名，返回新字典。"""
    img_key, sub_key = get_wbi_keys()
    mixin = _mixin_key(img_key + sub_key)
    p = dict(params)
    p['wts'] = int(time.time())
    # wbi 规定：过滤掉 !'()* 这几个字符，然后按 key 排序 urlencode
    p = {k: ''.join(c for c in str(v) if c not in "!'()*") for k, v in p.items()}
    query = urllib.parse.urlencode(sorted(p.items()))
    p['w_rid'] = hashlib.md5((query + mixin).encode()).hexdigest()
    return p


def search_video(keyword, order='click', page=1):
    """
    搜索视频（走 wbi 签名的正式搜索接口）。

    order: click = 按播放量 / pubdate = 按发布时间 / dm = 按弹幕数
    返回 B 站原始 JSON（code=0 表示成功，数据在 data.result）。
    """
    ensure_buvid3()
    signed = wbi_sign({
        'search_type': 'video',
        'keyword': keyword,
        'order': order,
        'page': page,
    })
    url = ('https://api.bilibili.com/x/web-interface/wbi/search/type?'
           + urllib.parse.urlencode(signed))
    return _fetch_json(url)


def video_view(bvid):
    """按 bvid 拿视频详情（含播放量/弹幕/封面，不签名也能调）。"""
    ensure_buvid3()
    return _fetch_json(f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}')


if __name__ == '__main__':
    # 自测：直接跑本文件时打印一次搜索结果，方便排查签名是否还有效
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    kw = sys.argv[1] if len(sys.argv) > 1 else '东方project'
    order = sys.argv[2] if len(sys.argv) > 2 else 'click'
    print(f'[自测] 搜索「{kw}」 order={order}  buvid3={"有" if ensure_buvid3() else "无"}')
    d = search_video(kw, order=order)
    print(f'[自测] code={d.get("code")} msg={d.get("message")}')
    for it in (d.get('data', {}).get('result') or [])[:5]:
        title = it.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
        print(f'  [{it.get("bvid")}] {title[:40]}  播放={it.get("play")}')
