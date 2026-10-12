#!/bin/bash
# Day 21 周验收：完整重跑一次「公网可访问 + 真实读写」证据采集，输出干净日志。
# 用法: bash docs/day21/evidence/run_verify.sh
set -u
cd "$(dirname "$0")/../../.." || exit 1

PY="C:/Users/25394/.workbuddy/binaries/python/versions/3.13.12/python.exe"
OUT="docs/day21/evidence/week3-verify.txt"
BASE="https://touhou-mock.app.workbuddy.host"
FN="https://ericamellia24-d2gk0ftukc71292c5.service.tcloudbase.com/api/health"

{
echo "==== 采集时间：$(date '+%Y-%m-%d %H:%M:%S') ===="
echo "==== 站点：$BASE ===="
echo ""
echo "===== [1] 公网首页可访问 ====="
curl -s -o /dev/null -w "GET /  ->  HTTP %{http_code}  (%{time_total}s)\n" --noproxy '*' "$BASE/"
echo ""
echo "===== [2] 云函数公网入口（无需凭证）====="
curl -s -w "\n-> HTTP %{http_code}\n" --noproxy '*' "$FN"
echo ""
echo "===== [3] 真实读：收藏 + 热搜 ====="
curl -s -o docs/day21/evidence/_fav.json -w "GET /api/favorites?limit=20  ->  HTTP %{http_code}\n" --noproxy '*' "$BASE/api/favorites?limit=20"
curl -s -o docs/day21/evidence/_hot.json -w "GET /api/hot?board=fresh&limit=12  ->  HTTP %{http_code}\n" --noproxy '*' "$BASE/api/hot?board=fresh&limit=12"
echo "--- /api/favorites 内容 ---"
"$PY" -c "import json;d=json.load(open('docs/day21/evidence/_fav.json',encoding='utf-8'));print('  source =',d.get('source'),' count =',d.get('count'))"
echo "--- /api/hot 内容 ---"
"$PY" -c "import json;d=json.load(open('docs/day21/evidence/_hot.json',encoding='utf-8'));c=d.get('counts',{});print('  source =',d.get('source'),' counts =',c,' 本条返回条数 =',len(d.get('data',[])))"
echo ""
echo "===== [4] 真实写：POST /api/favorites (art-2) ====="
echo "--- 4.0 先试重复提交（应被闸门挡下）---"
curl -s -X POST -H "Content-Type: application/json" -d '{"workId":"music-1","note":"重复提交测试"}' \
  -w "\nPOST(重复 music-1)  ->  HTTP %{http_code}\n" --noproxy '*' "$BASE/api/favorites"
echo ""
echo "--- 4.1 写入未收藏的 art-2 ---"
curl -s -X POST -H "Content-Type: application/json" -d '{"workId":"art-2","note":"Day21周验收-真实写入验证"}' \
  -w "\nPOST(新 art-2)  ->  HTTP %{http_code}\n" --noproxy '*' "$BASE/api/favorites" | head -30
echo ""
echo "--- 4.2 写后读回（count 应为 8）---"
curl -s --noproxy '*' "$BASE/api/favorites?limit=20" -o docs/day21/evidence/_fav_after.json
"$PY" docs/day21/evidence/check_fav.py docs/day21/evidence/_fav_after.json
NEWID=$("$PY" -c "import json;d=json.load(open('docs/day21/evidence/_fav_after.json',encoding='utf-8'));print([x['id'] for x in d['data'] if (x.get('note') or '').startswith('Day21')][0])")
echo "  (本次新增行 id = $NEWID)"
echo ""
echo "===== [5] 清理测试数据（直连 PostgREST 删除 id=$NEWID）====="
echo "  说明：应用层无 DELETE 接口，实测返回 501（见下方 5.0），故走 service_role 直连。"
echo "--- 5.0 应用层删除接口现状 ---"
curl -s -X DELETE -o /dev/null -w "DELETE /api/favorites/$NEWID  ->  HTTP %{http_code}  (应用层未实现，符合预期)\n" --noproxy '*' "$BASE/api/favorites/$NEWID"
echo "--- 5.1 直连 PostgREST 删除 ---"
"$PY" docs/day21/evidence/cleanup_test_row.py "$NEWID"
echo ""
echo "===== [6] 清理后复核（应恢复 7 条基线）====="
curl -s --noproxy '*' "$BASE/api/favorites?limit=20" -o docs/day21/evidence/_fav_after.json
"$PY" docs/day21/evidence/check_fav.py docs/day21/evidence/_fav_after.json
echo ""
echo "==== 采集结束：$(date '+%Y-%m-%d %H:%M:%S') ===="
} > "$OUT" 2>&1

rm -f docs/day21/evidence/_fav.json docs/day21/evidence/_hot.json docs/day21/evidence/_fav_after.json
echo "已写出：$OUT"
