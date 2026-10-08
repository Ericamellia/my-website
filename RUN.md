# RUN.md｜东方同人搜索 本地运行说明

> Day 7 MVP 运行存档。纯静态站（无后端、无数据库、无构建步骤），只需要一个静态文件服务器。

## 1. 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| Python | 3.x（任意现代版本） | 只用标准库 `http.server`，无需 pip 安装任何包 |
| 浏览器 | Chrome / Edge 等现代浏览器 | 需支持 fetch / ES6 模板字符串 |

## 2. 启动命令

> **重要提示（2026-10-08 实测）**：本地预览服务是**会话级**的 —— 进程随启动它的会话结束而消失。
> 所以「打不开」通常是**服务没在跑**，不是配置问题。重启命令见下。
> 8000 端口历史上被残留进程占用（连得上但无响应），**请直接用 8001**。

```bash
cd "C:\Users\25394\WorkBuddy\2026-09-18-00-29-07"
"C:\Users\25394\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m http.server 8001 --bind 127.0.0.1
```

启动成功的标志：终端输出

```
Serving HTTP on 127.0.0.1 port 8001 (http://127.0.0.1:8001/) ...
```

> ⚠️ 不要关闭这个终端窗口，关了服务就停。
> ⚠️ 若提示端口被占用（`OSError: [Errno 10048]`），换成 8002 等空闲端口，下面地址也跟着改。

### 判断服务是否在跑

```bash
netstat -ano | grep ":8001.*LISTENING"     # 有输出=在跑；无输出=没跑
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/my-app/   # 期望 200
```

若 `netstat` 只看到 `TIME_WAIT` / `SYN_SENT` 而没有 `LISTENING`，说明服务已停止，重新执行上面的启动命令即可。

### 打不开时优先试 127.0.0.1

某些环境下 `localhost` 会走系统代理（返回 **502 Bad Gateway**），而 `127.0.0.1` 直连本机可绕开代理。
**两个都试一遍**，能确定是代理问题还是服务问题。

## 3. 访问地址

| 页面 | URL |
|---|---|
| **根加载页**（先播「少女祈祷中」再进入） | http://127.0.0.1:8001/index.html |
| **首页** | http://127.0.0.1:8001/my-app/ |
| 同人音乐 | http://127.0.0.1:8001/my-app/#/music |
| 同人漫画 | http://127.0.0.1:8001/my-app/#/doujin |
| 同人游戏 | http://127.0.0.1:8001/my-app/#/game |
| 同人视频 | http://127.0.0.1:8001/my-app/#/video |
| ZUN 原曲 | http://127.0.0.1:8001/my-app/#/original |
| 作品详情（示例） | http://127.0.0.1:8001/my-app/#/music/1 |
| 角色反查（示例） | http://127.0.0.1:8001/my-app/#/character/博丽灵梦 |

## 4. 改了代码看效果（重要）

**每次改动 `app.js` / `style.css` 后，必须做两件事：**

1. 把 `my-app/index.html` 里引用的版本号加一：`app.js?v=4` → `app.js?v=5`
2. 浏览器用 **Ctrl + F5** 强制刷新

> 原因：`python -m http.server` 不发 `Cache-Control` 头，浏览器会用启发式缓存继续加载旧 JS，出现「改了没生效」的假象（Day 7 实际踩过）。

## 5. 常见问题

| 症状 | 原因 | 解法 |
|---|---|---|
| 双击 `index.html` 打开后一直「加载中」 | `file://` 协议下 fetch 被浏览器 CORS 拦截 | 必须用 http server（见第 2 节），不要直接双击文件 |
| **页面打不开 / 一直转圈 / 502** | **服务进程已随会话结束消失**（最常见） | 见第 2 节「判断服务是否在跑」，重新启动；地址优先用 `127.0.0.1` |
| 页面显示「数据加载失败：…」 | 服务没启动 / 端口不对 / 目录不对 | 核对终端是否还在跑、URL 端口是否一致 |
| 视频封面显示成色块 | B站图床防盗链或网络波动（已加 `referrerpolicy="no-referrer"` 降级） | 属预期降级，不裂图；网络正常时会显示真实封面 |
| 中文乱码 | 文件编码不对 | 全部文件统一 UTF-8（当前已是） |

## 5·补 数据库（Day 16 起）

数据层脚本在 `db/` 目录，目标库是 **CloudBase PostgreSQL**。

| 文件 | 用途 |
|---|---|
| `db/schema.sql` | 建表（2 张表：`circles` / `works`），幂等，可重复执行 |
| `db/seed.sql` | 种子数据全文（26 社团 + 30 作品），幂等 |
| `db/seed-part1-circles.sql` | 仅社团 26 条（分批导入用，控制台单次粘贴量有限） |
| `db/seed-part2-works.sql` | 仅作品 30 条（**必须在 part1 之后执行**，有外键依赖） |
| `db/gen_seed.py` | 从 `my-app/data/*.json` 重新生成 `seed.sql`（改了 JSON 就重跑这个） |

**导入顺序**：`schema.sql` → `seed-part1-circles.sql` → `seed-part2-works.sql`

**执行位置**：CloudBase 控制台 → SQL 数据库 → SQL 编辑器。

详细设计说明见 `docs/day16/data-model.md`。

## 6. 未来部署（GitHub Pages）

本地跑通后，部署只需把仓库推到 GitHub，在仓库 Settings → Pages 选 `main` 分支即可。

注意：站点在 `my-app/` 子目录，Pages 默认指向根目录，届时需要二选一：
- 方案 A：仓库根加一个跳转页（指向 `/my-app/`）
- 方案 B：把 Pages 配置改为 GitHub Actions 指定 `my-app/` 目录

（此项留到 Day 21+ 部署时再定，今日不做。）
