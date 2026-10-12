# -*- coding: utf-8 -*-
"""验证：顶栏火焰按钮 + 全部入口同一行 + #/hot 热搜页（本地 3000）。"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9333
BASE = os.environ.get('BASE', 'http://127.0.0.1:3000')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-hot-')
proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
    '--remote-debugging-port=%d' % CDP_PORT,
    '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1400,1000', 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
OK = []
try:
    for _ in range(40):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
                targets = json.load(r)
            page = [t for t in targets if t.get('type') == 'page']
            if page:
                ws = page[0]['webSocketDebuggerUrl']
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        print('无法连接 CDP'); sys.exit(1)

    from websocket import create_connection
    w = create_connection(ws, timeout=30)
    mid = [0]

    def cdp(method, params=None):
        mid[0] += 1
        w.send(json.dumps({'id': mid[0], 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(w.recv())
            if m.get('id') == mid[0]:
                return m

    def ev(expr):
        r = cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        rr = r.get('result', {}).get('result', {})
        return rr.get('value')

    def shot(name):
        r = cdp('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
        d = r.get('result', {}).get('data')
        if not d:
            return None
        p = os.path.join(OUTDIR, 'hot-' + name + '.png')
        open(p, 'wb').write(base64.b64decode(d))
        return os.path.basename(p)

    OK = []
    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # ---------- 首页：顶栏一行 + 火焰按钮 ----------
    cdp('Page.navigate', {'url': BASE + '/'})
    time.sleep(4)
    print('=' * 74)
    print('【作品站首页顶栏】')
    nav_n = ev('document.querySelectorAll("header nav .nav-item").length')
    print('  导航入口数 =', nav_n)
    OK.append(('顶栏', '导航入口数（应为8）', nav_n == 8, nav_n))

    has_hot = ev('!!document.querySelector("header nav .nav-item.nav-hot")')
    hot_href = ev('(document.querySelector("header nav .nav-item.nav-hot")||{}).getAttribute ? document.querySelector("header nav .nav-item.nav-hot").getAttribute("href") : null')
    hot_label = ev('(function(){var a=document.querySelector("header nav .nav-item.nav-hot");return a?a.querySelector(".nav-label").textContent:null})()')
    hot_aria = ev('(function(){var a=document.querySelector("header nav .nav-item.nav-hot");return a?a.getAttribute("aria-label"):null})()')
    hot_svg = ev('(function(){var a=document.querySelector("header nav .nav-item.nav-hot svg");return a?a.querySelectorAll("path").length:0})()')
    print('  火焰按钮存在 =', has_hot, '| href =', hot_href, '| hover 文字 =', hot_label, '| aria =', hot_aria)
    OK.append(('顶栏', '火焰按钮存在', bool(has_hot), has_hot))
    OK.append(('顶栏', 'href=#/hot', hot_href == '#/hot', hot_href))
    OK.append(('顶栏', 'hover 显示 B站必看', hot_label == 'B站必看', hot_label))
    OK.append(('顶栏', '火焰 SVG 路径', hot_svg == 1, hot_svg))

    # 同一行判定：所有 nav-item 的 top 值是否一致
    tops = ev('Array.from(document.querySelectorAll("header nav .nav-item")).map(function(a){return Math.round(a.getBoundingClientRect().top)})')
    hs = ev('Array.from(document.querySelectorAll("header nav .nav-item")).map(function(a){return Math.round(a.getBoundingClientRect().height)})')
    uniq = sorted(set(tops or []))
    print('  各入口 top 值 =', tops)
    print('  各入口 高度  =', hs)
    OK.append(('顶栏', '全部入口同一行（top 唯一）', len(uniq) == 1, tops))

    # 顶栏是否真的只有一行：8 个入口的 top 值必须完全一致（同行判定）
    ch = ev('Math.round(document.querySelector("header .container").getBoundingClientRect().height)')
    print('  header .container 高 =', ch, 'px（含上下 padding，仅作参考）')
    OK.append(('顶栏', '只有一行（nav 内 top 唯一）', len(uniq) == 1, tops))

    # 缩小后：确认没有溢出视口
    ovf = ev('document.documentElement.scrollWidth <= window.innerWidth + 1')
    print('  横向无溢出 =', ovf)
    OK.append(('顶栏', '横向无溢出', bool(ovf), ovf))

    print('  截图 →', shot('首页顶栏'))

    # ---------- hover 显示 tooltip（模拟鼠标移到火焰按钮） ----------
    box = ev('(function(){var a=document.querySelector("header nav .nav-item.nav-hot");var r=a.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    if box:
        cdp('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': box['x'], 'y': box['y']})
        time.sleep(0.6)
        op = ev('(function(){var l=document.querySelector("header nav .nav-item.nav-hot .nav-label");return getComputedStyle(l).opacity})()')
        txt = ev('document.querySelector("header nav .nav-item.nav-hot .nav-label").textContent')
        print('  hover 到底部提示 opacity =', op, '| 文字 =', txt)
        OK.append(('顶栏', 'hover 提示可见', float(op or 0) > 0.9, op))
        print('  截图 →', shot('火焰hover'))

    # ---------- 点进热搜页 ----------
    cdp('Page.navigate', {'url': BASE + '/#/hot'})
    time.sleep(4.5)
    print('-' * 74)
    print('【B站必看（热搜）页】', BASE + '/#/hot')
    src = ev('window.__dataSource')
    h2 = ev('(document.querySelector("#app h2")||{}).textContent')
    tabs = ev('Array.from(document.querySelectorAll(".hot-tab")).map(function(b){return b.textContent})')
    cards = ev('document.querySelectorAll(".hot-card").length')
    first_title = ev('(document.querySelector(".hot-card .hot-title")||{}).textContent')
    first_href = ev('(document.querySelector(".hot-card")||{}).href')
    first_rank = ev('(document.querySelector(".hot-card .hot-rank")||{}).textContent')
    # 封面加载情况
    cover_ok = ev('Array.from(document.querySelectorAll(".hot-cover img")).filter(function(i){return i.naturalWidth>0}).length')
    print('  数据源 =', src, '| 标题 =', h2)
    print('  tab =', tabs)
    print('  卡片数 =', cards, '| 封面已加载 =', cover_ok, '/', cards)
    print('  第1条 = #', first_rank, first_title)
    print('  第1条链接 =', first_href)
    OK.append(('热搜页', '标题 B站必看', h2 == 'B站必看', h2))
    OK.append(('热搜页', '两个 tab', tabs == ['最新投稿', '历史热门'], tabs))
    OK.append(('热搜页', '卡片有数据', isinstance(cards, int) and cards > 0, cards))
    OK.append(('热搜页', '封面已加载', cover_ok and cover_ok > 0, cover_ok))
    OK.append(('热搜页', '第1条跳B站', bool(first_href) and 'bilibili.com/video/BV' in str(first_href), first_href))
    print('  截图 →', shot('热搜页最新'))

    # 切到历史热门
    tb = ev('(function(){var b=document.querySelector(\'.hot-tab[data-hboard="hot"]\');var r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    if tb:
        cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': tb['x'], 'y': tb['y'], 'button': 'left', 'clickCount': 1})
        cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': tb['x'], 'y': tb['y'], 'button': 'left', 'clickCount': 1})
        time.sleep(2.5)
        cards2 = ev('document.querySelectorAll(".hot-card").length')
        act = ev('(document.querySelector(".hot-tab.active")||{}).textContent')
        print('  切到「历史热门」→ 激活 =', act, '| 卡片数 =', cards2)
        OK.append(('热搜页', 'tab 切换生效', act == '历史热门', act))
        print('  截图 →', shot('热搜页历史热门'))

    # ---------- 回归：其他页面是否正常 ----------
    print('-' * 74)
    print('【回归检查：现有页面未被破坏】')
    pages = [
        ('#/music', '同人音乐', '.work-item,.video-card'),
        ('#/doujin', '同人漫画', '.work-item,.video-card'),
        ('#/game', '同人游戏', '.work-item,.video-card'),
        ('#/video', '同人视频', '.work-item,.video-card'),
        ('#/art', '同人图', '.work-item,.video-card'),
        ('#/original', '原作页', '.og-card'),
        ('#/fav', '我的收藏', '#app h2'),
        ('#/search/灵梦', '搜索页', '.work-item,.video-card'),
    ]
    for route, name, sel in pages:
        cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
        cdp('Page.navigate', {'url': BASE + '/' + route}); time.sleep(3)
        n = ev('document.querySelectorAll("%s").length' % sel)
        t = ev('(document.querySelector("#app h2")||{}).textContent')
        print('  %-12s 元素=%s  标题=%s' % (name, n, t))
        OK.append(('回归', name, isinstance(n, int) and n > 0, n))

    # 详情页
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/music/1'}); time.sleep(3)
    dname = ev('(document.querySelector("#app h2")||{}).textContent')
    print('  %-12s 作品名=%s' % ('音乐详情', dname))
    OK.append(('回归', '音乐详情', bool(dname), dname))

finally:
    print()
    print('=' * 74)
    bad = [x for x in OK if not x[2]]
    print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(OK), len(OK) - len(bad), len(bad)))
    for n_, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n_, l, v))
    try:
        proc.kill()
    except Exception:
        pass
