# -*- coding: utf-8 -*-
"""验证：热搜主界面 = 单个框 + 两个分类按钮（点按钮切换榜单，各 10 条）。"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9338
BASE = os.environ.get('BASE', 'http://127.0.0.1:3000')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-onebox-')
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
        fp = os.path.join(OUTDIR, 'onebox-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    def click(x, y):
        cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
        cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})
    cdp('Page.navigate', {'url': BASE + '/#/hot'})
    time.sleep(5)

    print('=' * 78)
    print('【热搜主界面：一个框 + 两个分类按钮】')
    boxes = ev('document.querySelectorAll(".hot2-box").length')
    print('  框数 =', boxes)
    OK.append(('单框', '只有 1 个框', boxes == 1, boxes))

    tabs = ev('Array.from(document.querySelectorAll(".hot2-tab")).map(function(b){return b.textContent.trim()})')
    print('  分类按钮 =', tabs)
    OK.append(('单框', '两个分类按钮', isinstance(tabs, list) and len(tabs) == 2, tabs))
    OK.append(('单框', '按钮1=今日B站热搜', bool(tabs) and tabs[0] == '今日B站热搜', tabs))
    OK.append(('单框', '按钮2=历史B站热门', bool(tabs) and len(tabs) > 1 and tabs[1] == '历史B站热门', tabs))

    # 两个按钮在同一行（同 top）
    ttops = ev('Array.from(document.querySelectorAll(".hot2-tab")).map(function(b){return Math.round(b.getBoundingClientRect().top)})')
    print('  两按钮 top =', ttops)
    OK.append(('单框', '两按钮同一行', len(set(ttops or [])) == 1, ttops))

    # 默认激活 fresh
    act = ev('(document.querySelector(".hot2-tab.active")||{}).textContent')
    rows = ev('document.querySelectorAll(".hot2-list .hot2-row").length')
    sub = ev('(document.querySelector(".hot2-sub")||{}).textContent')
    first = ev('(document.querySelector(".hot2-list .hot2-title")||{}).textContent')
    print('  默认激活 =', act, '| 条数 =', rows, '| 副标题 =', sub)
    print('  第1条标题 =', first)
    OK.append(('单框', '默认激活=今日B站热搜', act == '今日B站热搜', act))
    OK.append(('单框', '显示 10 条', rows == 10, rows))
    OK.append(('单框', '副标题随榜单', '最新投稿' in str(sub), sub))

    # 条状形状
    shape = ev('''(function(){
      var r=document.querySelector(".hot2-list .hot2-row"); if(!r) return null;
      var cs=getComputedStyle(r);
      var cov=r.querySelector(".hot2-cover"), info=r.querySelector(".hot2-info");
      return {display:cs.display,
              covLeft:cov?Math.round(cov.getBoundingClientRect().left):null,
              infoLeft:info?Math.round(info.getBoundingClientRect().left):null,
              rowH:Math.round(r.getBoundingClientRect().height)};
    })()''')
    print('  单条形状 =', shape)
    OK.append(('单框', '条状横向', bool(shape) and shape['display'] == 'flex', shape and shape.get('display')))
    OK.append(('单框', '封面在左/信息在右', bool(shape) and shape['covLeft'] < shape['infoLeft'], shape))

    # 查看更多按钮指向当前榜
    more = ev('(function(){var a=document.querySelector(".hot2-more");return a?a.getAttribute("href"):null})()')
    print('  查看更多 =', more)
    OK.append(('单框', '查看更多指向当前榜', more == '#/hot/fresh', more))
    print('  截图 →', shot('默认今日热搜', {'x': 0, 'y': 0, 'width': 1500, 'height': 1000, 'scale': 1}))

    # ============ 点第二个按钮切换 ============
    print('-' * 78)
    print('【点击「历史B站热门」按钮切换】')
    tb = ev('(function(){var b=document.querySelectorAll(".hot2-tab")[1];var r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    click(tb['x'], tb['y'])
    time.sleep(3)
    act2 = ev('(document.querySelector(".hot2-tab.active")||{}).textContent')
    rows2 = ev('document.querySelectorAll(".hot2-list .hot2-row").length')
    sub2 = ev('(document.querySelector(".hot2-sub")||{}).textContent')
    first2 = ev('(document.querySelector(".hot2-list .hot2-title")||{}).textContent')
    more2 = ev('(function(){var a=document.querySelector(".hot2-more");return a?a.getAttribute("href"):null})()')
    print('  激活 =', act2, '| 条数 =', rows2, '| 副标题 =', sub2)
    print('  第1条标题 =', first2)
    print('  查看更多 =', more2)
    OK.append(('切换', '切到历史热门', act2 == '历史B站热门', act2))
    OK.append(('切换', '切换后仍 10 条', rows2 == 10, rows2))
    OK.append(('切换', '内容确实变了', bool(first2) and first2 != first, '%s → %s' % (first, first2)))
    OK.append(('切换', '查看更多跟着变', more2 == '#/hot/hot', more2))
    OK.append(('切换', '仍是 1 个框', ev('document.querySelectorAll(".hot2-box").length') == 1, None))
    print('  截图 →', shot('切到历史热门', {'x': 0, 'y': 0, 'width': 1500, 'height': 1000, 'scale': 1}))

    # 切回
    tb0 = ev('(function(){var b=document.querySelectorAll(".hot2-tab")[0];var r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    click(tb0['x'], tb0['y'])
    time.sleep(2.5)
    act3 = ev('(document.querySelector(".hot2-tab.active")||{}).textContent')
    first3 = ev('(document.querySelector(".hot2-list .hot2-title")||{}).textContent')
    print('  切回后激活 =', act3, '| 第1条 =', first3)
    OK.append(('切换', '可切回今日热搜', act3 == '今日B站热搜', act3))
    OK.append(('切换', '切回内容正确', first3 == first, '%s vs %s' % (first3, first)))

    # ============ 回归 ============
    print('-' * 78)
    print('【回归】')
    for route, name, sel in [('#/hot/fresh', '详细页', '.video-grid .video-card'),
                             ('#/hot/hot', '详细页2', '.video-grid .video-card'),
                             ('#/music', '同人音乐', '.work-item'),
                             ('#/video', '同人视频', '.video-card')]:
        cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
        cdp('Page.navigate', {'url': BASE + '/' + route}); time.sleep(3.5)
        n = ev('document.querySelectorAll("%s").length' % sel)
        print('  %-10s 元素=%s' % (name, n))
        OK.append(('回归', name, isinstance(n, int) and n > 0, n))

    # 热搜库搜索仍可用
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/hotsearch/%E7%81%B5%E6%A2%A6'})
    time.sleep(4)
    hs = ev('(document.querySelector("#app h2")||{}).textContent')
    print('  热搜库搜索「灵梦」= %s' % hs)
    OK.append(('回归', '热搜库搜索可用', bool(hs) and '热搜库搜索' in str(hs), hs))

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
