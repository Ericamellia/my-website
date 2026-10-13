#!/usr/bin/env bash
# ============================================================================
# 发布前检查 · preflight-check
# ----------------------------------------------------------------------------
# 用途：每次「要发布 / 要推送」之前跑一遍，把上线红线和最容易翻车的地方过一遍。
# 用法：在项目根目录执行
#     bash skills/preflight-check/check.sh                 # 完整检查（含公网）
#     bash skills/preflight-check/check.sh --offline       # 跳过公网检查（没网时）
#     bash skills/preflight-check/check.sh --staged-version   # 额外检查版本号是否已升
#
# 退出码：0 = 全部通过；1 = 有检查项失败（CI 里可直接用来卡发布）
#
# 依赖：git、curl、grep（都是系统自带，无需安装任何东西）
#
# ⚠️ 三个容易写错的地方（都踩过）：
#   1) `$(grep -c ... || echo 0)` 是错的 —— grep 无匹配时退出码 1，
#      `|| echo 0` 会**再输出一个 0**，拼成 "0\n0"，比较永远不等 → 假失败。
#      正确写法见下面 count() 函数。
#   2) `git check-ignore -v .env.example` 即使返回值命中，
#      命中的也可能是 `!` negation 规则（= 没被忽略）。判断要看规则行首是不是 `!`。
#   3) curl 不带 `-m` 超时会**永久挂住**（曾挂过 26 分钟）。所有请求都要带超时。
# ============================================================================
set -u

# 切到项目根（本脚本在 skills/preflight-check/ 下）
cd "$(dirname "$0")/../.." || exit 1

OFFLINE=0
CHECK_VERSION=0
for arg in "$@"; do
  case "$arg" in
    --offline) OFFLINE=1 ;;
    --staged-version) CHECK_VERSION=1 ;;
  esac
done

# 公网地址（可在环境变量里覆盖）
SITE="${PREFLIGHT_SITE:-https://touhou-mock.app.workbuddy.host}"

PASS=0
FAIL=0
declare -a FAILED_ITEMS=()

# 打印一条检查结果；$1=状态(OK/NG) $2=检查项名 $3=说明
report() {
  if [ "$1" = "OK" ]; then
    PASS=$((PASS + 1))
    printf '  [PASS] %s  %s\n' "$2" "$3"
  else
    FAIL=$((FAIL + 1))
    FAILED_ITEMS+=("$2")
    printf '  [FAIL] %s  %s\n' "$2" "$3"
  fi
}

# 数「有多少行输出」—— grep -c 无匹配时退出码为 1，
# 不能写 `|| echo 0`（会多输出一个 0）。统一走这里。
count() {
  grep -c "$@" 2>/dev/null || true
}

echo "============================================================"
echo "发布前检查 · preflight-check"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')    项目：$(pwd)"
echo "============================================================"

# ---------------------------------------------------------------------------
echo ""
echo "---- ① 密钥泄漏：被跟踪文件里有没有密钥「值」特征 ----"
echo "# 只认「键值形态」（KEY = 20 位以上长串），不认文档里散落的词"
echo "# 并且排除「自证文字」—— 讨论扫描规则本身的行（含省略号 / 正则元字符）"
RE='(eyJhbG|eyJ[A-Za-z0-9_-]{20,})|(API_?KEY|apikey|secret|token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_-]{20,}'
# 自证文字的特征：含省略号（... 或 …）或正则元字符（[A-Za-z 、{20,} 、\s* 等）
# 真密钥是一串连续字符，不会有这些东西。
SELFRE='\.\.\.|…|\[A-Za-z|\{20,\}|\\s\*|\\S\*'
HITS=$(git ls-files -z | xargs -0 grep -i -E "$RE" 2>/dev/null | grep -vE "$SELFRE")
NHIT=$(printf '%s' "$HITS" | count .)
if [ "$NHIT" -eq 0 ]; then
  report OK "① 密钥泄漏" "命中 0 行（干净）"
else
  report NG "① 密钥泄漏" "命中 $NHIT 行 —— 明细如下："
  printf '%s\n' "$HITS" | sed 's/^/         /'
fi

# ---------------------------------------------------------------------------
echo ""
echo "---- ② .env 不进仓库 ----"
ENVF=$(git ls-files | count -E '(^|/)\.env$')
if [ "$ENVF" -eq 0 ]; then
  report OK "② .env 未入库" "被跟踪的 .env 数 = 0"
else
  report NG "② .env 未入库" "有 $ENVF 个 .env 被跟踪：$(git ls-files | grep -E '(^|/)\.env$' | tr '\n' ' ')"
fi

# ---------------------------------------------------------------------------
echo ""
echo "---- ③ .env.example 必须能提交（不被忽略）----"
line=$(git check-ignore -v .env.example 2>/dev/null)
if [ -z "$line" ]; then
  report OK "③ .env.example 可提交" "无规则命中"
elif printf '%s' "$line" | grep -q '^[^:]*:[0-9]*:!'; then
  report OK "③ .env.example 可提交" "命中 ! 例外规则（未被忽略）"
else
  report NG "③ .env.example 可提交" "被忽略了，模板提交不了 → $line"
fi

# ---------------------------------------------------------------------------
if [ "$OFFLINE" -eq 0 ]; then
  echo ""
  echo "---- ④ 公网接口可达（$SITE）----"
  for p in /api/health /api/hot /api/favorites; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$SITE$p" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
      report OK "④ 公网 $p" "HTTP 200"
    else
      report NG "④ 公网 $p" "HTTP $code（期望 200）"
    fi
  done

  echo ""
  echo "---- ⑤ 错误响应不漏内部细节 ----"
  # 打一个必然失败的写请求，看它回不回事先约定好的「人话」，而不是堆栈/连接串
  BODY=$(curl -s -m 10 -X POST -H 'Content-Type: application/json' \
         -d '{}' "$SITE/api/favorites" 2>/dev/null || echo '')
  LEAK=$(printf '%s' "$BODY" | grep -E 'ECONNREFUSED|at Object\.|at async|node_modules|password=|postgres://|127\.0\.0\.1:[0-9]+' | head -1)
  if [ -n "$LEAK" ]; then
    report NG "⑤ 错误不漏内部细节" "响应体里有内部信息：$LEAK"
  else
    report OK "⑤ 错误不漏内部细节" "未命中堆栈/连接串特征"
  fi
else
  echo ""
  echo "---- ④⑤ 公网检查已跳过（--offline）----"
fi

# ---------------------------------------------------------------------------
if [ "$CHECK_VERSION" -eq 1 ]; then
  echo ""
  echo "---- ⑥ 前端版本号是否已升（对比 HEAD 与上一提交）----"
  cur=$(grep -oE 'app\.js\?v=[0-9]+' my-app/index.html | head -1 | grep -oE '[0-9]+')
  prev=$(git show HEAD:my-app/index.html 2>/dev/null | grep -oE 'app\.js\?v=[0-9]+' | head -1 | grep -oE '[0-9]+')
  if [ -z "$prev" ]; then
    report OK "⑥ 版本号" "无上一版本可比，当前 v=$cur"
  elif [ "$cur" -gt "$prev" ]; then
    report OK "⑥ 版本号" "已升：v$prev → v$cur"
  else
    report NG "⑥ 版本号" "未升（当前 v$cur，上一提交 v$prev）—— 改了 JS 必须升，否则用户吃缓存"
  fi
fi

# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "汇总：通过 $PASS 项，失败 $FAIL 项"
if [ "$FAIL" -eq 0 ]; then
  echo ">>> ✅ 全部通过，可以发布"
else
  echo ">>> ❌ 有 $FAIL 项没过，先修再发："
  for it in "${FAILED_ITEMS[@]}"; do echo "      - $it"; done
fi
echo "============================================================"

[ "$FAIL" -eq 0 ] || exit 1
exit 0
