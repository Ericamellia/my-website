'use strict';
/**
 * 数据访问层 · PostgreSQL 直连通道
 * ------------------------------------------------------------------
 * 用 pg 驱动直接连 PostgreSQL。适用于：本地开发、云函数/后端（能装依赖的环境）。
 *
 * 设计要点：
 *   - pg 驱动**按需加载**：没装 pg 时不 crash，自动降级到快照；
 *   - 连接池**懒创建**：只有真正要用的时候才建；
 *   - 对外只暴露两个东西：hasDatabase()（能不能用）和 query()（执行 SQL）。
 */

const config = require('./config');

/** 缓存 pg 模块，避免每次请求都去 require（也避免没装时反复抛错）。 */
let pgModule = null;
let pgTried = false;

/** 连接池：只有真正要用的时候才创建。 */
let pool = null;

/** 尝试加载 pg 驱动。返回 null 表示不可用（没装）。 */
function loadPg() {
  if (pgTried) return pgModule;
  pgTried = true;
  try {
    pgModule = require('pg');
  } catch (e) {
    pgModule = null;
  }
  return pgModule;
}

/** 判断当前是否有可用的真库连接。 */
function hasDatabase() {
  return !!config.getConnString() && !!loadPg();
}

/** 拿到连接池（懒创建）。 */
function getPool() {
  if (pool) return pool;
  const pg = loadPg();
  if (!pg) throw new Error('pg_driver_missing');
  pool = new pg.Pool(config.getPoolOptions());
  return pool;
}

/** 执行一条 SQL，返回 rows 数组。 */
async function query(sql, params) {
  const p = getPool();
  const res = await p.query(sql, params || []);
  return res.rows;
}

module.exports = {
  hasDatabase: hasDatabase,
  getPool: getPool,
  query: query
};
