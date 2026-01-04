[file name]: sql/init.sql
[file content begin]
-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS hotsearch_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE hotsearch_db;

-- 表1: hot_articles 表（舆情数据表）
CREATE TABLE IF NOT EXISTS hot_articles (
id INT AUTO_INCREMENT PRIMARY KEY,
platform_id TINYINT NOT NULL COMMENT '平台 ID(1-26)',
rank INT NOT NULL COMMENT '排名',
title VARCHAR(255) NOT NULL COMMENT '清洗后的标题',
author VARCHAR(100) NOT NULL COMMENT '清洗后的作者',
url TEXT NOT NULL COMMENT '文章 URL',
crawl_time DATETIME NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
UNIQUE KEY unique_platform_rank (platform_id, rank) -- 只保留平台+排名的唯一约束
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表2: push_tasks 表（推送任务表）
CREATE TABLE IF NOT EXISTS push_tasks (
id INT AUTO_INCREMENT PRIMARY KEY,
task_id VARCHAR(64) NOT NULL UNIQUE,
user_prompt TEXT NOT NULL,
push_time VARCHAR(5) NOT NULL COMMENT '推送时间，格式: HH:MM',
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
status ENUM('active', 'paused', 'deleted') DEFAULT 'active',
INDEX idx_task_id (task_id),
INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
[file content end]