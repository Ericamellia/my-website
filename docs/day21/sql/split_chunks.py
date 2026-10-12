# -*- coding: utf-8 -*-
"""
Day 21 路线B：把种子 SQL 拆成「一块一个文件」，方便控制台逐块粘贴。
产出 docs/day21/sql/chunks/  下形如：
  01-schema.sql
  02-og-categories.sql
  03-original-games-1.sql ... 03-original-games-4.sql
  04-characters-1.sql   ... 04-characters-12.sql
  05-originals-1.sql
"""
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
CHUNKS = os.path.join(BASE, 'chunks')
os.makedirs(CHUNKS, exist_ok=True)
for f in os.listdir(CHUNKS):
    os.remove(os.path.join(CHUNKS, f))


def split_inserts(path):
    """把一个 seed 文件按 '-- 块 N' 切成若干段，返回 [(label, sql)]。"""
    with open(path, encoding='utf-8') as f:
        content = f.read()
    parts = re.split(r'\n(?=-- 块 \d+)', content)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 跳过只有注释、没有实际 INSERT 的段落
        if 'INSERT INTO' not in p:
            continue
        m = re.search(r'-- 块 (\d+)（(\d+) 条）', p)
        label = 'chunk%s' % m.group(1) if m else 'part'
        out.append((label, p + '\n'))
    return out


manifest = []

# 01 schema
with open(os.path.join(BASE, 'schema.sql'), encoding='utf-8') as f:
    s = f.read()
open(os.path.join(CHUNKS, '01-schema.sql'), 'w', encoding='utf-8').write(s)
manifest.append(('01-schema.sql', '建 4 张表', len(s)))

# 02 categories
with open(os.path.join(BASE, 'seed-og-categories.sql'), encoding='utf-8') as f:
    s = f.read()
open(os.path.join(CHUNKS, '02-og-categories.sql'), 'w', encoding='utf-8').write(s)
manifest.append(('02-og-categories.sql', '原作分类 5 条', len(s)))

# 03 original_games
for i, (label, sql) in enumerate(split_inserts(os.path.join(BASE, 'seed-original-games.sql')), 1):
    fn = '03-original-games-%d.sql' % i
    open(os.path.join(CHUNKS, fn), 'w', encoding='utf-8').write(sql)
    manifest.append((fn, '原作作品（%s）' % label, len(sql)))

# 04 characters
for i, (label, sql) in enumerate(split_inserts(os.path.join(BASE, 'seed-characters.sql')), 1):
    fn = '04-characters-%d.sql' % i
    open(os.path.join(CHUNKS, fn), 'w', encoding='utf-8').write(sql)
    manifest.append((fn, '角色（%s）' % label, len(sql)))

# 05 originals
for i, (label, sql) in enumerate(split_inserts(os.path.join(BASE, 'seed-originals.sql')), 1):
    fn = '05-originals-%d.sql' % i
    open(os.path.join(CHUNKS, fn), 'w', encoding='utf-8').write(sql)
    manifest.append((fn, '原曲（%s）' % label, len(sql)))

print('拆分为 %d 个文件 → docs/day21/sql/chunks/\n' % len(manifest))
print('%-26s %-22s %s' % ('文件名', '内容', '大小'))
print('-' * 62)
for fn, desc, size in manifest:
    print('%-26s %-22s %d bytes' % (fn, desc, size))
print()
print('最大单块 = %d bytes（控制在 6KB 内，防控制台截断）'
      % max(m[2] for m in manifest))
