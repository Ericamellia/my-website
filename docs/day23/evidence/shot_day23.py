# -*- coding: utf-8 -*-
"""
Day 23 证据脚本 · 出两张截图
--------------------------------------------------------------------------------
产出（存 docs/day23/evidence/）：
  secret-scan-0条.png      —— ① 全仓库搜密钥特征词的结果（要有 0 条）
  三类错误中文提示.png      —— ② 三类错误（400 / 404 / 5xx）的中文提示

做法：先把「真实跑出来的结果」渲染成一个 HTML 结果页，再用无头浏览器截图。
不手写结论 —— 页面上的每一行都来自刚刚实际执行的命令/请求，
否则截图就成了「自己画的图」，没有证明力。

⚠️ 本机代理坑（Day 22 已踩）：无头浏览器不能走 HTTP_PROXY（127.0.0.1:53402），
   否则连本地 127.0.0.1 的请求也被绕进代理。所以启动前清掉代理环境变量。
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
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))   # 项目根
PORT = 9600 + int(time.time()) % 300
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
PROFILE = os.path.join(os.environ.get('TEMP', '/tmp'), 'edge-day23-%d' % PORT)

env = dict(os.environ)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    env.pop(k, None)


def run(cmd):
    """跑一条 shell 命令，返回 (stdout+stderr, exitcode)。"""
    p = subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True,
                       env=env, timeout=120)
    out = (p.stdout or b'').decode('utf-8', 'replace') + (p.stderr or b'').decode('utf-8', 'replace')
    return out.strip(), p.returncode


def api(method, path, body=None, base='http://127.0.0.1:3010'):
    url = base.rstrip('/') + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data,
                               headers={'Content-Type': 'application/json'} if body else {},
                               method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, None


# ============================================================================
# 第一步：真实采集两类证据
# ============================================================================
print('=== 采集证据 ===')

# ---- 证据 ①：密钥扫描 ----
scan_out, _ = run('bash docs/day23/evidence/secret-scan.sh')
print('密钥扫描完成，%d 字符' % len(scan_out))

# ---- 证据 ②：三类错误（服务已在 3010 跑着，由外部脚本负责起停）----
# 这里直接打请求，采三类的代表各一条
probes = []
cases = [
    ('① 入参校验 · 缺 workId', 'POST', '/api/favorites', {'userId': 'demo'}),
    ('① 入参校验 · workId 格式错', 'POST', '/api/favorites', {'userId': 'demo', 'workId': '@@@'}),
    ('① 入参校验 · PATCH 空 body', 'PATCH', '/api/favorites/1', {}),
    ('① 入参校验 · 非法 JSON', 'RAW', '/api/favorites', '{bad json'),
    ('② 资源不存在 · PATCH 不存在的 id', 'PATCH', '/api/favorites/99999', {'note': 'x'}),
    ('② 资源不存在 · 作品不存在', 'POST', '/api/favorites', {'userId': 'demo', 'workId': 'music-999999'}),
]
for name, method, path, body in cases:
    if method == 'RAW':
        req = urllib.request.Request('http://127.0.0.1:3010' + path,
                                     data=body.encode(),
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                st, j = resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            st, j = e.code, json.loads(e.read().decode())
    else:
        st, j = api(method, path, body)
    probes.append((name, st, j))
    print('  %-38s → HTTP %s' % (name, st))

# 第三类：由外部先造好（快照缺失），这里打 /api/circles 拿 503
st3, j3 = api('GET', '/api/circles')
probes.append(('③ 服务端异常 · 快照缺失（数据取不到）', st3, j3))
print('  %-38s → HTTP %s' % ('③ 服务端异常', st3))

# ============================================================================
# 第二步：渲染 HTML 结果页
# ============================================================================


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def probe_card(name, st, j):
    jj = json.dumps(j, ensure_ascii=False, indent=2) if j is not None else '(无响应体)'
    return (
        '<div class="pcard">'
        '<div class="pname">{name}</div>'
        '<div class="pline"><span class="st s{st}">HTTP {st}</span></div>'
        '<pre>{body}</pre>'
        '</div>'
    ).format(name=esc(name), st=st, body=esc(jj))


cards = '\n'.join(probe_card(n, s, j) for n, s, j in probes)

HTML = u"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Day 23 证据</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; padding:22px 26px; background:#f6f7f9; color:#1b1f24;
         font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }
  h1 { font-size:19px; margin:0 0 4px; }
  .sub { color:#5b6b7c; font-size:12px; margin-bottom:16px; }
  .panel { background:#fff; border:1px solid #e2e6ea; border-radius:10px;
           padding:16px 18px; margin-bottom:16px; }
  .panel h2 { font-size:15px; margin:0 0 10px; padding-bottom:8px;
              border-bottom:1px solid #eef1f4; }
  pre { margin:0; font-family:Consolas,"Courier New",monospace; font-size:11.5px;
        line-height:1.5; white-space:pre-wrap; word-break:break-all; }
  .scan { background:#0d1117; color:#c9d1d9; border-radius:8px; padding:13px 15px; }
  .probes { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .pcard { border:1px solid #e6eaee; border-radius:8px; overflow:hidden; background:#fcfdfe; }
  .pname { background:#f0f3f6; padding:7px 11px; font-size:12px; font-weight:600; }
  .pline { padding:5px 11px; }
  .st { display:inline-block; padding:1px 9px; border-radius:20px; font-size:11px;
        font-weight:700; color:#fff; }
  .st400 { background:#d68a00; } .st404 { background:#a4653a; }
  .st503 { background:#c0392b; } .st200 { background:#2e8b57; }
  .pcard pre { padding:8px 11px 11px; color:#2f3a45; }
  .foot { color:#6b7a8c; font-size:11px; margin-top:6px; }
</style></head><body>
  <h1>Day 23 · 上线红线三件套 · 实测证据</h1>
  <div class="sub">生成时间 __TS__ ｜ 全部内容来自本机真实执行，非手写</div>

  <div class="panel">
    <h2>① 密钥排查 —— 全仓库搜索密钥特征词</h2>
    <pre class="scan">__SCAN__</pre>
  </div>

  <div class="panel">
    <h2>② 三类错误提示 —— 中文人话（响应体）</h2>
    <div class="probes">
__CARDS__
    </div>
    <div class="foot">注：「服务端异常」一类需把服务切到快照通道并移走数据文件才能触发；
        外部脚本已先行制造该条件。</div>
  </div>
</body></html>
"""

# ⚠️ 用占位符替换，不用 str.format —— 页面里有 CSS 花括号 `{...}`，
#    format() 会把它们当占位符，直接 KeyError: ' box-sizing'（已踩过一次）。
HTML = (HTML
        .replace('__TS__', esc(time.strftime('%Y-%m-%d %H:%M:%S')))
        .replace('__SCAN__', esc(scan_out))
        .replace('__CARDS__', cards))

page = os.path.join(HERE, '_evidence_page.html')
with open(page, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('结果页已生成: %s' % page)

# ============================================================================
# 第三步：无头浏览器截图
# ============================================================================
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
                         '--remote-allow-origins=*', '--user-data-dir=' + PROFILE,
                         '--window-size=1280,1400', '--hide-scrollbars',
                         '--no-first-run', '--no-default-browser-check', 'about:blank'], env=env)
ws = None
try:
    def http_json(path):
        return json.loads(urllib.request.urlopen(
            'http://127.0.0.1:%d%s' % (PORT, path), timeout=2).read())

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

    cmd('Page.enable')
    cmd('Runtime.enable')
    cmd('Emulation.setDeviceMetricsOverride', width=1280, height=1400,
        deviceScaleFactor=1, mobile=False)

    cmd('Page.navigate', url='file:///' + page.replace('\\', '/'))
    # 导航后必须等新文档真正可用，否则 evaluate 还挂在旧文档上 → 元素取不到返回 None。
    # 用「轮询到元素出现」最稳，比死等 sleep 靠谱。
    box_ok = None
    for _ in range(50):
        try:
            box_ok = ev("document.querySelector('.panel') ? 1 : 0")
        except Exception:
            box_ok = None
        if box_ok:
            break
        time.sleep(0.3)
    print('  页面就绪: %s（.panel 命中=%s）' % (page, box_ok))
    time.sleep(0.5)

    def shot_panel(idx, name, pad=14):
        """按 .panel 的**索引**取（0=密钥面板，1=错误面板）。
        别用 :nth-of-type(n) —— 那是按「同类型兄弟」计数，body 下 .panel 前面
        还有 h1 和 .sub 两个 div，nth-of-type(1) 会落到 .sub 上（已踩）。"""
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
            raise RuntimeError('.panel[%d] 取不到元素' % idx)
        clip = {'x': max(0, box['x'] - pad), 'y': max(0, box['y'] - pad),
                'width': box['w'] + pad * 2, 'height': box['h'] + pad * 2}
        data = cmd('Page.captureScreenshot', format='png',
                   captureBeyondViewport=True, clip=dict(clip, scale=1)).get('data')
        p = os.path.join(HERE, name)
        with open(p, 'wb') as f:
            f.write(base64.b64decode(data))
        print('  截图: %s (%d bytes) %dx%d' % (name, os.path.getsize(p), box['w'], box['h']))
        return p

    print('\n=== 截图 ===')
    shot_panel(0, 'secret-scan-0条.png')
    shot_panel(1, '三类错误中文提示.png')

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
