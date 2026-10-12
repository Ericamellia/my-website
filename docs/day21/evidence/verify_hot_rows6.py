# -*- coding: utf-8 -*-
"""验证热搜详细页「6 行 + 每次展开更多追加 6 行」：
   ① 详细页首屏默认显示 6 行（= 列数 × 6）
   ② 「展开更多」按钮存在，且文案带剩余数量
   ③ 每次点击后新增一批（列数 × 6），且**点完立刻还有 6 行新内容**
   ④ 一直点到全部加载完，按钮自动消失
   ⑤ 回归：同人视频/音乐页仍是 3 行（没被影响）
"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9341
BASE = os.environ.get('BASE', 'http://127.0.0.1:3001')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-rows-')
proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1500,1300', 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
OK = []
try:
    for _ in range(40):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
                tg = json.load(r)
            pg = [t for t in tg if t.get('type') == 'page']
            if pg:
                ws = pg[0]['webSocketDebuggerUrl']; break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        print('无法连接 CDP'); sys.exit(1)

    from websocket import create_connection
    w = create_connection(ws, timeout=40)
    mid = [0]

    def cdp(m, p=None):
        mid[0] += 1
        w.send(json.dumps({'id': mid[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(w.recv())
            if r.get('id') == mid[0]:
                return r

    def ev(expr):
        r = cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        rr = r.get('result', {})
        if rr.get('exceptionDetails'):
            return None
        return rr.get('result', {}).get('value')

    def shot(name, clip=None):
        p = {'format': 'png'}
        if clip:
            p['clip'] = clip
        r = cdp('Page.captureScreenshot', p)
        d = r.get('result', {}).get('data')
        if not d:
            return None
        fp = os.path.join(OUTDIR, 'rows-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    def mouse(x, y, kind='move'):
        if kind == 'move':
            cdp('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})
        else:
            cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
            cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})

    # 统计已显示（非 lm-hidden）卡片数
    SHOWN = 'document.querySelectorAll("#hotDetailGrid .video-card:not(.lm-hidden)").length'
    TOTAL = 'document.querySelectorAll("#hotDetailGrid .video-card").length'
    COLS = ('(function(){var cs=Array.from(document.querySelectorAll("#hotDetailGrid .video-card:not(.lm-hidden)"));'
            'if(!cs.length)return 0;var t=cs[0].offsetTop;return cs.filter(function(c){return c.offsetTop===t}).length})()')
    BTN = 'document.querySelector(".load-more-btn")'

    def click_more():
        """把按钮滚到视口中央再点（否则点不到）"""
        b = ev('(function(){var b=document.querySelector(".load-more-btn");if(!b)return null;'
               'b.scrollIntoView({block:"center"});var r=b.getBoundingClientRect();'
               'return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
        if not b:
            return False
        mouse(b['x'], b['y'], 'click')
        time.sleep(0.7)
        return True

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # ================= 热搜详细页：6 行起步 =================
    cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(4)
    ev('location.hash = "#/hot/fresh"'); time.sleep(3)
    for _ in range(20):
        n = ev(TOTAL)
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    print('=' * 78)
    print('【热搜详细页 · 首屏 6 行】')
    total = ev(TOTAL)
    shown = ev(SHOWN)
    cols = ev(COLS)
    rows = round(shown / cols) if (shown and cols) else 0
    print('  总条数 =', total, '| 列数 =', cols, '| 首屏显示 =', shown, '→', rows, '行')
    OK.append(('详细页', '数据已扩充（>24 条）', isinstance(total, int) and total > 24, total))
    OK.append(('详细页', '首屏显示 6 行', rows == 6, '%s 条 / %s 列 = %s 行' % (shown, cols, rows)))
    batch = (cols or 0) * 6
    OK.append(('详细页', '一批 = 列数×6', batch == shown, 'batch=%s shown=%s' % (batch, shown)))
    print('  截图 →', shot('首屏6行', {'x': 0, 'y': 0, 'width': 1500, 'height': 1300, 'scale': 1}))

    # 按钮文案
    btxt = ev('(function(){var b=document.querySelector(".load-more-btn");return b?b.textContent.trim():null})()')
    print('  展开更多按钮 =', btxt)
    OK.append(('详细页', '存在展开更多按钮', bool(btxt), btxt))
    OK.append(('详细页', '按钮文案含剩余数', btxt is not None and '还有' in btxt, btxt))

    # ================= 连续点击：每次 +6 行 =================
    print('-' * 78)
    print('【连续点「展开更多」：每次追加 6 行】')
    step = 0
    prev_shown = shown
    while step < 10:
        has = ev('!!document.querySelector(".load-more-btn")')
        if not has:
            break
        step += 1
        if not click_more():
            break
        cur = ev(SHOWN)
        now_total = ev(TOTAL)
        print('  第 %d 次点击后：显示 %s / %s' % (step, cur, now_total))
        gained = (cur or 0) - (prev_shown or 0)
        expect = batch
        # 每次都该新增「一批」；最后一批可能不足（剩余不够），所以用 min 判断
        remain_before = (now_total or 0) - (prev_shown or 0)
        want = min(expect, remain_before)
        OK.append(('展开%d' % step, '新增 %d 条（一批）' % want, gained == want,
                   '新增 %s，期望 %s' % (gained, want)))
        prev_shown = cur
        if cur == now_total:
            break
    print('  共点击 %d 次，最终显示 = %s / %s' % (step, ev(SHOWN), ev(TOTAL)))
    OK.append(('详细页', '点到底后按钮消失', ev('!document.querySelector(".load-more-btn")'), ev('!!document.querySelector(".load-more-btn")')))
    OK.append(('详细页', '最终全部展示', ev(SHOWN) == ev(TOTAL), '%s/%s' % (ev(SHOWN), ev(TOTAL))))
    print('  截图 →', shot('全部展开', {'x': 0, 'y': 0, 'width': 1500, 'height': 1300, 'scale': 1}))

    # ================= 历史热门榜同样 6 行 =================
    print('-' * 78)
    print('【历史热门榜 · 同样 6 行】')
    ev('location.hash = "#/hot/hot"'); time.sleep(3)
    for _ in range(20):
        n = ev(TOTAL)
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    t2, s2, c2 = ev(TOTAL), ev(SHOWN), ev(COLS)
    r2 = round(s2 / c2) if (s2 and c2) else 0
    print('  总条数 =', t2, '| 列数 =', c2, '| 首屏 =', s2, '→', r2, '行')
    OK.append(('热门榜', '首屏 6 行', r2 == 6, '%s/%s=%s' % (s2, c2, r2)))

    # ================= 回归：其他页仍 3 行 =================
    print('-' * 78)
    print('【回归：同人视频/音乐仍是 3 行】')
    ev('location.hash = "#/video"'); time.sleep(3)
    for _ in range(20):
        n = ev('document.querySelectorAll(".video-grid .video-card").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    vs = ev('document.querySelectorAll(".video-grid .video-card:not(.lm-hidden)").length')
    vt = ev('document.querySelectorAll(".video-grid .video-card").length')
    vc = ev('(function(){var cs=Array.from(document.querySelectorAll(".video-grid .video-card:not(.lm-hidden)"));if(!cs.length)return 0;var t=cs[0].offsetTop;return cs.filter(function(c){return c.offsetTop===t}).length})()')
    vr = round(vs / vc) if (vs and vc) else 0
    print('  同人视频：总 %s | 列 %s | 显示 %s → %s 行' % (vt, vc, vs, vr))
    # 数据不足 3 行时本来就该全显示；够 3 行才要求显示 3 行
    vexpect = min(3, -(-vt // vc)) if (vt and vc) else 0
    OK.append(('回归', '同人视频行数=min(3, 总行数)', vr == vexpect, '实际 %s 行，期望 %s 行（总%s/列%s）' % (vr, vexpect, vt, vc)))

    ev('location.hash = "#/music"'); time.sleep(3)
    for _ in range(20):
        n = ev('document.querySelectorAll(".work-item").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    ms = ev('document.querySelectorAll(".work-item:not(.lm-hidden)").length')
    mt = ev('document.querySelectorAll(".work-item").length')
    mc = ev('(function(){var cs=Array.from(document.querySelectorAll(".work-item:not(.lm-hidden)"));if(!cs.length)return 0;var t=cs[0].offsetTop;return cs.filter(function(c){return c.offsetTop===t}).length})()')
    mr = round(ms / mc) if (ms and mc) else 0
    print('  同人音乐：总 %s | 列 %s | 显示 %s → %s 行' % (mt, mc, ms, mr))
    mexpect = min(3, -(-mt // mc)) if (mt and mc) else 0
    OK.append(('回归', '同人音乐行数=min(3, 总行数)', mr == mexpect, '实际 %s 行，期望 %s 行（总%s/列%s）' % (mr, mexpect, mt, mc)))

finally:
    print()
    print('=' * 78)
    bad = [x for x in OK if not x[2]]
    print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(OK), len(OK) - len(bad), len(bad)))
    for n_, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n_, l, v))
    try:
        proc.kill()
    except Exception:
        pass
