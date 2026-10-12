# -*- coding: utf-8 -*-
"""
Day 22 证据脚本 · 用无头浏览器在验证页上真实点 PATCH / DELETE，出两张截图
--------------------------------------------------------------------------------
产出（存 docs/day22/evidence/）：
  patch-改前改后对比.png   —— PATCH 后：改前 note → 改后 note + 接口返回 + GET 探针
  delete-删除后消失.png    —— DELETE 后：该条在 GET 里已消失

为什么要用浏览器而不是 curl：
  今天要交的截图是**页面上能看到的东西**。curl 的输出没有页面，
  而且这个页面的价值就是「把改前/改后摆在一起」——只有真的跑一遍才知道
  对比条、探针那几块是不是按预期显示。

流程：
  ① 打开 /verify/
  ② 等页面自动选好「最新一条」→ 记下 id 与改前 note
  ③ 点「发起 PATCH 改备注」→ 截图①
  ④ 点「发起 DELETE 取消收藏」（先 hook confirm 直接放行）→ 截图②
  ⑤ 收尾：把库恢复原状（这几步会真的动数据，脚本结束前必须还原）
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:3000/'
OUTDIR = os.path.dirname(os.path.abspath(__file__))
PORT = 9500 + int(time.time()) % 400
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
PROFILE = os.path.join(os.environ.get('TEMP', '/tmp'), 'edge-day22-%d' % PORT)

env = dict(os.environ)
# ⚠️ 清掉代理环境变量。
#   本机出公网要走 HTTP_PROXY（127.0.0.1:53402），但无头浏览器**不能**用它：
#   实测给它 --proxy-server 之后，连本地 127.0.0.1:3000 的请求也被绕进代理，
#   返回的不是 JSON，页面上所有 fetch 全废（探针报 "reading 'count' of null"）。
#   反过来清掉代理最稳：本地 3000 直连正常。
#   副作用只有一个 —— 页面上 Day 20 那张「云函数 api-health」卡片会显示失败
#   （它要连公网）。这不影响今天的验证：截图用 shot_card() **只裁 CRUD 卡片**，
#   那张 health 卡片根本不进画面。
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    env.pop(k, None)

proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
                         '--remote-allow-origins=*', '--user-data-dir=' + PROFILE,
                         '--window-size=1440,1000', '--hide-scrollbars',
                         '--no-first-run', '--no-default-browser-check', 'about:blank'], env=env)

ws = None


def http_json(path):
    return json.loads(urllib.request.urlopen('http://127.0.0.1:%d%s' % (PORT, path), timeout=2).read())


def api(method, path, body=None):
    url = BASE.rstrip('/') + path
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


try:
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
    cmd('Network.enable')
    cmd('Network.setCacheDisabled', cacheDisabled=True)
    cmd('Emulation.setDeviceMetricsOverride', width=1440, height=1000, deviceScaleFactor=1, mobile=False)

    def shot_card(name):
        """只截 CRUD 卡片那一块（按元素的绝对坐标裁），
        这样不会把下面的 health 卡片一起拍进去 —— 那张卡片走公网云函数，
        在无头环境里本机代理配置不一定吃得准，容易显示成失败，干扰截图重点。"""
        box = ev("""(() => {
            const el = document.getElementById('crudCard');
            const r = el.getBoundingClientRect();
            return {x: r.left + window.scrollX, y: r.top + window.scrollY,
                    w: r.width, h: r.height};
        })()""")
        clip = {'x': max(0, box['x'] - 12), 'y': max(0, box['y'] - 12),
                'width': box['w'] + 24, 'height': box['h'] + 24}
        data = cmd('Page.captureScreenshot', format='png',
                   captureBeyondViewport=True, clip=dict(clip, scale=1)).get('data')
        p = os.path.join(OUTDIR, name)
        with open(p, 'wb') as f:
            f.write(base64.b64decode(data))
        print('  截图: %s (%d bytes)  卡片尺寸 %dx%d'
              % (name, os.path.getsize(p), box['w'], box['h']))
        return p

    # ---- 记录「跑之前」的库状态，收尾要还原 ----
    _, before = api('GET', '/api/favorites?limit=200')
    before_map = {int(x['id']): x.get('note') for x in (before or {}).get('data', [])}
    print('跑前库里 %d 条' % len(before_map))

    # ---- ★ 先造一条专门的测试数据，PATCH / DELETE 都只动它 ----
    # 为什么必须这样：不能拿existing的真实记录做实验 ——
    # 删掉后即使补一条新的回来，原 id 也已经永久消失，
    # 「跑完和跑前一致」就成了假话。自己造的测试数据，自己删掉，才算真的干净。
    test_work = 'art-3'   # 随便挑一件作品，不碰库里已有的收藏
    # 若 art-3 已被收藏（409），换一件，保证一定能插进去
    for cand in ['art-3', 'art-4', 'art-5', 'art-1', 'art-2']:
        st0, j0 = api('POST', '/api/favorites',
                      {'workId': cand, 'note': 'Day22 截图用的测试数据（用完即删）'})
        if st0 == 201:
            test_work = cand
            break
    test_id = int(j0['data']['id'])
    print('已造测试数据：id=%d workId=%s （只动这一条）' % (test_id, test_work))

    # ---- 打开验证页 ----
    cmd('Page.navigate', url=BASE.rstrip('/') + '/verify/')
    time.sleep(3.0)

    # 等 JS 跑完（它会自动选 id 最大的那条 = 刚造的测试数据）
    for _ in range(40):
        v = ev("document.getElementById('cId') && document.getElementById('cId').value")
        if v:
            break
        time.sleep(0.3)

    # 手动把 id 固定成刚造的那条，避免「最新一条」判断有偏差
    ev("document.getElementById('cId').value = '%d';" % test_id)
    ev("""(() => {
        // 触发一次读取，让对比条的「改前」显示这条现在的 note
        const id = document.getElementById('cId').value;
        return fetch('/api/favorites?limit=200').then(r => r.json()).then(j => {
            const hit = (j.data || []).filter(x => Number(x.id) === Number(id))[0];
            document.getElementById('ccBefore').textContent = hit ? String(hit.note) : '（找不到该条）';
            document.getElementById('ccAfter').textContent = '（还没改）';
            return true;
        });
    })()""")
    time.sleep(0.8)
    target_id = ev("document.getElementById('cId').value")
    before_note = ev("document.getElementById('ccBefore').textContent")
    print('页面选中的 id = %s，改前 note = %r' % (target_id, before_note))

    # 把 CRUD 卡片滚进视口（截图要拍它）
    ev("document.getElementById('crudCard').scrollIntoView({block:'start'}); window.scrollBy(0,-20);")
    time.sleep(0.6)

    # ================= ① PATCH =================
    print('\n=== ① 点「发起 PATCH 改备注」 ===')
    ev("document.getElementById('cNote').value = 'Day22 闭环验证：这条备注是 PATCH 改的';")
    ev("""(() => {
        const b = document.getElementById('btnPatch');
        b.scrollIntoView({block:'center'});
        b.click();
        return true;
    })()""")
    time.sleep(2.2)

    after_status = ev("document.getElementById('cStatus').textContent")
    cc_before = ev("document.getElementById('ccBefore').textContent")
    cc_after = ev("document.getElementById('ccAfter').textContent")
    alive = ev("document.getElementById('cAlive').textContent")
    print('  状态: %s' % after_status)
    print('  改前: %r' % cc_before)
    print('  改后: %r' % cc_after)
    print('  探针: %r' % alive)

    time.sleep(0.4)
    shot_card('patch-改前改后对比.png')

    # ================= ② DELETE =================
    print('\n=== ② 点「发起 DELETE 取消收藏」 ===')
    # confirm 弹窗会阻塞，先 hook 成「直接确定」
    ev("window.confirm = function(){ return true; };")
    # 让对比条先显示「删除前还在」，随后点删除
    ev("""(() => {
        const b = document.getElementById('btnDelete');
        b.scrollIntoView({block:'center'});
        b.click();
        return true;
    })()""")
    time.sleep(2.2)

    del_status = ev("document.getElementById('cStatus').textContent")
    alive2 = ev("document.getElementById('cAlive').textContent")
    print('  状态: %s' % del_status)
    print('  探针: %r' % alive2)

    time.sleep(0.4)
    shot_card('delete-删除后消失.png')

    # 断言（截图之外再机械核一遍）
    print('\n=== 机械核对 ===')
    checks = []
    checks.append(('PATCH 返回 200', 'HTTP 200' in (after_status or '')))
    checks.append(('改前 ≠ 改后', cc_before != cc_after))
    checks.append(('DELETE 返回 200', 'HTTP 200' in (del_status or '')))
    checks.append(('删后探针显示已消失', '消失' in (alive2 or '')))
    _, after = api('GET', '/api/favorites?limit=200')
    ids_after = [int(x['id']) for x in (after or {}).get('data', [])]
    checks.append(('该 id 已不在 GET 里', int(target_id) not in ids_after))
    ok = True
    for n, c in checks:
        print('  [%s] %s' % ('PASS' if c else 'FAIL', n))
        ok = ok and c

    # ================= 收尾：还原 =================
    print('\n=== 收尾：还原库 ===')
    # 测试数据是自己造的，DELETE 时已经被删掉了；这里再兜一次（幂等，404 也无所谓）
    st, _ = api('DELETE', '/api/favorites/%s' % target_id)
    print('  清理测试数据 id=%s → HTTP %s%s'
          % (target_id, st, '（本就已删）' if st == 404 else ''))

    # 逐条对比：跑前登记的**真实数据**都还在吗？有没有多出来的？
    # 注意 before_map 只装「跑之前就在库里的」记录，测试数据不在其中 ——
    # 测试数据跑完被删掉是**预期结果**，不算「少掉的 id」。
    _, final = api('GET', '/api/favorites?limit=200')
    final_map = {int(x['id']): x.get('note') for x in (final or {}).get('data', [])}
    extra = set(final_map) - set(before_map)
    missing = set(before_map) - set(final_map)
    note_changed = {i for i in set(final_map) & set(before_map) if final_map[i] != before_map[i]}
    print('  跑后库里 %d 条（跑前 %d 条；另造 1 条测试数据 id=%s，已删）'
          % (len(final_map), len(before_map), test_id))
    print('  多出来的 id：%s' % (sorted(extra) or '无'))
    print('  少掉的 id：%s' % (sorted(missing) or '无'))
    print('  备注被改动的 id：%s' % (sorted(note_changed) or '无'))
    clean = (not extra) and (not missing) and (not note_changed) and (test_id not in final_map)
    print('  [%s] 原有数据一条没动，测试数据已清除' % ('PASS' if clean else 'FAIL'))
    ok = ok and clean

    sys.exit(0 if ok else 1)

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
