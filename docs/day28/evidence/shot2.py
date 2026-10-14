#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 · 截图 2：作品公网 URL 打开的样子（**带地址栏**）

★ 关键区别：
  CDP 的 Page.captureScreenshot 只能截「网页内容」，**截不到浏览器地址栏**。
  要拍到地址栏，必须用**系统级窗口截图**（Windows PrintWindow / BitBlt）。

方案：
  1) 用 Edge 打开公网地址（真实窗口，不 headless）
  2) 等页面渲染完
  3) 用 ctypes 调 Windows API 对该窗口做 PrintWindow 截图 → 含地址栏 + 完整页面
  4) 若 PrintWindow 拿不到内容，退化为「截取整个屏幕中该窗口所在区域」
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://touhou-mock.app.workbuddy.host/"
OUT = os.path.join(HERE, "day28-截图2-公网作品URL.png")
OUT_SOFT = os.path.join(HERE, "day28-截图2b-公网作品-板块页.png")
PORT = 9383
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

log_lines = []


def log(m=""):
    print(m)
    log_lines.append(str(m))
    # ★ 增量写日志：GDI 调用可能让进程直接崩溃（段错误），
    #   只在 finally 写的话什么都留不下来。所以每步都落盘。
    try:
        with open(os.path.join(HERE, "_s2_log.txt"), "a", encoding="utf-8") as f:
            f.write(str(m) + "\n")
    except Exception:
        pass


# ---------------- Windows 窗口截图 ----------------
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def find_window_by_pid(pid):
    """按进程 ID 找主窗口 —— Edge 的渲染进程与浏览器主进程 PID 不同，此法常失效。"""
    result = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        wpid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            ln = user32.GetWindowTextLengthW(hwnd)
            if ln > 0:
                buf = ctypes.create_unicode_buffer(ln + 1)
                user32.GetWindowTextW(hwnd, buf, ln + 1)
                rect = wt.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                result.append((hwnd, buf.value, rect.right - rect.left, rect.bottom - rect.top))
        return True

    user32.EnumWindows(cb, 0)
    result.sort(key=lambda x: x[2] * x[3], reverse=True)
    return result[0] if result else None


def find_browser_window(title_hint="touhou", min_w=400, min_h=300):
    """
    按**窗口标题关键词**找浏览器窗口（不依赖 PID）。

    ★ 为什么改按标题找：Edge 是多进程架构，我们用 Popen 启动的是浏览器主进程，
      但窗口可能挂在别的进程上 → 按 pid 匹配会全军覆没（Day 28 实测）。
    """
    result = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        ln = user32.GetWindowTextLengthW(hwnd)
        if ln <= 0:
            return True
        buf = ctypes.create_unicode_buffer(ln + 1)
        user32.GetWindowTextW(hwnd, buf, ln + 1)
        t = buf.value
        # 类名要是浏览器窗口（Chrome_WidgetWin_1），排除控制台等
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w >= min_w and h >= min_h and "Chrome_WidgetWin" in cls.value:
            result.append((hwnd, t, w, h, cls.value))
        return True

    user32.EnumWindows(cb, 0)
    # 优先标题含关键词的
    hit = [r for r in result if title_hint.lower() in r[1].lower()]
    pool = hit or result
    pool.sort(key=lambda x: x[2] * x[3], reverse=True)
    return pool[0] if pool else None


def capture_window(hwnd, out_path):
    """用 PrintWindow 抓窗口（含标题栏/地址栏）。"""
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return False, "窗口尺寸非法 %dx%d" % (w, h)

    hdc = user32.GetWindowDC(hwnd)
    if not hdc:
        return False, "GetWindowDC 失败"
    mdc = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, hbmp)

    ok = user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # 负数 = 自上而下
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0

    buf_size = w * h * 4
    buf = ctypes.create_string_buffer(buf_size)
    got = gdi32.GetDIBits(mdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)

    if got == 0:
        return False, "GetDIBits 失败"

    # 用 PIL 存 PNG（BGRA → RGB）
    from PIL import Image
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    img.convert("RGB").save(out_path, "PNG")
    return True, "PrintWindow ok(%d) %dx%d" % (ok, w, h)


def main():
    log("截图 2 开始：%s" % SITE)
    prof = os.path.join(HERE, "_s2_%d" % int(time.time() * 1000))
    env = dict(os.environ)
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        env.pop(k, None)

    proc = subprocess.Popen(
        [EDGE, "--new-window", "--user-data-dir=" + prof, "--no-first-run",
         "--no-default-browser-check", "--remote-debugging-port=%d" % PORT,
         "--remote-allow-origins=*", "--window-position=0,0",
         # ★ 关键：关掉 GPU 加速，让页面内容走软件渲染。
         #   否则 PrintWindow 抓到的是「有地址栏但内容空白」——GPU 合成层不在 GDI 表面上。
         "--disable-gpu", "--disable-gpu-compositing", "--disable-software-rasterizer",
         "--in-process-gpu",
         SITE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    log("Edge pid=%s" % proc.pid)

    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ws_url = None
    for i in range(50):
        time.sleep(1)
        try:
            ts = json.loads(op.open("http://127.0.0.1:%d/json" % PORT, timeout=4).read().decode())
        except Exception:
            continue
        for t in ts:
            if t.get("type") == "page" and "touhou-mock" in t.get("url", ""):
                ws_url = t["webSocketDebuggerUrl"]
                break
        if ws_url:
            log("  第 %d 秒拿到公网页" % (i + 1))
            break

    if ws_url:
        ws = websocket.create_connection(ws_url, timeout=30, http_proxy_host=None)
        mid = [0]

        def send(m, p=None):
            mid[0] += 1
            ws.send(json.dumps({"id": mid[0], "method": m, "params": p or {}}))
            dl = time.time() + 30
            while time.time() < dl:
                try:
                    ws.settimeout(1.5)
                    msg = json.loads(ws.recv())
                except Exception:
                    continue
                if msg.get("id") == mid[0]:
                    return msg
            return None

        def ev(js):
            r = send("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
            return r["result"].get("result", {}).get("value") if r and "result" in r else None

        send("Runtime.enable")
        send("Page.enable")
        time.sleep(8)  # 等真库数据

        info = ev("""
        (function(){
          return {url: location.href, title: document.title,
                  modules: document.querySelectorAll('.module-card').length,
                  navItems: document.querySelectorAll('header nav .nav-item').length,
                  h1: (document.querySelector('header h1')||{}).textContent||''};
        })()
        """)
        log("  页面信息：%s" % json.dumps(info, ensure_ascii=False))

        # ---- 窗口截图（含地址栏）----
        win = find_browser_window("touhou")
        if not win:
            log("!! 没找到窗口")
        else:
            hwnd, title, w, h = win[0], win[1], win[2], win[3]
            log("  窗口：%r  %dx%d" % (title[:50], w, h))
            # 置顶并等一会
            user32.SetForegroundWindow(hwnd)
            time.sleep(2)
            ok, msg = capture_window(hwnd, OUT)
            log("  截图结果：%s / %s" % (ok, msg))
            if ok:
                log("  已写出 %s（%d 字节）" % (os.path.basename(OUT), os.path.getsize(OUT)))

        # ---- 再拍一张板块页（证明完整作品）----
        if ws_url:
            ev("location.hash='#/music'")
            time.sleep(4)
            info2 = ev("({hash:location.hash, items:document.querySelectorAll('.work-item').length})")
            log("  板块页：%s" % json.dumps(info2, ensure_ascii=False))
            win2 = find_browser_window("touhou")
            if win2:
                user32.SetForegroundWindow(win2[0])
                time.sleep(2)
                ok2, msg2 = capture_window(win2[0], OUT_SOFT)
                log("  截图2b：%s / %s" % (ok2, msg2))
                if ok2:
                    log("  已写出 %s（%d 字节）" % (os.path.basename(OUT_SOFT), os.path.getsize(OUT_SOFT)))
        ws.close()

    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("截图 2 结束")


if __name__ == "__main__":
    try:
        with open(os.path.join(HERE, "_s2_log.txt"), "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass
    try:
        main()
    except Exception:
        import traceback
        log("EXC: %s" % traceback.format_exc())
    log("=== 脚本退出 ===")
