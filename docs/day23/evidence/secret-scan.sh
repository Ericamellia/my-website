#!/usr/bin/env bash
# ============================================================================
# Day 23 · 密钥排查脚本
# ----------------------------------------------------------------------------
# 目的：证明「全仓库搜不到密钥特征词」「.env 不在仓库且被忽略」。
# 用法：在项目根目录执行  bash docs/day23/evidence/secret-scan.sh
#
# ⚠️ 两个容易写错的地方（我第一次都踩了）：
#   1) 正则别只匹配「词」。service_role / API_KEY 这类词在文档里是**警告文字**
#      （「严禁进前端」），把它们算成密钥 = 全是误报。
#      → 只匹配「键值形态」：KEY = <20 位以上长串>。
#   2) `git check-ignore -v .env.example` 即使返回 0（命中），
#      命中的也可能是 **`!` negation 规则**（表示「没被忽略」）。
#      → 判断要看输出行的规则是不是以 `!` 开头。
# ============================================================================
set -u
cd "$(dirname "$0")/../../.." || exit 1

echo "============================================================"
echo "Day 23 · 密钥排查 · $(date '+%Y-%m-%d %H:%M:%S')"
echo "扫描范围：git ls-files（只扫会真正进仓库的被跟踪文件）"
echo "============================================================"

TRACKED=$(git ls-files | wc -l)
echo ""
echo "### 1. 被跟踪文件总数：$TRACKED"

# ---------------------------------------------------------------------------
echo ""
echo "### 2. 密钥「值」特征扫描（收紧版正则）"
echo "# 只认键值形态，不认文档里散落的词"
echo "#   正则A: JWT 头 eyJhbG… / eyJ + 20 位以上"
echo '#   正则B: (API_KEY|apikey|secret|token) 后跟 = 或 : 再跟 20 位以上长串'
RE='(eyJhbG|eyJ[A-Za-z0-9_-]{20,})|(API_?KEY|apikey|secret|token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_-]{20,}'
HITS=$(git ls-files -z | xargs -0 grep -i -E "$RE" 2>/dev/null)
NHIT=$(printf '%s' "$HITS" | grep -c . || true)
echo "命中行数 = $NHIT"
if [ "$NHIT" -gt 0 ]; then
  echo ">>> 命中明细："
  printf '%s\n' "$HITS"
else
  echo ">>> 结果：0 条（干净）"
fi

# ---------------------------------------------------------------------------
echo ""
echo "### 3. 已知良性提及（不是密钥，仅登记）"
echo "# service_role / API Key 这些『词』在代码注释和文档里出现，是在警告不要泄漏。"
echo "# 单独统计一下，免得下次看到又疑惑："
grep_n=$(git ls-files -z | xargs -0 grep -l -i -E 'service_role' 2>/dev/null | wc -l)
echo "提及 service_role 的文件数 = $grep_n （均为注释/文档说明，非密钥值）"

# ---------------------------------------------------------------------------
echo ""
echo "### 4. .env 是否在仓库里"
ENVF=$(git ls-files | grep -c -E '(^|/)\.env$' || true)
echo "\$ git ls-files | grep -c '(^|/)\.env$'  →  $ENVF"
git ls-files --error-unmatch .env >/dev/null 2>&1 \
  && echo ">>> ⚠️ .env 被跟踪了！" \
  || echo ">>> .env 未被跟踪 ✓"

# ---------------------------------------------------------------------------
echo ""
echo "### 5. .env 系列是否被忽略"
for f in .env .env.local .env.production .env.development deploy/.env; do
  line=$(git check-ignore -v "$f" 2>/dev/null)
  if [ -z "$line" ]; then
    echo "  $f  → ⚠️ 未被忽略"
  elif printf '%s' "$line" | grep -q '^[^:]*:[0-9]*:!'; then
    echo "  $f  → 命中 negation，未被忽略 ⚠️"
  else
    echo "  $f  → 已忽略 ✓   [$(printf '%s' "$line" | sed 's/:.*:/: /' | head -1)]"
  fi
done

# ---------------------------------------------------------------------------
echo ""
echo "### 6. .env.example 必须『不被忽略』（要能提交）"
line=$(git check-ignore -v .env.example 2>/dev/null)
if printf '%s' "$line" | grep -q '^[^:]*:[0-9]*:!'; then
  echo "  .env.example → 未被忽略 ✓（!.env.example 例外生效）"
elif [ -z "$line" ]; then
  echo "  .env.example → 未被忽略 ✓（无规则命中）"
else
  echo "  .env.example → ⚠️ 被忽略了，例外规则失效"
fi

# ---------------------------------------------------------------------------
echo ""
echo "### 7. 历史提交里是否出现过 .env"
hist=$(git log --all --pretty=format: --name-only --diff-filter=A 2>/dev/null \
       | grep -E '(^|/)\.env$' | sort -u)
if [ -z "$hist" ]; then
  echo ">>> 历史上从未提交过 .env ✓"
else
  echo ">>> ⚠️ 历史里出现过："
  printf '%s\n' "$hist"
fi

# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "结论"
echo "============================================================"
echo "密钥值命中行数 : $NHIT        （期望 0）"
echo ".env 被跟踪数  : $ENVF        （期望 0）"
if [ "$NHIT" -eq 0 ] && [ "$ENVF" -eq 0 ]; then
  echo ">>> ✅ 两项全 0，通过"
else
  echo ">>> ❌ 未达标，见上文"
fi
