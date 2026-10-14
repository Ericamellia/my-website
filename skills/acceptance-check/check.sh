#!/usr/bin/env bash
# ============================================================================
# 结营验收体检 · acceptance-check
#
# 把 Day 28 验收清单（docs/day28/acceptance.md）的 A~E 五类检查打包成一个脚本，
# 跑一次给出总分。用于：
#   - 每次发布后快速复验
#   - 改动后端接口后回归
#   - 下次结营 / 交接时一键体检
#
# 用法：
#   bash skills/acceptance-check/check.sh                # 完整（含公网）
#   bash skills/acceptance-check/check.sh --skip-write   # 跳过写库测试（只读）
#   SITE=https://你的域名 bash skills/acceptance-check/check.sh
#
# 退出码：0 = 全过；1 = 有项失败
#
# ★ 写库测试默认**会写一条再删掉**，保证不污染真库基线。
#   若真库不可用或不想写，加 --skip-write。
# ============================================================================
set -u

SITE="${SITE:-https://touhou-mock.app.workbuddy.host}"
SKIP_WRITE=0
for a in "$@"; do
  case "$a" in
    --skip-write) SKIP_WRITE=1 ;;
    --offline)    SITE="" ;;
  esac
done

PASS=0
FAIL=0
WARN=0

# ★ 清理兜底：本脚本会往真库写一条测试数据，任何退出路径都必须把它删掉。
#   否则真库会攒下脏数据（Day 28 就踩过：残留了一条 id=87）。
CLEANUP_IDS=""
cleanup() {
  if [ -n "$CLEANUP_IDS" ] && [ -n "$SITE" ]; then
    for cid in $CLEANUP_IDS; do
      c -o /dev/null -X DELETE "$SITE/api/favorites/$cid" 2>/dev/null
    done
    echo "  [清理] 已删除测试数据 id: $CLEANUP_IDS"
  fi
}
trap cleanup EXIT INT TERM

green() { printf '\033[32m%s\033[0m' "$1"; }
red()   { printf '\033[31m%s\033[0m' "$1"; }
yell()  { printf '\033[33m%s\033[0m' "$1"; }

ok()   { PASS=$((PASS+1)); printf '  [%s] %s\n' "$(green PASS)" "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  [%s] %s\n' "$(red FAIL)" "$1"; }
warn() { WARN=$((WARN+1)); printf '  [%s] %s\n' "$(yell WARN)" "$1"; }

# curl 包装：清掉代理（本机代理会劫持请求）
c() {
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
    curl -s --max-time 25 "$@"
}

echo "============================================================"
echo "结营验收体检 · acceptance-check"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
[ -n "$SITE" ] && echo "站点：$SITE" || echo "站点：（跳过公网检查）"
echo "============================================================"

# ---------------------------------------------------------------- A 公网可访问
echo
echo "---- A 类 · 公网可访问 ----"
if [ -z "$SITE" ]; then
  warn "A 类已跳过（--offline）"
else
  code=$(c -o /dev/null -w '%{http_code}' "$SITE/")
  [ "$code" = "200" ] && ok "A1 首页可打开（HTTP $code）" || bad "A1 首页异常（HTTP $code）"

  for asset in style.css app.js; do
    code=$(c -o /dev/null -w '%{http_code}' "$SITE/$asset")
    [ "$code" = "200" ] && ok "A2 $asset 可加载（HTTP $code）" || bad "A2 $asset 异常（HTTP $code）"
  done

  h=$(c "$SITE/api/health")
  if echo "$h" | grep -q '"ok": *true'; then
    ds=$(echo "$h" | grep -o '"dataSource": *"[a-z]*"' | head -1)
    ok "A3 /api/health ok:true（$ds）"
    echo "$h" | grep -q '"rest"' && ok "A4 数据源为 rest 真库" || warn "A4 数据源不是 rest（当前为快照兜底？）"
  else
    bad "A3 /api/health 异常"
  fi

  for p in "/api/hot?board=fresh&limit=1" "/api/favorites?limit=1" \
           "/api/works?category=music&limit=1" "/api/circles" "/api/originals"; do
    code=$(c -o /dev/null -w '%{http_code}' "$SITE$p")
    [ "$code" = "200" ] && ok "A5 $p（HTTP $code）" || bad "A5 $p（HTTP $code）"
  done
fi

# ---------------------------------------------------------------- B 真实读写
echo
echo "---- B 类 · 真实读写 + 持久化 ----"
if [ -z "$SITE" ]; then
  warn "B 类已跳过（--offline）"
elif [ "$SKIP_WRITE" = "1" ]; then
  r=$(c "$SITE/api/favorites?limit=50")
  cnt=$(echo "$r" | grep -o '"count": *[0-9]*' | head -1 | grep -o '[0-9]*')
  echo "$r" | grep -q '"rest"' && ok "B1 读收藏列表 200，source=rest（count=$cnt）" || bad "B1 读收藏异常"
  warn "B2~B7 写库测试已跳过（--skip-write）"
else
  # B1 读基线
  r=$(c "$SITE/api/favorites?limit=50")
  base=$(echo "$r" | grep -o '"count": *[0-9]*' | head -1 | grep -o '[0-9]*')
  echo "$r" | grep -q '"rest"' && ok "B1 读收藏列表（count=$base，source=rest）" || bad "B1 读收藏异常"

  # B2 写入
  # ★ 踩坑（Day 28 自己踩的）：一开始写成「发两次 POST」——
  #   一次拿 body、一次拿状态码。结果两次都写成功了，清理时只删掉第一条，
  #   真库残留一条脏数据。正确做法：**只发一次**，用 -w 把状态码和 body 一起拿回来。
  RESP=$(c -w $'\n__CODE__%{http_code}' -X POST "$SITE/api/favorites" \
        -H 'Content-Type: application/json' \
        -d '{"workId":"art-2","note":"acceptance-check 探针"}')
  wcode=$(printf '%s' "$RESP" | sed -n 's/.*__CODE__\([0-9]*\)$/\1/p')
  w=$(printf '%s' "$RESP" | sed 's/__CODE__[0-9]*$//')
  newid=$(echo "$w" | grep -o '"id": *[0-9]*' | head -1 | grep -o '[0-9]*')
  # 立刻登记，交给 trap 兜底（即使后面崩了也会被删掉）
  [ -n "$newid" ] && CLEANUP_IDS="$CLEANUP_IDS $newid"

  if [ "$wcode" = "201" ] || [ "$wcode" = "200" ]; then
    ok "B2 写入收藏（HTTP $wcode，新行 id=$newid）"
  elif [ "$wcode" = "409" ]; then
    # 说明 art-2 已存在 → 换个候选，或直接用 409 本身验防重复
    warn "B2 art-2 已被收藏（409）→ 跳过写入，改用 409 验证防重复闸门"
    ok "B6 防重复闸门有效（HTTP 409）"
    newid=""
  else
    bad "B2 写入收藏异常（HTTP $wcode）"
    newid=""
  fi

  # B3/B4 写后读 + 持久化
  if [ -n "$newid" ]; then
    after=$(c "$SITE/api/favorites?limit=50")
    ac=$(echo "$after" | grep -o '"count": *[0-9]*' | head -1 | grep -o '[0-9]*')
    [ "$ac" = "$((base+1))" ] && ok "B3 写后计数 +1（$base → $ac）" || bad "B3 计数异常（$base → $ac）"

    sleep 4
    later=$(c "$SITE/api/favorites?limit=50")
    lc=$(echo "$later" | grep -o '"count": *[0-9]*' | head -1 | grep -o '[0-9]*')
    [ "$lc" = "$ac" ] && ok "B4 持久化复核（4 秒后 count 仍为 $lc）" || bad "B4 持久化异常（$lc）"

    # B6 防重复
    dcode=$(c -o /dev/null -w '%{http_code}' -X POST "$SITE/api/favorites" \
            -H 'Content-Type: application/json' -d '{"workId":"art-2"}')
    [ "$dcode" = "409" ] && ok "B6 防重复闸门（HTTP 409）" || bad "B6 防重复异常（HTTP $dcode）"

    # B7 清理
    dc=$(c -o /dev/null -w '%{http_code}' -X DELETE "$SITE/api/favorites/$newid")
    fin=$(c "$SITE/api/favorites?limit=50")
    fc=$(echo "$fin" | grep -o '"count": *[0-9]*' | head -1 | grep -o '[0-9]*')
    if [ "$fc" = "$base" ]; then
      ok "B7 清理恢复基线（DELETE $dc，count 回到 $base）"
    else
      bad "B7 清理异常（count=$fc，基线=$base）—— 可能残留测试数据 id=$newid"
    fi
  fi
fi

# ---------------------------------------------------------------- C 契约与错误
echo
echo "---- C 类 · 接口契约与错误处理 ----"
if [ -z "$SITE" ]; then
  warn "C 类已跳过（--offline）"
else
  code=$(c -o /dev/null -w '%{http_code}' -X PATCH "$SITE/api/favorites")
  [ "$code" = "405" ] && ok "C1 方法不匹配 → 405" || bad "C1 期望 405，实为 $code"

  code=$(c -o /dev/null -w '%{http_code}' "$SITE/api/nonexistent-xyz")
  [ "$code" = "501" ] && ok "C2 不存在路径 → 501" || bad "C2 期望 501，实为 $code"

  code=$(c -o /dev/null -w '%{http_code}' -X POST "$SITE/api/favorites" \
         -H 'Content-Type: application/json' -d '{}')
  [ "$code" = "400" ] && ok "C3 缺必填字段 → 400" || bad "C3 期望 400，实为 $code"

  code=$(c -o /dev/null -w '%{http_code}' -X POST "$SITE/api/favorites" \
         -H 'Content-Type: application/json' -d '{"workId":"!!!bad!!!"}')
  [ "$code" = "400" ] && ok "C4 格式非法 → 400" || bad "C4 期望 400，实为 $code"

  leak=0
  for p in "/api/nonexistent-xyz" "/api/favorites?limit=99999" "/api/works?category=__bad__"; do
    n=$(c "$SITE$p" | grep -ciE 'at .*\.js:|postgres://|postgrest.*://|password|stack|ECONNREFUSED')
    leak=$((leak+n))
  done
  [ "$leak" = "0" ] && ok "C5 错误响应不漏内部细节（命中 0）" || bad "C5 错误响应疑似漏细节（命中 $leak）"

  code=$(c -o /dev/null -w '%{http_code}' -X DELETE "$SITE/api/favorites/99999999")
  [ "$code" = "404" ] && ok "C6 DELETE 幂等（不存在的 id → 404）" || warn "C6 期望 404，实为 $code"

  # C7：405 是否带 Allow 头
  allow=$(c -i -X PATCH "$SITE/api/favorites" | grep -i '^allow:' | head -1)
  if [ -n "$allow" ]; then
    ok "C7 405 带 Allow 头"
  else
    warn "C7 405 未带 Allow 响应头（allow 在 JSON body 里；RFC 7231 要求响应头）"
  fi
fi

# ---------------------------------------------------------------- D 本地交付物
echo
echo "---- D 类 · 本地交付物与 Skill ----"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

for f in README.md PRD.md TECH_DESIGN.md RUN.md AGENTS.md \
         docs/api-contract.md docs/rollback.md \
         skills/preflight-check/SKILL.md skills/preflight-check/check.sh \
         skills/filter-interaction-check/SKILL.md; do
  [ -f "$ROOT/$f" ] && ok "D 交付物存在：$f" || bad "D 交付物缺失：$f"
done

# 版本号一致性（本地 vs 线上）
if [ -n "$SITE" ]; then
  local_v=$(grep -oE 'app\.js\?v=[0-9]+' "$ROOT/deploy/public/index.html" | grep -o '[0-9]*$' | head -1)
  online_v=$(c "$SITE/" | grep -oE 'app\.js\?v=[0-9]+' | grep -o '[0-9]*$' | head -1)
  if [ -n "$local_v" ] && [ -n "$online_v" ]; then
    if [ "$local_v" = "$online_v" ]; then
      ok "D 前端版本号已同步（app.js v$local_v）"
    else
      warn "D 线上版本落后：本地 v$local_v vs 线上 v$online_v（未部署）"
    fi
  fi
fi

# ---------------------------------------------------------------- 汇总
echo
echo "============================================================"
echo "汇总：$(green "通过 $PASS")   $(red "失败 $FAIL")   $(yell "提醒 $WARN")"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
  echo ">>> $(red '有检查项失败')"
  exit 1
fi
echo ">>> $(green '全部通过')"
exit 0
