import pymysql
import datetime
import logging
from .settings import MYSQL_CONFIG


class MySQLPipeline:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        try:
            self.conn = pymysql.connect(
                host=MYSQL_CONFIG['host'],
                user=MYSQL_CONFIG['user'],
                password=MYSQL_CONFIG['password'],
                db=MYSQL_CONFIG['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.conn.cursor()
            self.logger.info("✅ 数据库连接成功")
            self._create_table()
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败: {e}")

    def _create_table(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS hot_articles
                (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    platform_id TINYINT NOT NULL COMMENT '平台 ID(1-22)',
                    rank INT NOT NULL COMMENT '排名',
                    title VARCHAR(255) NOT NULL COMMENT '清洗后的标题',
                    author VARCHAR(100) NOT NULL COMMENT '清洗后的作者',
                    url TEXT NOT NULL COMMENT '文章 URL',
                    crawl_time DATETIME NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_platform_rank (platform_id, rank)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            self.conn.commit()
            self.logger.info("✅ 表 hot_articles 已创建或已存在")
        except Exception as e:
            self.logger.error(f"❌ 创建表失败: {e}")

    def process_item(self, item, spider):
        try:
            if hasattr(item, 'process_item'):
                item = item.process_item()

            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.logger.debug(f"处理 item: {item}")

            self.cursor.execute("""
                INSERT INTO hot_articles (platform_id, rank, title, author, url, crawl_time)
                VALUES (%s, %s, %s, %s, %s, %s) 
                ON DUPLICATE KEY UPDATE
                    title = VALUES (title), 
                    author = VALUES (author), 
                    url = VALUES (url), 
                    crawl_time = VALUES (crawl_time)
            """, (
                item['platform_id'],
                item['rank'],
                item['title'],
                item['author'],
                item['url'],
                now
            ))

            self.conn.commit()

            if self.cursor.rowcount == 1:
                self.logger.info(f"✅ 已插入平台ID {item['platform_id']} 排名 {item['rank']} 的新记录: '{item['title']}'")
            else:
                self.logger.info(f"🔄 已更新平台ID {item['platform_id']} 排名 {item['rank']} 的记录: '{item['title']}'")

            return item

        except Exception as e:
            self.logger.error(f"❌ 处理 item 时出错: {e}", exc_info=True)
            self.conn.rollback()
            return item

    def close_spider(self, spider):
        try:
            if self.conn:
                self.conn.close()
                self.logger.info("🔌 数据库连接已关闭")
        except Exception as e:
            self.logger.error(f"❌ 关闭数据库连接失败: {e}")
