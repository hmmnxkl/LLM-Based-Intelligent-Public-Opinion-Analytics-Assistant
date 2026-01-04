import chromadb
from chromadb.config import Settings
from hotsearch_analysis_agent.config.settings import VECTOR_DB_CONFIG, MYSQL_CONFIG
import pymysql
import logging
from typing import List, Dict, Any
import jieba
import jieba.analyse
import time
import hashlib

logger = logging.getLogger(__name__)

class TitleVectorDBManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=VECTOR_DB_CONFIG['path'] + "_titles",
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = None
        self.is_initialized = False
        self.last_load_time = None
        self.loaded_data_hash = None

        jieba.initialize()

    def initialize(self):
        try:
            self.collection = self.client.get_or_create_collection(
                name="title_vectors",
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 400,
                    "hnsw:M": 32,
                    "hnsw:search_ef": 300,
                    "hnsw:num_threads": 4,
                }
            )
            self.is_initialized = True
            logger.info("✅ 标题向量数据库初始化成功")
        except Exception as e:
            logger.error(f"❌ 标题向量数据库初始化失败: {e}")
            raise e

    def _get_platform_name(self, platform_id):
        from hotsearch_analysis_agent.config.settings import PLATFORM_MAPPING
        return PLATFORM_MAPPING.get(platform_id, f"平台{platform_id}")

    def _extract_keywords(self, text, topK=5):
        try:
            keywords = jieba.analyse.extract_tags(text, topK=topK)
            return keywords
        except:
            return []

    def _get_platform_context(self, platform_id):
        platform_contexts = {
            1: "百度热搜 搜索引擎",
            2: "抖音热榜 短视频",
            3: "头条热榜 新闻资讯",
            4: "知乎热榜 问答社区",
            5: "微博热搜 社交媒体",
            6: "B站热榜 视频社区",
            7: "快手热榜 短视频",
            8: "360热榜 搜索引擎",
            9: "UC热榜 新闻资讯",
            10: "腾讯热榜 新闻资讯",
            11: "网易热榜 新闻资讯",
            12: "凤凰热榜 新闻资讯",
            13: "小红书热榜 社交电商",
            14: "搜狗热搜 搜索引擎",
            15: "澎湃热榜 新闻资讯"
        }
        return platform_contexts.get(platform_id, "热门平台")

    def load_recent_titles(self, hours=24, limit=3000):
        try:
            if not self.is_initialized:
                self.initialize()

            logger.info(f"📥 正在加载最近{hours}小时内的标题数据...")

            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()

            query = f"""
                SELECT platform_id, rank, title, author, url, crawl_time
                FROM hot_articles
                WHERE crawl_time >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)
                ORDER BY crawl_time DESC, platform_id, rank
                LIMIT {limit}
            """
            cursor.execute(query)
            articles = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

            if not articles:
                logger.warning("ostringstream 没有找到标题数据")
                conn.close()
                return False

            current_hash = self._calculate_data_hash(articles)
            if current_hash == self.loaded_data_hash and not self._should_force_reload():
                logger.info("📊 数据未变化，使用现有向量数据")
                conn.close()
                return True

            try:
                all_data = self.collection.get()
                if all_data['ids']:
                    self.collection.delete(ids=all_data['ids'])
                    logger.info(f"🗑️ 已删除 {len(all_data['ids'])} 条旧记录")
            except Exception as e:
                logger.warning(f"通过ID删除失败: {e}")
                try:
                    self.client.delete_collection("title_vectors")
                    self.collection = self.client.get_or_create_collection(
                        name="title_vectors",
                        metadata={"hnsw:space": "cosine"}
                    )
                    logger.info("🔄 通过重建集合清理数据")
                except Exception as e2:
                    logger.error(f"清理数据完全失败: {e2}")
                    conn.close()
                    return False

            field_index = {name: idx for idx, name in enumerate(column_names)}
            processed_count = 0
            seen_titles = set()

            documents = []
            metadatas = []
            ids = []

            for i, article in enumerate(articles):
                title = article[field_index['title']].strip()

                title_hash = hash(title)
                if title_hash in seen_titles:
                    continue
                seen_titles.add(title_hash)

                platform_id = article[field_index['platform_id']]
                url = article[field_index['url']] if 'url' in field_index else ""
                author = article[field_index['author']] if 'author' in field_index else ""
                crawl_time = article[field_index['crawl_time']] if 'crawl_time' in field_index else ""
                rank = article[field_index['rank']] if 'rank' in field_index else 0

                keywords = self._extract_keywords(title)
                platform_context = self._get_platform_context(platform_id)
                enhanced_content = f"{title} {' '.join(keywords)} {platform_context}"

                documents.append(enhanced_content)

                metadata = {
                    'title': title,
                    'platform_id': platform_id,
                    'platform_name': self._get_platform_name(platform_id),
                    'url': url,
                    'author': author if author and author != 'N/A' else '未知',
                    'crawl_time': crawl_time.strftime('%Y-%m-%d %H:%M:%S') if crawl_time else "",
                    'rank': rank,
                    'keywords': ' '.join(keywords[:3]),
                    'load_time': time.time(),
                    'original_title': title
                }

                metadatas.append(metadata)
                ids.append(f"title_{platform_id}_{processed_count}")
                processed_count += 1

            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                self.last_load_time = time.time()
                self.loaded_data_hash = current_hash
                logger.info(f"✅ 成功加载 {processed_count} 个标题到向量数据库")
            else:
                logger.warning("❌ 没有有效标题可添加到向量数据库")

            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ 加载标题数据失败: {e}")
            return False

    def _calculate_data_hash(self, articles):
        data_str = ""
        for article in articles[:100]:
            data_str += str(article)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _should_force_reload(self):
        if not self.last_load_time:
            return True
        return (time.time() - self.last_load_time) > 300

    def _enhance_search_query(self, query):
        keywords = self._extract_keywords(query, topK=3)
        enhanced_query = f"{query} {' '.join(keywords)}"
        return enhanced_query

    def _filter_and_format_results(self, results, platform_filter, n_results):
        from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper

        platform_ids = platform_mapper.extract_platforms_from_text(platform_filter)

        filtered_results = []
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0] if results['distances'] else [1.0] * len(documents)

        for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            if platform_ids and metadata['platform_id'] not in platform_ids:
                continue

            relevance_score = max(0, 1 - distance)

            result = {
                '标题': metadata['title'],
                '平台': metadata['platform_name'],
                '排名位置': metadata['rank'],
                '作者': metadata['author'],
                '发布时间': metadata['crawl_time'],
                '相关度': f"{relevance_score:.3f}",
                'URL': metadata.get('url', '')
            }
            filtered_results.append(result)

            if len(filtered_results) >= n_results:
                break

        return filtered_results

    def semantic_title_search(self, query: str, n_results: int = 10, platform_filter: str = "all", auto_load=True):
        if not self.is_initialized:
            self.initialize()

        if auto_load:
            self.load_recent_titles(hours=24, limit=3000)

        if self.collection.count() == 0:
            return "没有可用的标题数据，请先加载数据"

        try:
            logger.info(f"🔍 执行标题语义搜索: {query}")

            enhanced_query = self._enhance_search_query(query)

            results = self.collection.query(
                query_texts=[enhanced_query],
                n_results=min(n_results * 2, 50)
            )

            if not results['documents'] or not results['documents'][0]:
                logger.info("未找到相关标题")
                return "没有找到相关的新闻标题"

            filtered_results = self._filter_and_format_results(
                results,
                platform_filter,
                n_results
            )

            if not filtered_results:
                return "没有找到符合条件的结果"

            logger.info(f"✅ 标题搜索完成，找到 {len(filtered_results)} 个结果")
            return filtered_results

        except Exception as e:
            logger.error(f"❌ 标题搜索失败: {e}")
            return f"标题搜索失败: {e}"

title_vector_db_manager = TitleVectorDBManager()
