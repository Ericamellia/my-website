# CloudBase 开通与云函数部署说明（Day 15 · 板块①）

> 这份文档对应 Day 15 板块①「注册并开通 CloudBase」。
> **状态：已完成并已修通（2026-10-10 / Day 21）** —— 环境 `ericamellia24-d2gk0ftukc71292c5` 已开通，
> 云函数 `api-health` 已部署且**经网关访问返回 200**。
> Day 15 记录的 HTTP 网关 `INVALID_ENV` 已于 Day 21 定位并修复（真因见 §二·补2），
> 排查全过程记录在 `docs/day15/deploy-env.md`。
> 下文步骤保留作存档，重装/换环境时照做即可。

## 〇、本环境实测信息

| 项 | 值 |
|---|---|
| 环境 ID | `ericamellia24-d2gk0ftukc71292c5` |
| 地域 | 上海（ap-shanghai） |
| 计费 | 免费体验版（3000 资源点/月，单环境，不可加购） |
| 到期 | `2027-04-08`（单次续期 6 个月，不自动续） |
| 云函数 | `api-health`（`tam-dbzoo3qi`）· Node.js 18.15 · **HTTP 云函数** · 监听 9000 |
| 云函数状态 | ✅ **已修通**（Day 21）——经网关 `POST .../v1/functions/api-health?webfn=true` 返回 `200` |

## 〇·补　HTTP 云函数部署的三个关键点（Day 21 踩坑总结）

`api-health` 在控制台登记为「**HTTP 云函数**」，它和「自定义函数」是两套完全不同的模型：

| | 自定义函数 | **HTTP 云函数**（本函数） |
|---|---|---|
| 入口 | `exports.main(event, context)` | `app.listen(9000)` 的 Web 服务 |
| 监听端口 | 不需要 | ✅ **必须 9000** |
| `scf_bootstrap` | 不需要 | ✅ **必须有**（无扩展名、LF 换行、可执行权限） |

启动脚本（`functions/api-health/scf_bootstrap`）：

```bash
#!/bin/bash
export PORT=9000
cd "$(dirname "$0")"
exec /var/lang/node18/bin/node index.js
```

> 运行时的 Node 路径必须匹配：`Nodejs18.15` → `/var/lang/node18/bin/node`。

**打包时容易踩的坑**（Windows 上尤其）：
1. `scf_bootstrap` 必须是 **LF** 换行（CRLF 会报 `exec format error`）
2. 必须有**可执行权限**（zip 里写 `external_attr = 0o755 << 16`）
3. 包内文件**平铺根目录**，不要套一层文件夹

**调用时**必须带 `?webfn=true`，否则网关按普通云函数调用，返回 `400 FUNCTIONS_PARAM_INVALID`：

```bash
curl -X POST "https://{envId}.api.tcloudbasegateway.com/v1/functions/api-health?webfn=true" \
  -H "Authorization: Bearer {API_KEY}" -H "Content-Type: application/json" \
  -d '{"path":"/api/health","method":"GET"}'
```

## 一、开通步骤（约 10–15 分钟）

1. 打开 <https://tcb.cloud.tencent.com/> ，用微信或腾讯云账号登录。
2. 首次进入会提示**实名认证**（个人即可，身份证 + 人脸），按页面指引完成。
3. 创建环境：
   - 点「新建环境」→ 名称自填（本项目环境 ID 见上表）
   - 计费方式选 **免费体验版**（3000 资源点/月，1 个环境，学习阶段够用）
   - 地域选离你最近的（本环境为上海 `ap-shanghai`）
4. 创建完成后，在**环境概览**页能看到三样东西，Day 15 截图要用：
   - **环境 ID**（本环境：`ericamellia24-d2gk0ftukc71292c5`）
   - **剩余额度**（免费资源用量）
   - **到期日期**（免费资源到期时间：`2027-04-08`）
5. 环境 ID 已写入本目录 `cloudbaserc.json` 的 `envId` 字段。

## 二、部署 /api/health（两种方式选一种）

### 方式 A：控制台上传（不用装任何工具）

1. 进入环境 → 左侧「云函数」→「新建云函数」
2. 函数名填 `api-health`，运行环境选 `Nodejs 18.15`，创建方式选「本地上传（zip）」
3. 把 `functions/api-health/` 下的 `index.js` + `package.json` 打成一个 zip 上传
4. 函数详情 →「触发管理」→「HTTP 访问服务」→ 路径填 `/api/health`，方法 `GET`
5. 访问 `<默认域名>/api/health`，看到下面这段 JSON 即成功：

```json
{
  "ok": true,
  "service": "touhou-search",
  "env": "ericamellia24-d2gk0ftukc71292c5",
  "version": "1.0.0",
  "time": "2026-10-08T00:00:00.000Z",
  "uptimeSec": 0,
  "node": "v18.15.0",
  "checks": { "http": "ok", "static": "n/a" }
}
```

> **默认域名不生效时**（返回 `{"code":"INVALID_ENV"}`）：
> 去「环境管理 → HTTP 访问服务」，确认**页面顶部全局开关已开启**，
> 再用「域名关联资源」建路由（关联资源=云函数 `api-health`，域名=默认域名，
> 触发路径=`/api/health`），点确定后等 3–5 分钟。

### 方式 B：CloudBase CLI（命令行）

```bash
npm i -g @cloudbase/cli          # 装 CLI
tcb login                        # 浏览器授权登录
tcb env list                     # 确认环境 ID
# cloudbaserc.json 的 envId 已是真实环境 ID，无需再改
tcb fn deploy api-health --force # 部署云函数
tcb service create -f api-health -p /api/health --override  # 建 HTTP 访问路由
```

## 三、与本次已上线服务的关系

`deploy/` 下的 Node 服务已经跑在公网（`https://touhou-mock.app.workbuddy.host`），
`/api/health` 的返回与云函数版**完全一致**（同一份契约，见 `docs/api-contract.md`）。

差异只有两点：

| 项 | 已上线 mock 服务 | CloudBase 云函数 |
|---|---|---|
| `env` 字段 | `mock` | 环境 ID |
| `checks.static` | `ok` | `n/a`（不托管静态资源） |

等 CloudBase 环境开通后，把云函数版部署上去，前端把 baseURL 换成云函数域名即可，
前端代码一行都不用改——这正是先定契约的好处。

## 四、还没做的（按 Day 15 清单明确排除）

- 真实业务接口（`/api/works` 等）→ Day 16–20
- 数据库建表 → Day 16–20
- 跨域白名单收紧（当前是 `*`）→ Day 16
