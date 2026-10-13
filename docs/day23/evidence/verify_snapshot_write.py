# -*- coding: utf-8 -*-
"""
Day 23 余力加练 · 回补验证 —— 降级（快照）通道下的 PATCH / DELETE
--------------------------------------------------------------------------------
背景：Day 21 验收记了 F1/F3「应用层无删除能力」，Day 22 补上 DELETE 并在 REST 通道
跑了 19/19。但**快照降级通道**当时没单独验。

为什么这件事值得单独验：
  线上 API Key 一旦失效/被撤，服务会**自动降级到快照通道**。如果降级后 DELETE
  不能用，用户就会遇到「收藏按钮点了没反应」——而且是只在故障期间才出现的那种。
  降级通道的写路径（addFavoriteToSnapshot / deleteFavoriteFromSnapshot /
  updateFavoriteFromSnapshot）三份代码是**各写各的**，必须逐个验过。

跑法：
    python verify_snapshot_write.py [BASE_URL]
    默认 BASE_URL = http://127.0.0.1:3013/
    服务必须以**快照通道**启动（见下方命令），否则这个脚本没有意义。

启动服务的命令（关键：用**空串**挡住 .env 加载器，强制降级）：
    env -u HTTP_PROXY -u HTTPS_PROXY CLOUDBASE_ENV_ID= CLOUDBASE_API_KEY= \
        DATABASE_URL= PG_URL= PORT=3013 node deploy/server.js

⚠️ 安全约定：
  · 快照通道的写会**真的落到 deploy/data/favorites.json**（不像 REST 写远程库）。
  · 所以脚本必须自己备份、自己还原。不传 --keep 时，无论如何都还原。
  · 用专用 userId（snap-test-<时间戳>）隔离，不碰任何真实收藏。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:3013/'
for a in sys.argv[1:]:
    if a.startswith('http'):
        BASE = a
KEEP = '--keep' in sys.argv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
FAV = os.path.join(ROOT, 'deploy', 'data', 'favorites.json')
BAK = FAV + '.day23bak'

USER = 'snap-test-' + str(int(time.time()))
WORK = 'music-1'        # 真实存在的作品

PASS = 0
FAIL = 0


def ck(name, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  [PASS] ' + name)
    else:
        FAIL += 1
        print('  [FAIL] ' + name + ('  >> ' + str(extra) if extra else ''))


def api(method, path, body=None, timeout=10):
    """所有请求都带超时 —— 万一服务半路挂了，脚本要能自己结束，不能永久挂住。"""
    url = BASE.rstrip('/') + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'} if body is not None else {},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, None
    except Exception as e:
        return -1, {'_err': str(e)}


def main():
    print('=' * 60)
    print('降级（快照）通道写操作验证 · ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    print('=' * 60)

    # ---- 环境确认：必须真的是快照通道，否则这脚本没意义 ----
    st, j = api('GET', '/api/health')
    src = ((j or {}).get('checks') or {}).get('dataSource')
    print('')
    print('[环境确认] /api/health HTTP %s, dataSource=%s' % (st, src))
    if src != 'snapshot':
        print('>>> 环境不对：dataSource 应为 snapshot，实际是 %r。' % src)
        print('>>> 请用空串环境变量强制降级后再跑（见文件头注释）。')
        return 2

    print('')
    print('---- ① POST：新增一条 ----')
    st, j = api('POST', '/api/favorites', {'userId': USER, 'workId': WORK, 'note': '降级通道测试'})
    ck('POST 返回 201', st == 201, 'HTTP %s' % st)
    ck('source 是 snapshot', (j or {}).get('source') == 'snapshot', (j or {}).get('source'))
    fid = ((j or {}).get('data') or {}).get('id')
    print('  新条 id=%s' % fid)
    ck('响应带 id', fid is not None)

    print('')
    print('---- ② GET：能看到这条 ----')
    st, j = api('GET', '/api/favorites?userId=' + USER)
    ids = [x.get('id') for x in ((j or {}).get('data') or [])]
    ck('GET 返回 200', st == 200, 'HTTP %s' % st)
    ck('列表含新条', fid in ids, ids)

    print('')
    print('---- ③ PATCH：改备注 ----')
    st, j = api('PATCH', '/api/favorites/%s' % fid, {'note': '降级通道改过的备注'})
    ck('PATCH 返回 200', st == 200, 'HTTP %s' % st)
    ck('响应含新备注', ((j or {}).get('data') or {}).get('note') == '降级通道改过的备注',
       ((j or {}).get('data') or {}).get('note'))

    print('')
    print('---- ④ DELETE：软删除 ----')
    st, j = api('DELETE', '/api/favorites/%s' % fid)
    ck('DELETE 返回 200', st == 200, 'HTTP %s' % st)
    ck('回传被删那条作凭证', ((j or {}).get('data') or {}).get('id') == fid)

    print('')
    print('---- ⑤ GET：删除后已消失 ----')
    st, j = api('GET', '/api/favorites?userId=' + USER)
    ids = [x.get('id') for x in ((j or {}).get('data') or [])]
    ck('GET 返回 200', st == 200)
    ck('列表里已无该条', fid not in ids, ids)

    print('')
    print('---- ⑥ 幂等：二次 DELETE 应 404 ----')
    st, _ = api('DELETE', '/api/favorites/%s' % fid)
    ck('二次 DELETE 返回 404', st == 404, 'HTTP %s' % st)

    print('')
    print('---- ⑦ 落盘：快照文件里该行 isDeleted=true ----')
    try:
        with open(FAV, 'r', encoding='utf-8') as f:
            snap = json.load(f)
        row = [r for r in (snap.get('items') or []) if r.get('id') == fid]
        ck('快照里找得到该行', len(row) == 1)
        ck('该行 isDeleted === true', bool(row) and row[0].get('isDeleted') is True,
           row[0] if row else None)
    except Exception as e:
        ck('快照文件可读', False, e)

    print('')
    print('---- ⑧ 复活：再收藏同一作品应复用旧行 ----')
    st, j = api('POST', '/api/favorites', {'userId': USER, 'workId': WORK, 'note': '复活后'})
    ck('复活 POST 返回 201', st == 201, 'HTTP %s' % st)
    new_id = ((j or {}).get('data') or {}).get('id')
    ck('复活复用同一条（id 不变）', new_id == fid, '原 %s / 新 %s' % (fid, new_id))

    print('')
    print('=' * 60)
    print('结果：PASS=%d  FAIL=%d' % (PASS, FAIL))
    if FAIL == 0:
        print('>>> ✅ 降级通道的 PATCH / DELETE / 复活 全部可用')
    else:
        print('>>> ❌ 有失败项')
    return 0 if FAIL == 0 else 1


# ---- 备份 + 无论如何都还原 ----
backed = False
try:
    if os.path.exists(FAV):
        with open(FAV, 'rb') as s, open(BAK, 'wb') as d:
            d.write(s.read())
        backed = True
    rc = main()
finally:
    if backed and not KEEP:
        with open(BAK, 'rb') as s, open(FAV, 'wb') as d:
            d.write(s.read())
        os.remove(BAK)
        print('')
        print('（快照已还原: %d bytes）' % os.path.getsize(FAV))
    elif KEEP:
        print('')
        print('（--keep：未还原，备份留在 %s）' % BAK)

sys.exit(rc)
