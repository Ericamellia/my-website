# -*- coding: utf-8 -*-
"""探测 works / circles 两张已有表的真实列名（用 REST 拿 1 条看字段）。"""
import json, urllib.request, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
ENV = {}
with open(os.path.join(ROOT, '.env'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

env_id = ENV.get('CLOUDBASE_ENV_ID')
key = ENV.get('CLOUDBASE_API_KEY')
if not env_id or not key:
    print('缺少 CLOUDBASE_ENV_ID / CLOUDBASE_API_KEY')
    sys.exit(1)

BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env_id


def get(table, select='*', limit=1):
    url = BASE + table + '?select=' + select + '&limit=' + str(limit)
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        body = ''
        if hasattr(e, 'read'):
            try:
                body = e.read().decode('utf-8')[:300]
            except Exception:
                pass
        return {'__error__': str(e), '__body__': body}


for t in ['works', 'circles']:
    print('=' * 60)
    print('表:', t)
    rows = get(t)
    if isinstance(rows, dict) and '__error__' in rows:
        print('  错误:', rows['__error__'])
        print('  body:', rows.get('__body__'))
    elif isinstance(rows, list) and rows:
        print('  列名:', sorted(rows[0].keys()))
        print('  样例:', json.dumps(rows[0], ensure_ascii=False)[:600])
    else:
        print('  返回:', rows)
