'use strict';
/**
 * 数据访问层 · 配置
 * ------------------------------------------------------------------
 * 只负责一件事：把「环境变量 → 连接参数」这层翻译做掉，
 * 让上层（pg.js / rest.js / snapshot.js）不用到处 process.env。
 *
 * 三条数据源通道的开关，全部由这里的环境变量决定：
 *   ① HTTP API（PostgREST）：CLOUDBASE_ENV_ID + CLOUDBASE_API_KEY
 *   ② pg 直连：              PG_URL 或 DATABASE_URL
 *   ③ 快照降级：              以上都没有 → 读 deploy/data/*.json
 */

const path = require('path');

/** 快照文件目录。 */
const DATA_DIR = path.join(__dirname, '..', 'data');

/* ============================================================
 * ① HTTP API（PostgREST）通道的配置
 * ============================================================ */

/** CloudBase 环境 ID（必须从控制台「复制」取得，不要手打/OCR）。 */
function getRestEnvId() {
  return process.env.CLOUDBASE_ENV_ID || '';
}

/** CloudBase 服务端 API Key（service_role，绕过 RLS，**严禁进前端/仓库**）。 */
function getRestApiKey() {
  return process.env.CLOUDBASE_API_KEY || '';
}

/** 是否具备走 HTTP API 的条件（环境 ID + API Key 都在）。 */
function hasRestApi() {
  return !!(getRestEnvId() && getRestApiKey());
}

/** PostgREST 基址：https://{envId}.api.tcloudbasegateway.com/v1/rdb/rest/{table} */
function getRestBase(table) {
  return 'https://' + getRestEnvId() + '.api.tcloudbasegateway.com/v1/rdb/rest/' + table;
}

/* ============================================================
 * ② pg 直连通道的配置
 * ============================================================ */

/**
 * 取数据库连接串。
 * 支持两种环境变量名（PG_URL 是本项目约定，DATABASE_URL 是业界通用叫法）。
 */
function getConnString() {
  return process.env.PG_URL || process.env.DATABASE_URL || '';
}

/** 连接池参数（集中一处，方便调优）。 */
function getPoolOptions() {
  return {
    connectionString: getConnString(),
    // CloudBase / 云数据库通常要求 SSL；本地直连时可用 PG_NO_SSL=1 关掉
    ssl: process.env.PG_NO_SSL === '1' ? false : { rejectUnauthorized: false },
    max: 5,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 8000
  };
}

module.exports = {
  DATA_DIR: DATA_DIR,
  // ① REST
  getRestEnvId: getRestEnvId,
  getRestApiKey: getRestApiKey,
  hasRestApi: hasRestApi,
  getRestBase: getRestBase,
  // ② pg
  getConnString: getConnString,
  getPoolOptions: getPoolOptions
};
