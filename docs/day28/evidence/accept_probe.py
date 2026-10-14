#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 结营验收 · B 类「真实读写 + 持久化」探针

按公网验收（用户选择），全部打真实线上地址。
验完即清理（DELETE 掉自己写进去的那条），保证不污染真库基线。

跑法（必须用 venv Python，且清掉代理环境变量）：
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
    C:/Users/25394/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
    docs/day28/evidence/accept_probe.py

输出同时写 stdout 和 accept_probe_log.txt（venv stdout 有时会被 sandbox 吞掉）。
"""
import json
import os
import time
import urllib.request
import urllib.error

SITE = os.environ.get("SITE", "https://touhou-mock.app.workbuddy.host")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accept_probe_log.txt")

_lines = []


def log(msg=""):
    print(msg)
    _lines.append(str(msg))


def req(method, path, body=None, timeout=25):
    """发一个请求，返回 (status, parsed_json_or_text, raw_bytes)。不抛异常，错误也如实返回。"""
    url = SITE + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, _parse(raw), raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, _parse(raw), raw
    except Exception as e:  # 网络层错误也如实记录
        return -1, {"_error": repr(e)}, b""


def _parse(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return raw.decode("utf-8", "replace")


def main():
    log("=" * 68)
    log("Day 28 结营验收 · B 类 真实读写 + 持久化")
    log("站点：%s" % SITE)
    log("时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 68)

    # ---------- B1 读：收藏列表基线 ----------
    log("\n【B1】读收藏列表（基线）")
    st, js, _ = req("GET", "/api/favorites?limit=50")
    base_count = js.get("count") if isinstance(js, dict) else None
    base_ids = [x.get("id") for x in js.get("data", [])] if isinstance(js, dict) else []
    log("  HTTP %s  source=%s  count=%s" % (st, js.get("source"), base_count))
    log("  现有 id：%s" % base_ids)
    b1_pass = st == 200 and isinstance(js, dict) and js.get("source") == "rest"
    log("  → %s" % ("PASS" if b1_pass else "FAIL"))

    # ---------- B2 写：新增一条收藏 ----------
    # 选一个当前没被收藏的 workId，避免撞 409 干扰验证
    all_works_st, all_works, _ = req("GET", "/api/circles")
    candidate = "art-2"
    log("\n【B2】写入一条收藏 POST /api/favorites {workId:%r}" % candidate)
    st, js, raw = req("POST", "/api/favorites", {"workId": candidate, "note": "Day28验收探针（验完即删）"})
    log("  HTTP %s" % st)
    log("  响应：%s" % json.dumps(js, ensure_ascii=False)[:300])
    new_id = js.get("data", {}).get("id") if isinstance(js, dict) else None
    b2_pass = st in (200, 201) and isinstance(js, dict) and js.get("ok") is True
    if st == 409:
        b2_pass = False
        log("  !! 撞到 409：说明候选 workId 已被占用，探针需换一个 id")
    log("  → %s  （新行 id=%s）" % ("PASS" if b2_pass else "FAIL", new_id))

    # ---------- B3 写后读：计数 +1 ----------
    log("\n【B3】写后立即读回，验证计数 +1")
    st, js, _ = req("GET", "/api/favorites?limit=50")
    after_count = js.get("count") if isinstance(js, dict) else None
    after_ids = [x.get("id") for x in js.get("data", [])] if isinstance(js, dict) else []
    log("  HTTP %s  count=%s（基线 %s）" % (st, after_count, base_count))
    log("  id 列表：%s" % after_ids)
    b3_pass = (after_count == (base_count or 0) + 1) and (new_id in after_ids)
    log("  → %s" % ("PASS" if b3_pass else "FAIL"))

    # ---------- B4 持久化：等一会儿再读（跨请求、跨时间）----------
    log("\n【B4】持久化复核：间隔 6 秒后再次独立读取")
    time.sleep(6)
    st, js, _ = req("GET", "/api/favorites?limit=50")
    later_count = js.get("count") if isinstance(js, dict) else None
    later_ids = [x.get("id") for x in js.get("data", [])] if isinstance(js, dict) else []
    row = next((x for x in js.get("data", []) if x.get("id") == new_id), None) if isinstance(js, dict) else None
    log("  HTTP %s  count=%s" % (st, later_count))
    log("  新行仍在？%s" % ("是" if row else "否"))
    if row:
        log("  新行内容：workId=%s  note=%s  createdAt=%s" % (row.get("workId"), row.get("note"), row.get("createdAt")))
    b4_pass = bool(row) and later_count == after_count
    log("  → %s" % ("PASS" if b4_pass else "FAIL"))

    # ---------- B5 数据源确实是真库 ----------
    log("\n【B5】数据源核对：source 必须是 rest（不是 snapshot 兜底）")
    srcs = []
    for p in ["/api/favorites?limit=1", "/api/hot?board=fresh&limit=1", "/api/works?category=music&limit=1", "/api/circles"]:
        st, js, _ = req("GET", p)
        s = js.get("source") if isinstance(js, dict) else None
        srcs.append((p, s))
        log("  %-42s source=%s" % (p, s))
    b5_pass = all(s == "rest" for _, s in srcs)
    log("  → %s" % ("PASS" if b5_pass else "FAIL"))

    # ---------- B6 防重复闸门 ----------
    log("\n【B6】防重复：对刚才写入的同一条再 POST 一次，应回 409")
    st, js, _ = req("POST", "/api/favorites", {"workId": candidate})
    log("  HTTP %s" % st)
    log("  响应：%s" % json.dumps(js, ensure_ascii=False)[:200])
    b6_pass = st == 409
    log("  → %s" % ("PASS" if b6_pass else "FAIL"))

    # ---------- B7 清理，恢复基线 ----------
    log("\n【B7】清理测试数据 DELETE /api/favorites/%s，恢复基线" % new_id)
    if new_id is not None:
        st, js, _ = req("DELETE", "/api/favorites/%s" % new_id)
        log("  HTTP %s  %s" % (st, json.dumps(js, ensure_ascii=False)[:200]))
    st, js, _ = req("GET", "/api/favorites?limit=50")
    final_count = js.get("count") if isinstance(js, dict) else None
    final_ids = [x.get("id") for x in js.get("data", [])] if isinstance(js, dict) else []
    log("  清理后 count=%s（基线 %s）" % (final_count, base_count))
    log("  清理后 id：%s" % final_ids)
    b7_pass = final_count == base_count and new_id not in final_ids
    log("  → %s" % ("PASS" if b7_pass else "FAIL"))

    # ---------- 汇总 ----------
    log("\n" + "=" * 68)
    results = [("B1 读收藏列表(基线)", b1_pass), ("B2 写入收藏", b2_pass),
               ("B3 写后计数+1", b3_pass), ("B4 持久化复核", b4_pass),
               ("B5 source=rest", b5_pass), ("B6 防重复 409", b6_pass),
               ("B7 清理恢复基线", b7_pass)]
    for name, ok in results:
        log("  %-22s %s" % (name, "PASS" if ok else "FAIL"))
    log("  小计：%d/%d PASS" % (sum(1 for _, o in results if o), len(results)))
    log("=" * 68)

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_lines))


if __name__ == "__main__":
    main()
