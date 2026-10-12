# -*- coding: utf-8 -*-
"""
Day 22 证据脚本 · 四类操作闭环验证（增 POST / 查 GET / 改 PATCH / 删 DELETE）
--------------------------------------------------------------------------------
跑法：
    python verify_crud_cycle.py [BASE_URL] [--keep]
    默认 BASE_URL = http://127.0.0.1:3000/

这个脚本证明的是**闭环**，不是四个孤立接口：
    ① POST   新增一条          → 记下 id
    ② GET    查得到这条        → 证明「增」真的落库了
    ③ PATCH  改这条的备注       → 值 A → 值 B，再 GET 确认库里改成 B
    ④ DELETE 删这条            → 响应里带回被删数据
    ⑤ GET    再也查不到这条     → 证明「删」在库里真的生效了

断言设计上的两个讲究：
  · 每一步都要**重新 GET 一次**，不能只看接口自己的返回 ——
    接口返回是「它说它做了什么」，GET 是「库里实际是什么」，两者必须一致。
  · 测试用的那条**自己造、自己删**，跑完库里的数据与跑之前逐条一致
    （脚本末尾会对比「跑前快照」和「跑后快照」，多一条少一条都算失败）。
    没加 --keep 时，即使中途失败也会尽力清理掉测试数据。
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = 'http://127.0.0.1:3000/'
KEEP = '--keep' in sys.argv

args = [a for a in sys.argv[1:] if not a.startswith('--')]
if args:
    BASE = args[0]
if not BASE.endswith('/'):
    BASE += '/'

PASS, FAIL = [], []


def req(method, path, body=None):
    """发一个请求，返回 (status, data)。data 是解析后的 JSON（解析失败给 None）。"""
    url = BASE.rstrip('/') + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            txt = resp.read().decode('utf-8')
            status = resp.status
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8')
        status = e.code
    try:
        return status, json.loads(txt)
    except Exception:
        return status, None


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    mark = 'PASS' if cond else 'FAIL'
    print('  [%s] %s%s' % (mark, name, ('  → ' + detail) if detail else ''))


def list_favs(limit=200):
    """读全部收藏（用大 limit 保证不漏）。返回 (count, data[])。"""
    st, j = req('GET', '/api/favorites?limit=%d' % limit)
    if st != 200 or not j or not isinstance(j.get('data'), list):
        return None, []
    return j.get('count'), j['data']


def find(items, fav_id):
    for it in items:
        if int(it.get('id')) == int(fav_id):
            return it
    return None


def snap_ids(items):
    """把列表压成「id:note」集合，用来对比跑前跑后有没有被意外改动。"""
    return sorted('%s:%s' % (it.get('id'), it.get('note')) for it in items)


TS = datetime.now().strftime('%H:%M:%S')
print('=' * 74)
print('Day 22 · 四类操作闭环验证（POST → GET → PATCH → DELETE → GET）')
print('目标服务: %s' % BASE)
print('时间: %s' % TS)
print('=' * 74)

# ---------------------------------------------------------------- 0. 前置
st, health = req('GET', '/api/health')
check('0. 服务在线（GET /api/health → 200 + ok:true）',
      st == 200 and health and health.get('ok') is True,
      'HTTP %s · 数据源=%s' % (st, (health or {}).get('checks', {}).get('dataSource')))

before_count, before_items = list_favs()
check('0. 跑之前先把库里的收藏读一份（作为「跑完要还原」的基准）',
      before_count is not None,
      '跑前 %s 条，ids=%s' % (before_count, ','.join(str(i.get('id')) for i in before_items)))
before_ids = snap_ids(before_items)

test_id = None   # 测试记录 id，收尾时用来清理

try:
    # ------------------------------------------------------------ ① 增
    print('\n--- ① 增：POST /api/favorites ------------------------------------------')
    st, post = req('POST', '/api/favorites', {
        'workId': 'art-2',
        'note': 'Day22 闭环验证 · 原始备注'
    })
    ok = st == 201 and post and post.get('ok') is True and post.get('action') == 'created'
    check('① POST 新增一条 → 201 created', ok,
          'HTTP %s · id=%s' % (st, (post or {}).get('data', {}).get('id')))
    if ok:
        test_id = int(post['data']['id'])
    
    # 万一 art-2 之前已被收藏（409），退而求其次：拿已有那条来跑后面几步
    if st == 409:
        st2, j2 = req('GET', '/api/favorites?limit=200')
        existing = find((j2 or {}).get('data') or [], 
                        (post or {}).get('data', {}).get('id')) if post else None
        if existing:
            test_id = int(existing['id'])
            print('  （art-2 已被收藏过，改用已有记录 id=%d 继续验证）' % test_id)

    # ------------------------------------------------------------ ② 查
    print('\n--- ② 查：GET /api/favorites -----------------------------------------')
    count2, items2 = list_favs()
    hit = find(items2, test_id) if test_id else None
    check('② 新增的那条能在 GET 列表里查到（证明真的落库了）',
          hit is not None,
          '库里 %s 条' % count2)
    if hit:
        check('② 查到的 workId 与新增时一致',
              hit.get('workId') == (post or {}).get('data', {}).get('workId'),
              'workId=%s' % hit.get('workId'))

    # ------------------------------------------------------------ ③ 改
    print('\n--- ③ 改：PATCH /api/favorites/:id -----------------------------------')
    old_note = hit.get('note') if hit else None
    new_note = 'Day22 闭环验证 · 备注已改（%s）' % TS
    st, pat = req('PATCH', '/api/favorites/%s' % test_id, {'note': new_note})
    ok = st == 200 and pat and pat.get('action') == 'updated'
    check('③ PATCH 改备注 → 200 updated', ok,
          'HTTP %s · 改前=%r 改后=%r' % (st, old_note, (pat or {}).get('data', {}).get('note')))

    # ★ 关键：不能只信 PATCH 自己的返回，要 GET 出来对
    count3, items3 = list_favs()
    hit3 = find(items3, test_id)
    check('③ 再 GET 确认库里真的变成了新值（改前 ≠ 改后）',
          hit3 is not None and hit3.get('note') == new_note and old_note != new_note,
          'GET 读到 = %r' % (hit3 or {}).get('note'))
    check('③ 改备注不该动到其他字段（createdAt 保持原值）',
          hit3 is not None and hit.get('createdAt') == hit3.get('createdAt'),
          'createdAt=%s' % (hit3 or {}).get('createdAt'))

    # ------------------------------------------------------------ ④ 删
    print('\n--- ④ 删：DELETE /api/favorites/:id ----------------------------------')
    st, dele = req('DELETE', '/api/favorites/%s' % test_id)
    ok = st == 200 and dele and dele.get('action') == 'deleted'
    check('④ DELETE → 200 deleted', ok, 'HTTP %s' % st)
    check('④ 响应里把「被删的那条」原样带回（误删后唯一的凭证）',
          bool(dele and dele.get('data') and int(dele['data'].get('id', 0)) == int(test_id)),
          '带回 workId=%s note=%r' % ((dele or {}).get('data', {}).get('workId'),
                                      (dele or {}).get('data', {}).get('note')))

    # ------------------------------------------------------------ ⑤ 再查
    print('\n--- ⑤ 再查：GET 里该条必须消失 ---------------------------------------')
    count5, items5 = list_favs()
    check('⑤ 删除后 GET 不再返回该条（库里真的没了）',
          find(items5, test_id) is None,
          '库里 %s 条' % count5)
    check('⑤ 总数比删除前少 1（%s → %s）' % (count3, count5),
          count5 == count3 - 1,
          '%s → %s' % (count3, count5))

    # ------------------------------------------------------------ ⑥ 幂等/边界
    print('\n--- ⑥ 边界：删过的 id 再删一次 ---------------------------------------')
    st, again = req('DELETE', '/api/favorites/%s' % test_id)
    check('⑥ 再删一次同一 id → 404（幂等：不会假装成功，也不会 500）',
          st == 404 and (again or {}).get('error') == 'favorite_not_found',
          'HTTP %s · %s' % (st, (again or {}).get('error')))

finally:
    # ------------------------------------------------------------ 收尾还原
    print('\n--- 收尾：还原数据库 -------------------------------------------------')
    if test_id is not None:
        st, _ = req('DELETE', '/api/favorites/%s' % test_id)
        print('  清理测试记录 id=%s → HTTP %s%s' % (test_id, st, '（本就已删）' if st == 404 else ''))

    after_count, after_items = list_favs()
    after_ids = snap_ids(after_items)
    check('★ 跑完与跑前完全一致（不多一条、不少一条、没改动任何备注）',
          after_ids == before_ids,
          '跑前 %s 条 → 跑后 %s 条' % (before_count, after_count))

# ---------------------------------------------------------------- 汇总
print('\n' + '=' * 74)
print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - ' + f)
print('=' * 74)
sys.exit(1 if FAIL else 0)
