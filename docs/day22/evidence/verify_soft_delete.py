# -*- coding: utf-8 -*-
"""
Day 22 余力加练 · 证据脚本 —— 软删除验证（is_deleted 打标记）
--------------------------------------------------------------------------------
跑法：
    python verify_soft_delete.py [BASE_URL] [--keep]
    默认 BASE_URL = http://127.0.0.1:3000/

它证明三件事，缺一不可：

  ① 软删除**真的让记录从读接口消失**
     DELETE 之后 GET 列表里必须看不到它 —— 这是"软删"对用户可见的全部效果。
     如果只打了标记但忘了加过滤，用户会看到"删了还在"，这是软删除最典型的翻车。

  ② 「删后重新收藏同一作品」**不会撞唯一约束**（软删除最关键的坑）
     老的全表唯一约束 UNIQUE(user_id, work_id) 会在软删后继续占位，
     导致重新收藏报 409。必须换成部分唯一索引 ... WHERE is_deleted = FALSE 才行。
     这一步如果没做对，现象是"我明明删了，怎么还说我收藏过"。

  ③ 重新收藏 = **复活旧行**（而不是插一条新行）
     脚本会核对：新收藏能成功、能出现在列表里，且总数只 +1。

附带验两个边界：
  · 二次 DELETE 同一个 id → 404（软删行视同不存在，幂等语义保持）
  · PATCH 已软删的行 → 404（已删的行对用户来说"不存在"，不该还能改）

安全约定（延续 verify_crud_cycle.py）：
  · 测试数据自己造、自己删，跑完库里与跑之前逐条一致（末尾对比快照）
  · 用专用测试作品 art-5，不碰任何真实收藏
  · 不传 --keep 时，即使中途失败也尽力清理
"""
import json
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:3000/'
KEEP = '--keep' in sys.argv
USER = 'local'          # 与线上服务默认一致
WORK = 'art-5'          # 专用测试作品，避开真实数据

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


def req(method, path, body=None):
    """返回 (status, json_body)。4xx/5xx 不当异常抛，交给断言判断。"""
    url = BASE.rstrip('/') + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read().decode('utf-8')
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def list_ids():
    st, body = req('GET', '/api/favorites?userId=' + USER + '&limit=50')
    if st != 200 or not isinstance(body, dict):
        return None
    return [x.get('id') for x in (body.get('items') or [])]


def main():
    global PASS, FAIL
    print('=== 软删除验证（Day 22 余力加练）===')
    print('BASE = ' + BASE)
    print('测试作品 = %s   用户 = %s\n' % (WORK, USER))

    before = list_ids()
    if before is None:
        print('[ABORT] GET /api/favorites 拿不到列表，服务没起来或接口异常。')
        sys.exit(2)
    print('起始：共 %d 条\n' % len(before))

    created_id = None
    revived_id = None
    try:
        # --- 1) 新增一条作为素材 ---
        print('【1】POST 新增一条测试收藏')
        st, body = req('POST', '/api/favorites',
                       {'userId': USER, 'workId': WORK, 'note': '软删测试'})
        ck('新增返回 201', st == 201, 'status=%s body=%s' % (st, json.dumps(body, ensure_ascii=False)[:200]))
        created_id = (body or {}).get('item', {}).get('id') if isinstance(body, dict) else None
        ck('返回了新记录 id', created_id is not None, json.dumps(body, ensure_ascii=False)[:200])
        print('    → id = %s' % created_id)

        # --- 2) GET 能看到 ---
        print('\n【2】GET 列表应包含它')
        ids = list_ids()
        ck('列表里能看到', ids is not None and created_id in ids, 'ids=%s' % ids)
        ck('总数 = 起始 + 1', ids is not None and len(ids) == len(before) + 1,
           '%s vs %s' % (len(ids) if ids else None, len(before) + 1))

        # --- 3) DELETE 软删 ---
        print('\n【3】DELETE 软删除（打 is_deleted 标记）')
        st, body = req('DELETE', '/api/favorites/%s' % created_id)
        ck('返回 200', st == 200, 'status=%s' % st)
        item = (body or {}).get('item') if isinstance(body, dict) else None
        ck('响应回传被删数据（凭证）', bool(item and item.get('workId') == WORK),
           json.dumps(body, ensure_ascii=False)[:220])

        # --- 4) ★ 核心：GET 里必须消失 ---
        print('\n【4】★ GET 列表里应消失（软删对用户可见的效果）')
        ids = list_ids()
        ck('列表里已看不到', ids is not None and created_id not in ids, 'ids=%s' % ids)
        ck('总数回到起始值', ids is not None and len(ids) == len(before),
           '%s vs %s' % (len(ids) if ids else None, len(before)))

        # --- 5) 二次删 → 404（幂等） ---
        print('\n【5】二次 DELETE 同一 id → 应 404（软删行视同不存在）')
        st, body = req('DELETE', '/api/favorites/%s' % created_id)
        ck('二次删返回 404', st == 404, 'status=%s' % st)
        ck('错误码 favorite_not_found',
           isinstance(body, dict) and body.get('error') == 'favorite_not_found',
           json.dumps(body, ensure_ascii=False)[:200])

        # --- 6) ★★ 最关键：重新收藏同一作品，不能撞唯一约束 ---
        print('\n【6】★★ 重新收藏同一作品（软删除最关键的坑）')
        st, body = req('POST', '/api/favorites',
                       {'userId': USER, 'workId': WORK, 'note': '复活测试'})
        ck('重新收藏成功（没撞 409）', st == 201,
           'status=%s body=%s' % (st, json.dumps(body, ensure_ascii=False)[:220]))
        revived_id = (body or {}).get('item', {}).get('id') if isinstance(body, dict) else None
        print('    → 新 id = %s（原 id = %s）' % (revived_id, created_id))

        # --- 7) GET 又能看到 ---
        print('\n【7】GET 列表应重新出现')
        ids = list_ids()
        ck('列表里又能看到', ids is not None and revived_id in ids, 'ids=%s' % ids)
        ck('总数 = 起始 + 1', ids is not None and len(ids) == len(before) + 1,
           '%s vs %s' % (len(ids) if ids else None, len(before) + 1))

        # --- 8) PATCH 已软删的行 → 404 ---
        print('\n【8】PATCH 已软删的旧行 → 应 404')
        st, body = req('PATCH', '/api/favorites/%s' % created_id,
                       {'note': '试图改已删的'})
        ck('改已软删的行返回 404', st == 404,
           'status=%s body=%s' % (st, json.dumps(body, ensure_ascii=False)[:200]))

    finally:
        # --- 9) 清理 ---
        print('\n【9】清理测试数据')
        if revived_id is not None:
            req('DELETE', '/api/favorites/%s' % revived_id)
        elif created_id is not None:
            req('DELETE', '/api/favorites/%s' % created_id)

        after = list_ids()
        if after is not None:
            extra = [i for i in after if i not in before]
            missing = [i for i in before if i not in after]
            ck('库里没多出记录', not extra, 'extra=%s' % extra)
            ck('库里没少记录', not missing, 'missing=%s' % missing)

    print('\n=== 结果：%d 通过 / %d 失败 ===' % (PASS, FAIL))
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == '__main__':
    main()
