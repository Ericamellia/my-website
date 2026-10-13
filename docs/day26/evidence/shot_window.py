# Day 26 截图辅助：打开真实浏览器窗口（含地址栏），抓该窗口截图
#
# 为什么不用无头截图：无头模式没有地址栏、没有浏览器外壳。
# Day 26 的截图要求「图里要有地址栏和页面」，所以必须是真窗口。
#
# 做法：
#   1. 用 Edge 打开目标 URL（普通窗口，不是 --app，这样有地址栏）
#   2. 轮询等待窗口出现并置前
#   3. 用 ctypes + Win32 GDI 抓「该窗口」的位图（只抓窗口，不抓整屏）
#   4. 保存 PNG
#
# 用法：python shot_window.py <url> <输出png> [等待秒数]
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("找不到 msedge.exe")


def enum_windows_pids():
    """返回 {hwnd: pid}，只取可见的顶层窗口。"""
    result = {}
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            result[hwnd] = pid.value
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return result


def window_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def grab_window(hwnd, out_png):
    """用 PrintWindow 抓窗口位图。

    不依赖 PIL：把 32 位 BGRA 像素直接写成一个标准 BMP 文件，
    再由调用方（或后续步骤）转成 PNG。这样 base 解释器也能跑。
    """
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError("窗口尺寸非法: %dx%d" % (w, h))

    hwnd_dc = user32.GetWindowDC(hwnd)
    if not hwnd_dc:
        raise RuntimeError("GetWindowDC 失败（窗口可能最小化）")

    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bmp)

    # PW_RENDERFULLCONTENT = 2：能抓到 GPU 合成的窗口内容（浏览器必需）
    PW_RENDERFULLCONTENT = 0x00000002
    ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
    used = "PrintWindow" if ok else "BitBlt"
    if not ok:
        gdi32.BitBlt(mem_dc, 0, 0, w, h, hwnd_dc, 0, 0, SRCCOPY)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
            ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
            ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
            ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
            ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h            # 负值 = 自上而下（BMP 里会用正高 + 翻转）
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0        # BI_RGB

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
    raw = buf.raw

    # 写 BMP：文件头(14) + 信息头(40) + 像素（BGRX，自下而上）
    import struct
    row_bytes = w * 4
    pixel_data = bytearray()
    for y in range(h - 1, -1, -1):      # BMP 是自下而上
        pixel_data += raw[y * row_bytes:(y + 1) * row_bytes]
    file_size = 14 + 40 + len(pixel_data)
    header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, 14 + 40)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 32, 0, len(pixel_data),
                       2835, 2835, 0, 0)
    with open(out_png, "wb") as f:
        f.write(header + info + bytes(pixel_data))

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    return w, h, used


def main():
    # 所有关键步骤都写进这个日志文件，避免被 sandbox 吞掉输出
    def log(msg):
        print(msg, flush=True)
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "shot_debug.log"), "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    if len(sys.argv) < 3:
        raise SystemExit("用法: shot_window.py <url> <out.png> [wait_sec]")
    url = sys.argv[1]
    out = sys.argv[2]
    wait = float(sys.argv[3]) if len(sys.argv) > 3 else 9.0
    log("=== 启动 url=%s out=%s wait=%s" % (url, out, wait))

    edge = find_edge()
    log("edge = " + edge)

    before = set(enum_windows_pids().keys())
    log("已有窗口数 = %d" % len(before))

    # 每次用唯一 profile 目录，强制开全新 Edge 实例，避免复用旧进程
    # （复用时会「新窗口挂在旧进程下」，枚举不到新 hwnd，脚本会静默失败）
    profile = os.path.join(
        os.path.dirname(os.path.abspath(out)),
        "_edgeprofile_%d" % int(time.time() * 1000))
    cmd = [
        edge,
        "--new-window",
        "--no-first-run",
        "--disable-features=msImplicitSignin",
        "--window-size=1900,1250",
        "--window-position=60,40",
        "--user-data-dir=" + profile,
        url,
    ]
    subprocess.Popen(cmd)
    log("已 Popen，开始等窗口…")

    # 轮询等新窗口出现。
    # 注意：Edge 冷启动可能先弹出「还原页面」之类的小提示框，
    # 它也有标题、也会被当成新窗口。所以这里挑「面积最大」的那个，
    # 才是真正的浏览器主窗口。
    def area(h):
        r = wt.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        return max(0, r.right - r.left) * max(0, r.bottom - r.top)

    target = None
    deadline = time.time() + 45
    while time.time() < deadline:
        now = enum_windows_pids()
        cands = [h for h in now if h not in before]
        cands = [h for h in cands if window_title(h)]
        if cands:
            for h in cands:
                log("  候选 hwnd=%s area=%s title=%r" % (h, area(h), window_title(h)))
            best = max(cands, key=area)
            # 主窗口至少要够大（避免抓到恢复提示框）
            if area(best) >= 400 * 300:
                target = best
                break
        time.sleep(0.5)
    log("target = %s" % target)

    if not target:
        raise RuntimeError("未等到浏览器窗口（或窗口太小，疑似提示框）")

    # 等页面渲染
    time.sleep(wait)

    # 置前
    user32.ShowWindow(target, 9)      # SW_RESTORE
    user32.SetForegroundWindow(target)
    time.sleep(0.8)

    # 最大化：窗口客户区高度直接吃满屏幕高度，
    # 对「内容比一屏略高」的页面最有效。
    if os.environ.get("SHOT_MAX", "0") == "1":
        user32.ShowWindow(target, 3)      # SW_MAXIMIZE
        time.sleep(1.5)

    # 置前之后再强制设定窗口尺寸。
    # 顺序很关键：SW_RESTORE 会把窗口恢复成「还原前」的尺寸，
    # 所以 MoveWindow 必须放在 SW_RESTORE 之后，否则会被覆盖回去。
    if os.environ.get("SHOT_MAX", "0") != "1":
        win_w = int(os.environ.get("SHOT_W", "1800"))
        win_h = int(os.environ.get("SHOT_H", "1200"))
        user32.MoveWindow(target, 20, 10, win_w, win_h, True)
        time.sleep(1.5)

    rr = wt.RECT()
    user32.GetWindowRect(target, ctypes.byref(rr))
    log("  窗口实际尺寸 %dx%d" % (rr.right - rr.left, rr.bottom - rr.top))

    w, h, used = grab_window(target, out)
    log("SAVED %s %dx%d  via=%s  title=%r" % (out, w, h, used, window_title(target)))

    # 关掉这个窗口
    WM_CLOSE = 0x0010
    user32.PostMessageW(target, WM_CLOSE, 0, 0)
    time.sleep(1.0)

    # 清理本次用的临时 profile
    import shutil
    try:
        shutil.rmtree(profile, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    import traceback
    _logp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_debug.log")
    try:
        main()
    except BaseException as e:          # 注意：SystemExit 不继承 Exception，这里用 BaseException
        tb = traceback.format_exc()
        print("EXCEPTION:", tb, flush=True)
        try:
            with open(_logp, "a", encoding="utf-8") as f:
                f.write("EXCEPTION:\n" + tb + "\n")
        except Exception:
            pass
        raise
