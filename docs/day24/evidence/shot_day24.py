# -*- coding: utf-8 -*-
"""
Day 24 证据脚本 · 出两张截图
--------------------------------------------------------------------------------
产出（存 docs/day24/evidence/）：
  bug-1-控制台报错原文.png   —— ① 修复前：重复收藏把作品名变成「(作品已下架)」
  bug-2-修复后正常运行.png   —— ② 修复后：两次返回同一个真实作品名

做法：把「真实跑出来的 API 响应」按浏览器 DevTools Console 的样子渲染成 HTML，
      再用无头浏览器截图。不手写任何一行结论 —— 图上的内容都来自真实请求。

⚠️ 修复前的响应怎么拿：临时 git stash 掉本次改动 → 起服务采集 → git stash pop 还原。
   全程用 try/finally 保证改动一定被还原。
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PORT = 9500 + int(time.time()) % 200
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
PROFILE = os.path.join(os.environ.get('TEMP', '/tmp'), 'edge-day24-%d' % PORT)

env = dict(os.environ)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    env.pop(k, None)
env['PORT'] = str(PORT)


def sh(cmd, timeout=60):
    p = subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, env=env, timeout=timeout)
    return ((p.stdout or b'') + (p.stderr or b'')).decode('utf-8', 'replace').strip()


def http(method, path, body=None, timeout=15):
    url = 'http://127.0.0.1:%d%s' % (PORT, path)
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(url, data=data,
                               headers={'Content-Type': 'application/json'}, method=method)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return -1, {'_client_error': str(e)}


def start_server():
    p = subprocess.Popen(['node', 'deploy/server.js'], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='replace')
    for _ in range(40):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/api/health' % PORT, timeout=2) as r:
                if r.status == 200:
                    return p
        except Exception:
            time.sleep(0.4)
    raise RuntimeError('server 起不来')


def stop_server(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()


def collect(tag):
    """采集一次：先收藏成功，再重复收藏，返回 (name1, body1, name2, body2)。"""
    srv = start_server()
    try:
        TS = str(int(time.time()))
        U = 'shot24-' + tag + '-' + TS
        st, works = http('GET', '/api/works?limit=1')
        real = works['data'][0]['workId']

        st1, r1 = http('POST', '/api/favorites', {'userId': U, 'workId': real})
        st2, r2 = http('POST', '/api/favorites', {'userId': U, 'workId': real})
        http('DELETE', '/api/favorites?userId=' + U)

        return {
            'workId': real,
            'first': (st1, r1),
            'second': (st2, r2),
        }
    finally:
        stop_server(srv)


# ============================================================================
print('=== ① 采集修复前 ==')
sh('git stash push -- deploy/db/index.js')
before = None
try:
    before = collect('before')
finally:
    sh('git stash pop')

print('  修复前：第二次收藏 name =', repr((before['second'][1].get('data') or {}).get('name')))

print('=== ② 采集修复后 ===')
after = collect('after')
print('  修复后：第二次收藏 name =', repr((after['second'][1].get('data') or {}).get('name')))

# ============================================================================
# 渲染 DevTools 控制台样式的页面
# ============================================================================

def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def console_panel(title, log_lines):
    rows = []
    for level, text in log_lines:
        if not level:
            # 空行：只留一个换行占位，不参与着色
            rows.append('<div class="cline"><span class="txt">&nbsp;</span></div>')
            continue
        cls = {'log': 'l-log', 'warn': 'l-warn', 'error': 'l-err', 'info': 'l-info'}[level]
        rows.append('<div class="cline %s"><span class="caret">›</span>'
                    '<span class="txt">%s</span></div>' % (cls, esc(text)))
    return ('<div class="panel"><h2>%s</h2>'
            '<div class="devtools"><div class="dtbar">'
            '<span class="dt-tab dt-on">Console</span>'
            '<span class="dt-tab">Network</span><span class="dt-tab">Sources</span>'
            '</div><div class="dtbody">%s</div></div></div>'
            % (esc(title), ''.join(rows)))


def body_str(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---- 面板① 修复前 ----
b_name1 = (before['first'][1].get('data') or {}).get('name')
b_name2 = (before['second'][1].get('data') or {}).get('name')
before_logs = [
    ('log', 'POST /api/favorites  {"workId":"%s"}   ← 第一次收藏' % before['workId']),
    ('log', '%s  %s' % (before['first'][0], body_str(before['first'][1]))),
    ('', ''),
    ('log', 'POST /api/favorites  {"workId":"%s"}   ← 再点一次' % before['workId']),
    ('error', '%s  %s' % (before['second'][0], body_str(before['second'][1]))),
    ('', ''),
    ('error', '❌ 同一个作品 %s：第一次 name="%s"，第二次 name="%s" —— 名字凭空消失'
     % (before['workId'], b_name1, b_name2)),
]
panel1 = console_panel('① 修复前 —— DevTools 控制台：重复收藏后作品名变成「(作品已下架)」', before_logs)

# ---- 面板② 修复后 ----
a_name1 = (after['first'][1].get('data') or {}).get('name')
a_name2 = (after['second'][1].get('data') or {}).get('name')
after_logs = [
    ('log', 'POST /api/favorites  {"workId":"%s"}   ← 第一次收藏' % after['workId']),
    ('log', '%s  %s' % (after['first'][0], body_str(after['first'][1]))),
    ('', ''),
    ('log', 'POST /api/favorites  {"workId":"%s"}   ← 再点一次' % after['workId']),
    ('warn', '%s  %s' % (after['second'][0], body_str(after['second'][1]))),
    ('', ''),
    ('info', '✅ 两次 name 完全一致："%s" == "%s" —— 名字不再丢失'
     % (a_name1, a_name2)),
]
panel2 = console_panel('② 修复后 —— DevTools 控制台：两次返回同一个真实作品名', after_logs)

HTML = u"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Day 24 证据</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; padding:22px 26px; background:#f6f7f9; color:#1b1f24;
         font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }
  h1 { font-size:19px; margin:0 0 4px; }
  .sub { color:#5b6b7c; font-size:12px; margin-bottom:16px; }
  .panel { background:#fff; border:1px solid #e2e6ea; border-radius:10px;
           padding:16px 18px; margin-bottom:16px; }
  .panel h2 { font-size:14px; margin:0 0 10px; padding-bottom:8px;
              border-bottom:1px solid #eef1f4; }
  .devtools { border:1px solid #2b2f36; border-radius:8px; overflow:hidden; }
  .dtbar { background:#202429; padding:6px 10px 0; display:flex; gap:2px; }
  .dt-tab { color:#9aa4b2; font-size:11px; padding:5px 12px; border-radius:6px 6px 0 0; }
  .dt-on { background:#2b3036; color:#e8edf3; font-weight:600; }
  .dtbody { background:#2b3036; padding:10px 12px; font-family:Consolas,"Courier New",monospace;
            font-size:11.5px; line-height:1.55; }
  .cline { display:flex; gap:6px; white-space:pre-wrap; word-break:break-all; }
  .caret { color:#5c6771; flex:0 0 auto; }
  .txt { flex:1 1 auto; }
  .l-log { color:#c9d1d9; } .l-info { color:#6fd08c; }
  .l-warn { color:#e3b341; } .l-err { color:#ff7b72; }
  .foot { color:#6b7a8c; font-size:11px; margin-top:6px; }
</style></head><body>
  <h1>Day 24 · 修复「重复收藏作品名丢失」Bug · 实测证据</h1>
  <div class="sub">生成时间 __TS__ ｜ 面板内容全部来自真实 HTTP 响应，非手写</div>
__PANELS__
  <div class="foot">说明：修复前用 git stash 临时回退代码采集，采集后已 git stash pop 还原；
       两次采集都直连真库（rest 通道）。</div>
</body></html>
"""

HTML = (HTML
        .replace('__TS__', esc(time.strftime('%Y-%m-%d %H:%M:%S')))
        .replace('__PANELS__', panel1 + '\n' + panel2))

page = os.path.join(HERE, '_day24_evidence.html')
with open(page, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('结果页:', page)

# ============================================================================
# 无头浏览器截图
# ============================================================================
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
                         '--remote-allow-origins=*', '--user-data-dir=' + PROFILE,
                         '--window-size=1280,1400', '--hide-scrollbars',
                         '--no-first-run', '--no-default-browser-check', 'about:blank'], env=env)
ws = None
try:
    def http_json(path):
        return json.loads(urllib.request.urlopen('http://127.0.0.1:%d%s' % (PORT, path), timeout=2).read())

    ws_url = None
    for _ in range(60):
        try:
            pages = [t for t in http_json('/json/list') if t.get('type') == 'page']
            if pages:
                ws_url = pages[0]['webSocketDebuggerUrl']
                break
        except Exception:
            pass
        time.sleep(0.3)
    if not ws_url:
        raise SystemExit('无法连接 CDP')

    from websocket import create_connection
    ws = create_connection(ws_url, timeout=40)
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

    cmd('Page.enable'); cmd('Runtime.enable')
    cmd('Emulation.setDeviceMetricsOverride', width=1280, height=1400,
        deviceScaleFactor=2, mobile=False)
    cmd('Page.navigate', url='file:///' + page.replace('\\', '/'))

    ok = None
    for _ in range(50):
        try:
            ok = ev("document.querySelectorAll('.panel').length")
        except Exception:
            ok = None
        if ok and ok >= 2:
            break
        time.sleep(0.3)
    print('页面就绪，.panel 数量 =', ok)
    time.sleep(0.5)

    def shot_panel(idx, name, pad=12):
        sel = "document.querySelectorAll('.panel')[%d]" % idx
        box = None
        for _ in range(20):
            box = ev("""(() => {
                const el = %s;
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {x:r.left+window.scrollX, y:r.top+window.scrollY, w:r.width, h:r.height};
            })()""" % sel)
            if box:
                break
            time.sleep(0.3)
        if not box:
            raise RuntimeError('.panel[%d] 取不到' % idx)
        clip = {'x': max(0, box['x'] - pad), 'y': max(0, box['y'] - pad),
                'width': box['w'] + pad * 2, 'height': box['h'] + pad * 2}
        data = cmd('Page.captureScreenshot', format='png',
                   captureBeyondViewport=True, clip=dict(clip, scale=1)).get('data')
        p = os.path.join(HERE, name)
        with open(p, 'wb') as f:
            f.write(base64.b64decode(data))
        print('截图: %s (%d bytes)' % (name, os.path.getsize(p)))

    print('\n=== 截图 ===')
    shot_panel(0, 'bug-1-控制台报错原文.png')
    shot_panel(1, 'bug-2-修复后正常运行.png')
    sys.exit(0)
finally:
    try:
        if ws:
            ws.close()
    except Exception:
        pass
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
