# -*- coding: utf-8 -*-
"""
Day 24 板块① 复现脚本 —— 外键违规被误判成「重复收藏」

目的：直接对真库（PostgREST 通道）发三个请求，把**原始响应**打出来，
      看清 PostgREST 对外键违规（23503）到底回什么状态码。

三个请求：
  A. 唯一冲突  —— 已存在的 (user_id, work_id) 再插一次   → 期望 409 + 23505
  B. 外键违规  —— work_id 指向不存在的作品               → 期望 409 + 23503（关键！）
  C. 正常插入  —— 全新 (user_id, work_id)，用完即删      → 期望 201

用法（在项目根目录）：
  python docs/day24/evidence/repro_fk_409.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_env(path):
    """读 .env（只取键值，不做任何打印）。"""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env(os.path.join(ROOT, '.env'))
# 也允许被 deploy/.env 覆盖（server.js 的内建加载器会读它，这里对齐一下）
ENV.update(load_env(os.path.join(ROOT, 'deploy', '.env')))

ENV_ID = ENV.get('CLOUDBASE_ENV_ID', '')
API_KEY = ENV.get('CLOUDBASE_API_KEY', '')

if not ENV_ID or not API_KEY:
    print('[FATAL] 缺少 CLOUDBASE_ENV_ID / CLOUDBASE_API_KEY，无法复现')
    sys.exit(2)

BASE = 'https://' + ENV_ID + '.api.tcloudbasegateway.com/v1/rdb/rest/'


def req(method, table, query=None, body=None, prefer=None, timeout=15):
    """发一个 PostgREST 请求，返回 (status, data)。带超时，不带代理。"""
    url = BASE + table
    if query:
        parts = []
        for k, v in query.items():
            if v is None:
                continue
            parts.append(urllib.parse.quote(str(k), safe='') + '=' + urllib.parse.quote(str(v), safe=''))
        if parts:
            url += '?' + '&'.join(parts)

    headers = {
        'Authorization': 'Bearer ' + API_KEY,
        'Content-Type': 'application/json',
    }
    if prefer:
        headers['Prefer'] = prefer

    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)

    # 强制不走代理（本机代理会劫持请求）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return -1, {'_client_error': str(e)}


import urllib.parse  # noqa: E402  (放在这里避免顶部顺序困扰)


def show(tag, status, data):
    print('')
    print('=' * 68)
    print(tag)
    print('-' * 68)
    print('HTTP 状态码 =', status)
    print('响应体原文  =', json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data)
    code = ''
    if isinstance(data, dict):
        code = str(data.get('code') or data.get('message') or '')
    print('错误码特征  =', code)
    print('=' * 68)


TS = str(int(time.time()))
U = 'day24probe-' + TS          # 本次专用的 user_id，避免污染真实收藏

print('Day 24 复现：外键违规到底回什么码？')
print('user_id =', U, '（本次临时用户，用完清理）')

# ---------- 找一个真实存在的 work_id，做「唯一冲突」对照组 ----------
st, exists_works = req('GET', 'works', {'select': 'work_id', 'limit': '1'})
if st != 200 or not isinstance(exists_works, list) or not exists_works:
    print('[FATAL] 取 works 失败：', st, exists_works)
    sys.exit(2)
REAL_WORK = exists_works[0]['work_id']
print('对照组用的真实 work_id =', REAL_WORK)

# ============ A. 唯一冲突（23505）============
st1, d1 = req('POST', 'favorites',
              query={'select': 'id'},
              body={'user_id': U, 'work_id': REAL_WORK, 'note': 'A-唯一冲突对照'},
              prefer='return=representation')
show('【A】第一次插入真实作品（应 201 成功）', st1, d1)

st2, d2 = req('POST', 'favorites',
              query={'select': 'id'},
              body={'user_id': U, 'work_id': REAL_WORK, 'note': 'A-唯一冲突对照'},
              prefer='return=representation')
show('【A】再插一次同一 (user, work) —— 唯一冲突', st2, d2)

# ============ B. 外键违规（23503）—— 核心！============
FAKE_WORK = 'music-999999'   # 格式合法（板块-编号），但库里不存在
st3, d3 = req('POST', 'favorites',
              query={'select': 'id'},
              body={'user_id': U, 'work_id': FAKE_WORK, 'note': 'B-外键违规'},
              prefer='return=representation')
show('【B】work_id 指向不存在的作品 —— 外键违规', st3, d3)

# ============ C. 用现有 isUniqueViolation 逻辑判定 ============
def isUniqueViolation(status, data):
    """完全复制 deploy/db/rest.js 第 78-82 行的逻辑。"""
    if status == 409:
        return True
    if isinstance(data, dict) and '23505' in str(data.get('code', '')):
        return True
    return False

print('')
print('#' * 68)
print('# 用当前 isUniqueViolation() 判定上面三个响应：')
print('#' * 68)
for tag, st, d in (('A-唯一冲突', st2, d2), ('B-外键违规', st3, d3)):
    verd = isUniqueViolation(st, d)
    print('  %-12s status=%-4s → isUniqueViolation=%s  %s'
          % (tag, st, verd, '❌ 误判！' if (tag.startswith('B') and verd) else ''))

print('')
print('结论：若 B 的状态码也是 409，则外键违规会被 isUniqueViolation 误判为「重复收藏」。')

# ---------- 清理：删掉本次插入的 A 组数据 ----------
stc, dc = req('DELETE', 'favorites', {'user_id': 'eq.' + U})
print('')
print('清理本次临时数据 user_id=%s → HTTP %s' % (U, stc))
