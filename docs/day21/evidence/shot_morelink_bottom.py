# -*- coding: utf-8 -*-
"""截取热搜详细页最底部（含「更多请前往 bilibili 查看」外链）的特写。
用法: python shot_morelink_bottom.py <BASE_URL> [out.png]
"""
import base64, json, os, subprocess, sys, time, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:3000/'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'shot-morelink-bottom.png'
PORT = 9400 + int(time.time()) % 400
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
PROFILE = os.path.join(os.environ.get('TEMP', '/tmp'), 'edge-shot-%d' % PORT)

# 清空代理环境，避免拦截本地请求
env = dict(os.environ)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    env.pop(k, None)

proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
                         '--remote-allow-origins=*', '--user-data-dir=' + PROFILE,
                         '--window-size=1440,900', '--hide-scrollbars',
                         '--no-first-run', '--no-default-browser-check', 'about:blank'], env=env)
try:
    ws_url = None
    for _ in range(60):
        try:
            j = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % PORT, timeout=1).read())
            pages = [t for t in j if t.get('type') == 'page']
            if pages:
                ws_url = pages[0]['webSocketDebuggerUrl']
                break
        except Exception:
            pass
        time.sleep(0.3)
    if not ws_url:
        raise SystemExit('无法连接 CDP')

    from websocket import create_connection
    ws = create_connection(ws_url, timeout=30)
    _id = [0]

    def cmd(method, **params):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == _id[0]:
                return m.get('result', {})

    def ev(expr):
        r = cmd('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value')

    cmd('Page.enable')
    cmd('Runtime.enable')
    cmd('Network.enable')
    cmd('Network.setCacheDisabled', cacheDisabled=True)
    cmd('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)

    # 先到首页，再切 hash（直接带 hash navigate 有时不触发路由）
    cmd('Page.navigate', url=BASE)
    time.sleep(2.0)
    ev('location.hash = "#/hot/fresh"')
    for _ in range(60):
        time.sleep(0.4)
        n = ev('document.querySelectorAll("#hotDetailGrid .video-card").length') or 0
        if n > 0:
            break

    # 点几次「展开更多」把内容铺满
    for _ in range(2):
        ev("""(() => {
            const b = document.querySelector('.load-more-btn');
            if (b) { b.scrollIntoView({block:'center'}); b.click(); }
            return !!b;
        })()""")
        time.sleep(0.8)

    # 滚到页面绝对底部
    info = ev("""(() => {
        window.scrollTo(0, document.body.scrollHeight);
        const link = document.querySelector('.hot-more-link');
        const r = link ? link.getBoundingClientRect() : null;
        return {scrollY: window.scrollY, innerH: window.innerHeight,
                docH: document.body.scrollHeight,
                linkTop: r ? r.top : null, linkH: r ? r.height : null,
                text: link ? link.innerText.trim() : null};
    })()""")
    time.sleep(1.2)
    print('滚动位置 =', info)

    # 全视口截图（视口即最终可见区域）
    shot = cmd('Page.captureScreenshot', format='png', captureBeyondViewport=False)
    data = shot.get('data')
    with open(OUT, 'wb') as f:
        f.write(base64.b64decode(data))
    print('截图:', OUT, os.path.getsize(OUT), 'bytes')
    ws.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
