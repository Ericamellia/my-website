# -*- coding: utf-8 -*-
"""
Day 21 周验收：用 service_role API Key 直连 CloudBase PostgREST，
删除测试写入的 favorites 行（id=23），恢复 7 条基线。

用法: python cleanup_test_row.py <row_id>
只读取 deploy/.env 的键值，不打印密钥。
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(ROOT, 'deploy', '.env')

row_id = sys.argv[1] if len(sys.argv) > 1 else '23'

env = {}
with open(ENV_PATH, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

env_id = env.get('CLOUDBASE_ENV_ID')
api_key = env.get('CLOUDBASE_API_KEY')
print('env_id  =', env_id)
print('api_key =', ('已读取（%d 字符，不回显）' % len(api_key)) if api_key else '缺失')
if not env_id or not api_key:
    sys.exit('缺少 CLOUDBASE_ENV_ID / CLOUDBASE_API_KEY')

base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/favorites' % env_id

# 清除代理，避免本机代理干扰
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + api_key)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Prefer', 'return=representation')
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# 1. 删前：查这一行是否存在
st, body = call('GET', base + '?id=eq.%s&select=id,work_id,note' % row_id)
print('\n[删前] GET id=%s -> HTTP %s' % (row_id, st))
print('       ', body[:300])

# 2. 删除
st, body = call('DELETE', base + '?id=eq.%s' % row_id)
print('\n[删除] DELETE id=%s -> HTTP %s' % (row_id, st))
print('       ', body[:300])

# 3. 删后：确认整表条数
st, body = call('GET', base + '?select=id&order=id')
print('\n[删后] GET favorites -> HTTP %s' % st)
try:
    rows = json.loads(body)
    print('       剩余条数 =', len(rows), ' ids =', [x['id'] for x in rows])
except Exception:
    print('       ', body[:300])
