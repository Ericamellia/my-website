# CloudBase 开通与云函数部署说明（Day 15 · 板块①）

> 这份文档对应 Day 15 板块①「注册并开通 CloudBase」。
> **注册必须由本人完成**——需要腾讯云账号 + 手机号 + 实名认证，任何人都无法代做。
> 下面把步骤写死，照着点即可；完成后把「环境 ID」发我，剩下的部署我来接。

## 一、开通步骤（约 10–15 分钟）

1. 打开 <https://tcb.cloud.tencent.com/> ，用微信或腾讯云账号登录。
2. 首次进入会提示**实名认证**（个人即可，身份证 + 人脸），按页面指引完成。
3. 创建环境：
   - 点「新建环境」→ 名称填 `touhou-search`
   - 计费方式选 **按量计费**（有免费额度，学习阶段不花钱）
   - 地域选离你最近的（华南 `ap-guangzhou`）
4. 创建完成后，在**环境概览**页能看到三样东西，Day 15 截图要用：
   - **环境 ID**（形如 `touhou-search-1x2y3z`）
   - **剩余额度**（免费资源用量）
   - **到期日期**（免费资源到期时间）
5. 把环境 ID 填进本目录的 `cloudbaserc.json`，把 `{{envId}}` 替换掉。

## 二、部署 /api/health（两种方式选一种）

### 方式 A：控制台上传（不用装任何工具）

1. 进入环境 → 左侧「云函数」→「新建云函数」
2. 函数名填 `api-health`，运行环境选 `Nodejs 16`，创建方式选「本地上传（zip）」
3. 把 `functions/api-health/` 下的 `index.js` + `package.json` 打成一个 zip 上传
4. 函数详情 →「触发管理」→「HTTP 访问服务」→ 路径填 `/api/health`，方法 `GET`
5. 访问 `<默认域名>/api/health`，看到下面这段 JSON 即成功：

```json
{
  "ok": true,
  "service": "touhou-search",
  "env": "touhou-search-1x2y3z",
  "version": "1.0.0",
  "time": "2026-10-01T00:00:00.000Z",
  "uptimeSec": 0,
  "node": "v16.x",
  "checks": { "http": "ok", "static": "n/a" }
}
```

### 方式 B：CloudBase CLI（命令行）

```bash
npm i -g @cloudbase/cli          # 装 CLI
tcb login                        # 浏览器授权登录
tcb env list                     # 确认环境 ID
# 把 cloudbaserc.json 里的 {{envId}} 换成真实环境 ID
tcb fn deploy api-health --force # 部署云函数
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
