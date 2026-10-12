# -*- coding: utf-8 -*-
"""
Day 21 路线B：SQL 语法自检 + 条数核对。
用 sqlglot 把每个 chunk 解析成 Postgres AST，任何语法错立刻暴露。
用法: python docs/day21/sql/verify_sql.py
"""
import os
import re
import sys

import sqlglot

BASE = os.path.dirname(os.path.abspath(__file__))
CHUNKS = os.path.join(BASE, 'chunks')

files = sorted(os.listdir(CHUNKS))
total_rows = {'categories': 0, 'games': 0, 'characters': 0, 'originals': 0}
bad = []

print('%-26s %-8s %s' % ('文件', '语句数', '解析结果'))
print('-' * 60)

for fn in files:
    path = os.path.join(CHUNKS, fn)
    with open(path, encoding='utf-8') as f:
        sql = f.read()
    # 去掉纯注释行后按分号切
    stmts = [s.strip() for s in re.split(r';\s*\n', sql) if s.strip()]
    stmts = [s for s in stmts if re.search(r'(CREATE|INSERT|SELECT)', s, re.I)]
    ok = 0
    for s in stmts:
        try:
            sqlglot.parse_one(s, read='postgres')
            ok += 1
        except Exception as e:
            bad.append((fn, str(e)[:90]))
    print('%-26s %-8d %s' % (fn, ok, 'OK' if ok == len(stmts) else 'FAIL'))

    # 统计条数
    n = sql.count("'),\n(") + (1 if 'INSERT INTO' in sql else 0)
    if 'og-categories' in fn:
        total_rows['categories'] += sql.count('(') - 1
    elif 'original-games' in fn:
        total_rows['games'] += sql.count("'),\n(") + (0 if 'ON CONFLICT' not in sql else 1)
    elif 'characters' in fn:
        total_rows['characters'] += sql.count("'),\n(") + (0 if 'ON CONFLICT' not in sql else 1)
    elif 'originals' in fn:
        total_rows['originals'] += sql.count("'),\n(") + (0 if 'ON CONFLICT' not in sql else 1)

print()
if bad:
    print('!!! 语法错误 %d 处：' % len(bad))
    for fn, e in bad:
        print('   %s: %s' % (fn, e))
    sys.exit(1)
else:
    print('语法自检：全部通过 ✓')

print()
print('=== 数据条数核对（按 INSERT 行的括号对统计）===')
# 更可靠的条数统计：数每个 INSERT 语句里的 value 元组
expect = {'og-categories': 5, 'original-games': 39, 'characters': 112, 'originals': 6}
for key, exp in expect.items():
    cnt = 0
    for fn in files:
        if key not in fn:
            continue
        with open(os.path.join(CHUNKS, fn), encoding='utf-8') as f:
            sql = f.read()
        # 每条 value 元组都以 "),\n" 结尾（最后一条以 ")\nON CONFLICT" 结束）
        cnt += sql.count("),\n(") + (sql.count('\nON CONFLICT') if 'ON CONFLICT' in sql else 0)
    flag = 'OK' if cnt == exp else '!! 期望 %d，实际 %d' % (exp, cnt)
    print('  %-18s %4d  %s' % (key, cnt, flag))
