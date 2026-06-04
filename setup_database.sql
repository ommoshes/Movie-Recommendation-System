-- ============================================================
-- 电影推荐系统 - 数据库初始化脚本
-- 使用方法:
--   1. 确保已安装 MySQL 并启动服务
--   2. 在命令行执行: mysql -u root -p < setup_database.sql
--   3. 或导入此文件到 MySQL 客户端工具（如 Navicat、MySQL Workbench）
-- ============================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS movies_db
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE movies_db;

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL  -- 存储加密后的密码哈希
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. 电影表
-- ============================================================
CREATE TABLE IF NOT EXISTS movies (
    movieId INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    genres VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. 评分表
-- ============================================================
CREATE TABLE IF NOT EXISTS ratings (
    userId INT NOT NULL,
    movieId INT NOT NULL,
    rating FLOAT NOT NULL,           -- 用户评分（0.5-5.0星）
    timestamp BIGINT NOT NULL,       -- 评分时间戳（MovieLens 数据格式）
    PRIMARY KEY (userId, movieId),   -- 联合主键（用户对同一电影的评分唯一）
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (movieId) REFERENCES movies(movieId) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. 电影评论表
-- ============================================================
CREATE TABLE IF NOT EXISTS movie_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movieId INT NOT NULL,
    userId INT NOT NULL,
    content TEXT NOT NULL,                    -- 评论内容
    likes_count INT DEFAULT 0,                -- 点赞数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 评论时间
    is_deleted TINYINT DEFAULT 0,             -- 软删除标记
    FOREIGN KEY (movieId) REFERENCES movies(movieId) ON DELETE CASCADE,
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. 评论互动表（点赞记录）
-- ============================================================
CREATE TABLE IF NOT EXISTS comment_interactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    comment_id INT NOT NULL,
    userId INT NOT NULL,
    interaction_type TINYINT DEFAULT 1,       -- 1: 点赞
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_comment_user (comment_id, userId),  -- 同一用户对同一评论只能点赞一次
    FOREIGN KEY (comment_id) REFERENCES movie_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. 创建索引（提升查询性能）
-- ============================================================
CREATE INDEX idx_ratings_userid ON ratings(userId);
CREATE INDEX idx_ratings_movieid ON ratings(movieId);
CREATE INDEX idx_movies_title ON movies(title(191));  -- 前缀索引，兼容 utf8mb4
CREATE INDEX idx_comments_movieid ON movie_comments(movieId);
CREATE INDEX idx_comments_userid ON movie_comments(userId);
CREATE INDEX idx_interactions_comment ON comment_interactions(comment_id);

-- ============================================================
-- 数据导入说明
-- ============================================================
-- 建表完成后，需要导入电影和评分数据：
--
-- 方法一：使用 Python 脚本（推荐）
--   python import_csv.py
--
-- 方法二：使用 MySQL 命令导入 CSV
--   LOAD DATA LOCAL INFILE 'movies.csv'
--   INTO TABLE movies
--   FIELDS TERMINATED BY ','
--   ENCLOSED BY '"'
--   LINES TERMINATED BY '\n'
--   IGNORE 1 ROWS;
--
--   LOAD DATA LOCAL INFILE 'ratings.csv'
--   INTO TABLE ratings
--   FIELDS TERMINATED BY ','
--   ENCLOSED BY '"'
--   LINES TERMINATED BY '\n'
--   IGNORE 1 ROWS;
-- ============================================================
