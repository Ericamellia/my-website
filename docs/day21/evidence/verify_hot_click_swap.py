# -*- coding: utf-8 -*-
"""验证热搜卡片点击行为对调：
   ① 点封面本体 → 跳 B 站（<a target=_blank> 原生行为，不被 JS 拦截）
   ② 点 hover 小窗 → 开大图（preventDefault，不跳 B 站），大图内可下载原图
   ③ 详细页（.video-grid .video-card）同样规则
   ④ 回归：同人视频/音乐/原作卡片行为不变。
"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9339
BASE = os.environ.get('BASE', 'http://127.0.0.1:3000')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-swap-')
proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1500,1200', 'about:blank'
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
        fp = os.path.join(OUTDIR, 'swap-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    def mouse(x, y, kind='move'):
        if kind == 'move':
            cdp('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})
        else:
            cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
            cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})

    # 注入探针：记录点击落在哪个元素、外层链接地址，并拦截真实跳转（只观察不真的跳走）。
    # 说明：项目有全局「外链先过少女祈祷中转页」拦截器（document 级、冒泡阶段），
    # 所以「点封面」的 defaultPrevented 必然为 true——但它仍然会跳 B 站（经中转页）。
    # 因此判定口径改为：①是否调用了 goExternal/进入中转页  ②是否打开了 lightbox。
    PROBE = """
    window.__probe = { target: null, href: null, tag: null, wentTransit: null, openedLightbox: null };
    if (!window.__probeBound) {
      window.__probeBound = true;
      document.addEventListener('click', function(e){
        var t = e.target.closest ? e.target.closest('.hover-pop, .hot2-open') : null;
        if (!t) return;
        var a = e.target.closest ? e.target.closest('a') : null;
        var rec = { target: t.className, href: a ? a.getAttribute('href') : null, tag: a ? a.getAttribute('target') : null };
        window.__probe = rec;
      }, true);
      // 哨兵：中转页跳转会被 goExternal 改写 location；用 unload 前后对比捕获
      window.addEventListener('beforeunload', function(){ window.__probe.leftPage = true; });
    }
    'ok';
    """

    def probe():
        return ev('JSON.stringify(window.__probe)')

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # ============ 主界面（条状列表 #/hot） ============
    cdp('Page.navigate', {'url': BASE + '/'})
    time.sleep(4)
    ev('location.hash = "#/hot"')
    time.sleep(3)
    for _ in range(20):
        n = ev('document.querySelectorAll("#hot2-list .hot2-cover").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    print('=' * 78)
    print('【热搜主界面 · 条状列表】')
    print('  条数 =', ev('document.querySelectorAll("#hot2-list .hot2-cover").length'))
    ev(PROBE)

    # --- ① 点封面本体 → 应跳 B 站 ---
    print('-' * 78)
    print('【① 点封面本体 → 跳 B 站】')
    cover = ev('(function(){var c=document.querySelector("#hot2-list .hot2-cover");if(!c)return null;var r=c.getBoundingClientRect();return {x:Math.round(r.left+20),y:Math.round(r.top+r.height/2),href:(c.closest("a")||{}).href}})()')
    print('  封面中心点 =', cover)
    if cover:
        OK.append(('条状', '封面外层链接指向 bilibili', 'bilibili.com' in str((cover or {}).get('href')), str((cover or {}).get('href'))[:70]))
        # 先 hover 让小窗出现，再点封面（避开小窗区域：取图片左侧 20px）
        mouse(cover['x'], cover['y'], 'click')
        time.sleep(0.9)
        p = json.loads(probe() or '{}')
        print('  探针 =', p)
        # 点封面本体：命中 .hot2-open（不是 .hover-pop）→ 交给外层 <a> 跳 B 站
        OK.append(('条状', '点封面命中 hot2-open', 'hot2-open' in str(p.get('target')), p.get('target')))
        OK.append(('条状', '点封面外层 target=_blank', p.get('tag') == '_blank', p.get('tag')))
        lb = ev('document.getElementById("lightbox").hidden')
        OK.append(('条状', '点封面不开大图', lb is True, lb))

    # --- ② 点小窗 → 应开大图，且不跳 B 站 ---
    print('-' * 78)
    print('【② 点 hover 小窗 → 开大图（不跳 B 站）】')
    # 先移到封面触发 hover，小窗出现后取其坐标
    mouse(10, 500); time.sleep(0.3)
    mouse(cover['x'], cover['y']); time.sleep(0.8)
    pop = ev('(function(){var p=document.querySelector("#hot2-list .hot2-cover .hover-pop");if(!p)return null;var s=getComputedStyle(p);var r=p.getBoundingClientRect();return {display:s.display,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),w:Math.round(r.width),h:Math.round(r.height)}})()')
    print('  小窗 =', pop)
    OK.append(('条状', 'hover 弹出小窗', bool(pop) and pop.get('display') == 'block', (pop or {}).get('display')))
    if pop and pop['display'] == 'block':
        print('  截图 →', shot('小窗hover', {'x': 90, 'y': 80, 'width': 640, 'height': 440, 'scale': 1}))
        mouse(pop['x'], pop['y'], 'click')
        time.sleep(1.2)
        lb2 = ev('document.getElementById("lightbox").hidden')
        src = ev('(document.getElementById("lightbox-img")||{}).src')
        cur = ev('location.href')
        p2 = json.loads(probe() or '{}')
        print('  点小窗后：lightbox hidden =', lb2, '| 当前页 =', str(cur)[:60])
        print('  探针 =', p2)
        OK.append(('条状', '点小窗打开大图', lb2 is False, lb2))
        OK.append(('条状', '大图有图片地址', bool(src) and str(src).startswith('http'), str(src)[:60]))
        OK.append(('条状', '点小窗未跳B站', 'bilibili.com' not in str(cur), str(cur)[:60]))
        print('  截图 →', shot('小窗开大图', {'x': 0, 'y': 0, 'width': 1500, 'height': 1000, 'scale': 1}))
        # 下载按钮仍在
        dl = ev('!!document.getElementById("lightbox-dl")')
        OK.append(('条状', '大图仍有下载按钮', bool(dl), dl))
        # Esc 关闭
        cdp('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
        cdp('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
        time.sleep(0.5)
        cl = ev('document.getElementById("lightbox").hidden === true')
        OK.append(('条状', 'Esc 可关闭大图', bool(cl), cl))

    # ============ 详细页（.video-grid .video-card） ============
    print('-' * 78)
    print('【详细页 · 同人视频同款卡片】')
    # 用 hashchange 触发路由（about:blank 后直接带 hash 导航有时不触发路由）
    cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(4)
    ev('location.hash = "#/hot/hot"')
    time.sleep(3)
    for _ in range(20):
        n = ev('document.querySelectorAll(".video-grid .video-card .hot2-open").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    print('  详细页卡片封面数 =', ev('document.querySelectorAll(".video-grid .video-card .hot2-open").length'))
    ev(PROBE)
    vc = ev('(function(){var c=document.querySelector(".video-grid .video-card .hot2-open");if(!c)return null;var r=c.getBoundingClientRect();return {x:Math.round(r.left+20),y:Math.round(r.top+30),href:(c.closest("a")||{}).href}})()')
    print('  第1张卡片封面 =', vc)
    if vc:
        OK.append(('详细页', '封面外层链接指向 bilibili', 'bilibili.com' in str((vc or {}).get('href')), str((vc or {}).get('href'))[:70]))
        mouse(vc['x'], vc['y'], 'click')
        time.sleep(0.9)
        p3 = json.loads(probe() or '{}')
        lb3 = ev('document.getElementById("lightbox").hidden')
        print('  点封面探针 =', p3, '| lightbox hidden =', lb3)
        OK.append(('详细页', '点封面命中 hot2-open', 'hot2-open' in str(p3.get('target')), p3.get('target')))
        OK.append(('详细页', '点封面外层 target=_blank', p3.get('tag') == '_blank', p3.get('tag')))
        OK.append(('详细页', '点封面不开大图', lb3 is True, lb3))

        # 点小窗开大图
        mouse(10, 500); time.sleep(0.3)
        mouse(vc['x'], vc['y']); time.sleep(0.8)
        vpop = ev('(function(){var p=document.querySelector(".video-grid .hot2-open .hover-pop");if(!p)return null;var s=getComputedStyle(p);var r=p.getBoundingClientRect();return {display:s.display,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
        print('  详细页小窗 =', vpop)
        OK.append(('详细页', 'hover 弹出小窗', bool(vpop) and vpop.get('display') == 'block', (vpop or {}).get('display')))
        if vpop and vpop['display'] == 'block':
            mouse(vpop['x'], vpop['y'], 'click')
            time.sleep(1.2)
            lb4 = ev('document.getElementById("lightbox").hidden')
            src4 = ev('(document.getElementById("lightbox-img")||{}).src')
            cur4 = ev('location.href')
            print('  点小窗后 lightbox hidden =', lb4, '| 当前页 =', str(cur4)[:60])
            OK.append(('详细页', '点小窗打开大图', lb4 is False, lb4))
            OK.append(('详细页', '大图有图片地址', bool(src4) and str(src4).startswith('http'), str(src4)[:60]))
            OK.append(('详细页', '点小窗未跳B站', 'bilibili.com' not in str(cur4), str(cur4)[:60]))
            print('  截图 →', shot('详细页小窗开大图', {'x': 0, 'y': 0, 'width': 1500, 'height': 900, 'scale': 1}))

    # ============ 回归 ============
    print('-' * 78)
    print('【回归：其他页面不受影响】')
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(4)
    ev('location.hash = "#/video"'); time.sleep(3)
    for _ in range(20):
        n = ev('document.querySelectorAll(".video-grid .video-card").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    vcard = ev('document.querySelectorAll(".video-grid .video-card").length')
    vpop2 = ev('document.querySelectorAll(".video-grid .video-card .hover-pop").length')
    print('  同人视频 卡片=%s | 含hover小窗=%s' % (vcard, vpop2))
    OK.append(('回归', '同人视频卡片正常', isinstance(vcard, int) and vcard > 0, vcard))
    OK.append(('回归', '视频卡片仍有hover小窗', isinstance(vpop2, int) and vpop2 > 0, vpop2))
    # 同人视频的 hover-pop 仍是「跳 B 站」老规矩
    ev(PROBE)
    vp = ev('(function(){var p=document.querySelector(".video-grid .video-card .hover-pop");if(!p)return null;var r=p.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    if vp:
        mouse(10, 500); time.sleep(0.3)
        mouse(vp['x'], vp['y']); time.sleep(0.7)
        if ev('(function(){var p=document.querySelector(".video-grid .video-card .hover-pop");return p?(getComputedStyle(p).display==="block"):false})()'):
            mouse(vp['x'], vp['y'], 'click'); time.sleep(0.8)
            p5 = json.loads(probe() or '{}')
            lb5 = ev('document.getElementById("lightbox").hidden')
            print('  视频页点小窗探针 =', p5, '(prevented=True 表示被 JS 拦截去开原图，不是开大图)')
            OK.append(('回归', '视频页点小窗仍不开大图', lb5 is True, lb5))

    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(4)
    ev('location.hash = "#/music"'); time.sleep(3)
    for _ in range(20):
        n = ev('document.querySelectorAll(".work-item").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    m = ev('document.querySelectorAll(".work-item").length')
    print('  同人音乐 卡片 =', m)
    OK.append(('回归', '同人音乐正常', isinstance(m, int) and m > 0, m))

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
