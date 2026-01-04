#!/bin/bash
# docker-entrypoint.sh

set -e  # 出现错误时退出

echo "🚀 启动 HotSearch 分析系统..."

# 清理 Xvfb 锁文件
echo "🧹 清理 Xvfb 锁文件..."
rm -f /tmp/.X99-lock 2>/dev/null || true

# 启动 Xvfb 用于无头浏览器
echo "🖥️  启动 Xvfb 虚拟显示..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# 等待 Xvfb 启动
sleep 2

# 检查 Xvfb 是否启动成功
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "⚠️  Xvfb 启动失败，但继续启动应用..."
fi

# 检查数据库连接
echo "⏳ 等待 MySQL 数据库启动..."
MAX_RETRIES=30
RETRY_COUNT=0
DB_READY=0

# 使用更兼容的 netcat 命令检查端口
while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ $DB_READY -eq 0 ]; do
    # 尝试多种方法检查端口
    if command -v nc >/dev/null 2>&1; then
        # 使用 netcat
        if nc -z mysql 3306 2>/dev/null; then
            DB_READY=1
        fi
    elif command -v python3 >/dev/null 2>&1; then
        # 使用 Python
        if python3 -c "
import socket
import sys
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(('mysql', 3306))
    sock.close()
    sys.exit(0 if result == 0 else 1)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
            DB_READY=1
        fi
    else
        # 使用 telnet 或简单的 bash 重定向
        if timeout 2 bash -c '</dev/tcp/mysql/3306' 2>/dev/null; then
            DB_READY=1
        fi
    fi

    if [ $DB_READY -eq 1 ]; then
        echo "✅ MySQL 数据库已就绪"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "⏰ 等待 MySQL 启动... ($RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ MySQL 数据库连接超时，继续启动应用..."
fi

# 初始化向量数据库目录
echo "📁 初始化目录结构..."
mkdir -p vector_db/chroma_db 2>/dev/null || true
mkdir -p logs 2>/dev/null || true
mkdir -p data 2>/dev/null || true

# 检查数据库表结构
echo "🗃️  检查数据库表结构..."
if command -v python3 >/dev/null 2>&1; then
    python3 -c "
import pymysql
import os
import sys

try:
    conn = pymysql.connect(
        host='mysql',
        user='root',
        password='123456',
        database='hotsearch_db',
        port=3306
    )

    cursor = conn.cursor()
    cursor.execute('SHOW TABLES LIKE \"hot_articles\"')
    result = cursor.fetchone()

    if result:
        print('✅ hot_articles 表已存在')
    else:
        print('⚠️  hot_articles 表不存在，应用将继续启动')

    conn.close()
except Exception as e:
    print(f'❌ 数据库连接检查失败: {e}')
    print('⚠️  应用将继续启动，但数据库功能可能受限')
"
else
    echo "⚠️  Python3 不可用，跳过数据库检查"
fi

# 启动应用
echo "🎯 启动 Flask 应用..."
exec python3 app.py