# -*- coding: utf-8 -*-
"""验证热搜详细页底部「更多请前往 bilibili 查看」：
   ① 该链接存在于详细页，文案正确
   ② 位置在列表最底部（在 .load-more-btn 之后、页面内容末尾）
   ③ href 指向 bilibili，target=_blank
   ④ 点击 → 走外链拦截（进「少女祈祷中」中转页），不原地跳走
   ⑤ 点「展开更多」后该链接仍在最底部（位置不被挤乱）
   ⑥ 回归：首页/其他页不出现该链接
"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9347
BASE = os.environ.get('BASE', 'http://127.0.0.1:3001')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-more-')
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
        fp = os.path.join(OUTDIR, 'more-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # 跑两个榜单都验一遍
    for board, label in (('fresh', '今日B站热搜'), ('hot', '历史B站热门')):
        print('=' * 78)
        print('【详细页 %s（#/hot/%s）底部外链】' % (label, board))
        cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(4)
        ev('location.hash = "#/hot"'); time.sleep(2)
        ev('location.hash = "#/hot/%s"' % board); time.sleep(3)
        for _ in range(20):
            n = ev('document.querySelectorAll("#hotDetailGrid .video-card").length')
            if isinstance(n, int) and n > 0:
                break
            time.sleep(0.5)

        info = ev("""(function(){
          var a = document.querySelector('#app .hot-more-link a');
          if (!a) return {exists:false};
          var r = a.getBoundingClientRect();
          return {exists:true, text:a.textContent.trim(), href:a.getAttribute('href'),
                  target:a.getAttribute('target'), rel:a.getAttribute('rel'),
                  vis:r.width>0&&r.height>0, x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)};
        })()""")
        print('  链接 =', info)
        OK.append(('详细页', '链接存在且可见', bool(info) and info.get('exists') and info.get('vis'), info))
        OK.append(('详细页', '文案含「更多请前往 bilibili 查看」',
                   info.get('exists') and '更多请前往' in info.get('text', '') and 'bilibili' in info.get('text', ''),
                   info.get('text')))
        OK.append(('详细页', 'href 指向 bilibili', 'bilibili.com' in str(info.get('href')), info.get('href')))
        OK.append(('详细页', 'target=_blank', info.get('target') == '_blank', info.get('target')))

        # 位置：必须在 .load-more-btn 之后（DOM 顺序），且在 #app 内容里靠后
        order = ev("""(function(){
          var app = document.getElementById('app');
          var kids = Array.from(app.children);
          var link = app.querySelector('.hot-more-link');
          var btn  = app.querySelector('.load-more-btn');
          return {linkIdx: kids.indexOf(link), btnIdx: btn ? kids.indexOf(btn) : -1,
                  appChildren: kids.map(function(e){return e.className || e.tagName})};
        })()""")
        print('  DOM 顺序 =', order)
        li, bi = order.get('linkIdx'), order.get('btnIdx')
        OK.append(('详细页', '位置在展开按钮之后', bi >= 0 and li > bi, 'link=%s btn=%s' % (li, bi)))
        # 底部最后一块内容（footer 之前）
        last = ev("""(function(){
          var app = document.getElementById('app');
          var kids = Array.from(app.children).filter(function(e){return e.offsetHeight>0});
          var lastEl = kids[kids.length-1];
          return lastEl ? lastEl.className : null;
        })()""")
        print('  页面最后一个可见块 class =', last)
        OK.append(('详细页', '是页面最后一个块', last == 'hot-more-link', last))
        print('  截图 →', shot('底部外链-%s' % board, {'x': 0, 'y': 0, 'width': 1500, 'height': 1200, 'scale': 1}))

        if board == 'fresh':
            # 点「展开更多」后，链接仍应在最底部
            print('  —— 点一次「展开更多」后复查位置 ——')
            b = ev('(function(){var b=document.querySelector(".load-more-btn");if(!b)return null;b.scrollIntoView({block:"center"});var r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
            if b:
                cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': b['x'], 'y': b['y'], 'button': 'left', 'clickCount': 1})
                cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': b['x'], 'y': b['y'], 'button': 'left', 'clickCount': 1})
                time.sleep(1)
            order2 = ev("""(function(){
              var app = document.getElementById('app');
              var kids = Array.from(app.children).filter(function(e){return e.offsetHeight>0});
              var lastEl = kids[kids.length-1];
              return lastEl ? lastEl.className : null;
            })()""")
            shown = ev('document.querySelectorAll("#hotDetailGrid .video-card:not(.lm-hidden)").length')
            print('  展开后显示 = %s 条 | 最后一块 = %s' % (shown, order2))
            OK.append(('详细页', '展开后链接仍在最底部', order2 == 'hot-more-link', order2))

            # 点击 → 外链拦截：goExternal 会 window.open 新标签写祈祷页，并在这之前预开 about:blank
            # 用 hook window.open 记录调用（不真正打开窗口，避免弹窗），再点
            print('  —— 点击该链接（hook window.open 观察）——')
            ev("""window.__opened = [];
                 if(!window.__openHooked){window.__openHooked=1;
                   var orig = window.open;
                   window.open = function(u,n){ window.__opened.push(String(u)); return null; };
                 }
                 'ok';""")
            lk = ev('(function(){var a=document.querySelector("#app .hot-more-link a");a.scrollIntoView({block:"center"});var r=a.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
            cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': lk['x'], 'y': lk['y'], 'button': 'left', 'clickCount': 1})
            cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': lk['x'], 'y': lk['y'], 'button': 'left', 'clickCount': 1})
            time.sleep(1.5)
            opened = ev('JSON.stringify(window.__opened)')
            still = ev('document.querySelectorAll("#app .hot-more-link").length')
            print('  window.open 调用 =', opened)
            print('  当前页仍在原位（链接还在）=', still)
            OK.append(('详细页', '点击触发外链跳转（window.open 被调用）',
                       opened not in (None, '[]'), opened))
            OK.append(('详细页', '当前页未原地跳走', still == 1, still))
            print('  截图 →', shot('点击后', {'x': 0, 'y': 0, 'width': 1500, 'height': 900, 'scale': 1}))
            break

    # ============ 回归：其他页不出现该链接 ============
    print('-' * 78)
    print('【回归：非详细页不出现该链接】')
    for h, name in (('#/', '首页'), ('#/hot', '热搜主界面'), ('#/video', '同人视频'), ('#/music', '同人音乐')):
        cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(2.5)
        ev('location.hash = "%s"' % h); time.sleep(2.5)
        cnt = ev('document.querySelectorAll("#app .hot-more-link").length')
        print('  %s → .hot-more-link 数量 = %s' % (name, cnt))
        OK.append(('回归', '%s 无该链接' % name, cnt == 0, cnt))

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
