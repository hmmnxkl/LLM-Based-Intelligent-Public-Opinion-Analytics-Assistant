import chromadb
from chromadb.config import Settings
from hotsearch_analysis_agent.config.settings import VECTOR_DB_CONFIG, MYSQL_CONFIG
import pymysql
from hotsearch_analysis_agent.utils.content_extractor import ContentExtractor
import logging

logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=VECTOR_DB_CONFIG['path'],
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = None
        self.content_extractor = ContentExtractor()
        self.is_initialized = False

    def initialize(self):
        try:
            logger.info("📚 正在初始化向量数据库...")
            self.collection = self.client.get_or_create_collection(
                name=VECTOR_DB_CONFIG['collection_name']
            )
            self.is_initialized = True
            logger.info("✅ 向量数据库集合创建成功")
            return True
        except Exception as e:
            logger.error(f"❌ 初始化向量数据库失败: {e}")
            return False

    def _load_articles_to_vector_db(self, force_clear=False):
        try:
            if force_clear:
                logger.info("清空现有向量数据库数据")
                self.collection.delete()

            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()

            query = """
                    SELECT platform_id, rank, title, author, url, crawl_time
                    FROM hot_articles
                    WHERE crawl_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
                    ORDER BY crawl_time DESC LIMIT 1000
                    """
            cursor.execute(query)
            articles = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

            if not articles:
                logger.warning("📭 没有找到文章数据")
                return False

            documents = []
            metadatas = []
            ids = []

            field_index = {name: idx for idx, name in enumerate(column_names)}

            processed_count = 0
            video_count = 0
            article_count = 0

            for i, article in enumerate(articles):
                title = article[field_index['title']]
                platform_id = article[field_index['platform_id']]
                url = article[field_index['url']] if 'url' in field_index else ""
                author = article[field_index['author']] if 'author' in field_index else ""
                crawl_time = article[field_index['crawl_time']] if 'crawl_time' in field_index else ""

                logger.info(f"处理第 {i + 1}/{len(articles)} 篇文章: {title[:50]}...")

                content, is_video, video_url = self.content_extractor.extract_text_content(url)

                if content and not content.startswith("网络请求失败") and not content.startswith("提取内容失败"):
                    document_content = f"标题: {title}\n内容: {content}"

                    content_type = "视频" if is_video else "文章"
                    if is_video:
                        video_count += 1
                        if video_url:
                            document_content += f"\n视频URL: {video_url}"
                            logger.info(f"🎥 视频内容处理完成，视频URL: {video_url}")
                    else:
                        article_count += 1

                    logger.info(f"📄 {content_type} 内容处理完成，长度: {len(document_content)} 字符")
                else:
                    document_content = title
                    article_count += 1
                    logger.warning(f"⚠️ 内容提取失败，仅使用标题: {title}")

                documents.append(document_content)

                metadata = {
                    'title': title,
                    'platform_id': platform_id,
                    'url': url,
                    'author': author,
                    'crawl_time': crawl_time.strftime('%Y-%m-%d %H:%M:%S') if crawl_time else "",
                    'content_type': 'video' if is_video else 'article',
                    'has_video_url': bool(video_url)
                }
                if video_url:
                    metadata['video_url'] = video_url

                metadatas.append(metadata)
                ids.append(f"article_{i}")
                processed_count += 1

            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"✅ 成功加载 {processed_count} 篇文章到向量数据库")
                logger.info(f"📊 内容统计 - 文章: {article_count}, 视频: {video_count}")
            else:
                logger.warning("❌ 没有有效文档可添加到向量数据库")

            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ 加载文章数据失败: {e}")
            return False

    def ensure_data_loaded(self, force_reload=False):
        if not self.is_initialized:
            self.initialize()

        if force_reload or self.collection.count() == 0:
            logger.info("📥 正在加载文章数据到向量数据库...")
            return self._load_articles_to_vector_db()
        return True

    def similarity_search(self, query: str, n_results: int = 5):
        if not self.is_initialized:
            logger.error("向量数据库未初始化")
            return "向量数据库未初始化，请先初始化系统"

        if self.collection.count() == 0:
            logger.info("🔍 首次搜索，正在加载文章数据...")
            success = self._load_articles_to_vector_db()
            if not success:
                logger.error("数据加载失败")
                return "数据加载失败，无法进行搜索"

        try:
            logger.info(f"🔍 执行搜索查询: {query}")
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )

            if not results['documents'] or not results['documents'][0]:
                logger.info("未找到相关结果")
                return "没有找到相关结果"

            formatted_results = []
            for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                result_item = {
                    '排名': i + 1,
                    '标题': metadata['title'],
                    'URL': metadata['url'],
                    '平台': metadata['platform_id'],
                    '内容类型': metadata.get('content_type', 'unknown'),
                    '相关内容': doc[:300] + '...' if len(doc) > 300 else doc
                }

                if metadata.get('has_video_url') and metadata.get('video_url'):
                    result_item['视频URL'] = metadata['video_url']

                formatted_results.append(result_item)

            logger.info(f"✅ 搜索完成，找到 {len(formatted_results)} 个结果")
            return formatted_results

        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            return f"搜索失败: {e}"

    def refresh_vector_data(self):
        logger.info("🔄 手动刷新向量数据库数据")
        if not self.is_initialized:
            self.initialize()
        return self._load_articles_to_vector_db(force_clear=True)
