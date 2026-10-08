-- ============================================================
-- PostgreSQL 首次初始化脚本
-- 挂载方式：docker-compose.yml 里 ./backend/sql → /docker-entrypoint-initdb.d
-- 执行时机：仅数据卷为空时执行一次（官方 postgres 镜像行为）
-- 作用：把向量检索扩展装好，供后续角色/片段语义召回使用
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
