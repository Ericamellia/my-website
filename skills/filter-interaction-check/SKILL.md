---
name: filter-interaction-check
description: 检查静态站（无构建步骤的 HTML+CSS+JS）列表页的筛选 / 搜索交互是否真的能用，覆盖三种必测情况——有结果、无结果、清空恢复，并顺带体检可访问性（label 关联、空状态可被读屏播报、键盘可达）。触发场景：新增或改动筛选控件（搜索框、下拉筛选、分类 Tab）后自检；用户反馈「筛选没反应 / 筛完一片空白 / 清空后回不来」；需要给出可亲眼确认的筛选证据时。
agent_created: true
---

# 列表筛选交互检查

## 一句话

**它检查的是：筛选控件在三件事上是否都成立——有结果时能筛出东西、没结果时能给出提示而不是白屏、清空后能完整恢复。**

## 为什么不能只读代码

静态站的筛选通常是「给卡片加 `style.display='none'`」这种 DOM 操作，语法检查全过、代码看着也对，但下面这些只有真跑一遍才暴露：

| 症状 | 根因 |
|---|---|
| 筛完一片空白、没有「无结果」提示 | 只做了隐藏，忘了切换空状态区块的 `hidden` |
| 清空后只回来一部分卡片 | 筛选与「分页只显示三行」两套隐藏逻辑互相覆盖 |
| 筛完数量不对 | 筛选命中的是隐藏面板里的卡片，或没排除已被分页隐藏的卡片 |
| 改了没效果 | 浏览器缓存旧版 `app.js`（没升 `?v=N`） |

## 三种必测情况

1. **有结果**：输入能命中的关键词 → 可见卡片数 > 0，且数量等于预期命中数，空状态区块保持隐藏。
2. **无结果**：输入乱敲的关键词 → 可见卡片数 = 0，**且空状态区块显示出来**（有文案，不是空白一片）。
3. **清空恢复**：把控件清回空 → 可见卡片数恢复到总数，空状态重新隐藏；若列表带分页，应回到「只显示三行」。

## 怎么实测（零依赖：无头浏览器 + 同域 iframe）

筛选靠事件驱动，静态 dump 看不到交互后的状态，所以用「父页 → 同域 iframe → 改控件值并派发事件 → 读结果」的方式：

```html
<!-- filter-check.html：与被测站点同端口同域，放在站点根目录 -->
<iframe id="f" src="http://127.0.0.1:8001/my-app/#/music" style="width:900px;height:900px"></iframe>
<div id="out">pending</div>
<script>
  window.addEventListener('load', () => setTimeout(() => {
    const d = document.getElementById('f').contentDocument;
    const input = d.getElementById('search');           // 搜索框
    const set = v => { input.value = v; input.dispatchEvent(new Event('input')); };
    const visible = () => [...d.querySelectorAll('.work-item, .video-card')]
      .filter(el => el.offsetParent !== null).length;    // offsetParent 为 null = 真不可见
    const emptyShown = () => { const n = d.getElementById('no-result'); return n && !n.hidden; };

    const r = [];
    set('灵梦');  r.push('有结果: visible=' + visible() + ' empty=' + emptyShown());
    set('zzzz');  r.push('无结果: visible=' + visible() + ' empty=' + emptyShown());
    set('');      r.push('清空恢复: visible=' + visible() + ' empty=' + emptyShown());
    document.getElementById('out').textContent = r.join(' | ');
  }, 2500));
</script>
```

```bash
# 起服务后跑（Edge 无头把执行完的 DOM 打印出来）
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --disable-gpu \
  --user-data-dir=C:/Users/25394/shots/profile --window-size=1000,1000 \
  --virtual-time-budget=9000 --dump-dom "http://127.0.0.1:8001/filter-check.html" > dom.html
grep -o '<div id="out">[^<]*' dom.html
```

判据：
- 有结果 → `visible>0`、`empty=false`
- 无结果 → `visible=0`、`empty=true`
- 清空恢复 → `filteredOut=0`、`empty=false`

**清空恢复不要断言 `visible=总数`**：站点若带「一次只显示三行」的分页，恢复后可见数就是分页上限（列数×3），不等于总数。正确判据是「没有卡片还被筛选隐藏（`filteredOut=0`）」+ 空状态隐藏。

**判断可见性用 `offsetParent !== null`**，不要只数 `.lm-hidden` class —— 筛选用的是 inline `display:none`，分页用的是 class，两者叠加时只数 class 会漏判。

## 数据侧陷阱：下拉筛选全 0 命中，先查数据再改代码

下拉筛选（如「按原曲筛选」）每个选项都筛出 0 条时，八成不是代码错了，而是**作品数据没标注该字段**（例如 `music.original` 全是 `null`）。验证方式：

```bash
python -c "import json;d=json.load(open('data/music.json',encoding='utf-8'));print([w.get('original') for w in d['music']])"
```

判定顺序：数据字段为空 → 属于数据待补，代码没问题，如实记进报告；字段有值却筛不出 → 才是代码 bug（多半是 `data-*` 属性存的是名称而 option 存的是 id，两者对不上）。

## 可访问性加练（可选但建议）

顺手过一遍这几项，出问题就记进报告：

- 搜索框有 `placeholder` 且最好有可见 `<label>` 或 `aria-label`
- 「无结果」区块带 `role="status"` / `aria-live="polite"`，内容变化能被读屏播报
- 下拉筛选（`<select>`）与它的文字说明用 `<label>` 包起来，或 `for`/`id` 对应
- 筛选结果是键盘可达的：Tab 能走到输入框、下拉与结果里的链接
- 按钮有可读文本；展开类按钮带 `aria-expanded`

## 常见坑

- 站点有版本号缓存（`app.js?v=N`）时，改完必须升版本号再测，否则测的是旧代码
- 分类 Tab 面板里的列表在隐藏状态下量不出「一行几列」，要先切到该面板再测
- 筛选与分页共存时：筛选变化后要把分页数量重置，否则沿用上一次展开的数量
- 截图要带地址栏时用**非无头**窗口截图（headless 截图没有地址栏）

## 调用记录

每次真实调用后把结果追加到 `RUN_LOG.md`：日期、被测页面、三种情况的实际输出、可访问性结论、证据文件名。
