import chromadb
import jieba
import jieba.analyse
from typing import List, Dict, Any
from chromadb.config import Settings
from hotsearch_analysis_agent.config.settings import VECTOR_DB_CONFIG, MYSQL_CONFIG
import pymysql
import logging
import time
import hashlib
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SentimentVectorDBManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=VECTOR_DB_CONFIG['path'] + "_sentiment",
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = None
        self.is_initialized = False
        self.last_load_time = None
        self.loaded_data_hash = None

        from hotsearch_analysis_agent.utils.advanced_sentiment import AdvancedSentimentAnalyzer
        self.sentiment_analyzer = AdvancedSentimentAnalyzer()

        jieba.initialize()

    def initialize(self):
        try:
            self.collection = self.client.get_or_create_collection(
                name="sentiment_vectors",
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16,
                    "hnsw:search_ef": 100,
                    "description": "情感分析向量数据库"
                }
            )
            self.is_initialized = True
            logger.info("✅ 情感向量数据库初始化成功")

            count = self.collection.count()
            logger.info(f"📊 当前向量数据库中有 {count} 条记录")

        except Exception as e:
            logger.error(f"❌ 情感向量数据库初始化失败: {e}")
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

    def _calculate_data_hash(self, articles):
        data_str = ""
        for article in articles[:100]:
            data_str += str(article)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _should_force_reload(self):
        if not self.last_load_time:
            return True
        return (time.time() - self.last_load_time) > 300

    def _clear_all_data(self):
        try:
            if self.collection:
                all_data = self.collection.get()
                if all_data['ids']:
                    self.collection.delete(ids=all_data['ids'])
                    logger.info(f"🗑️ 已清空 {len(all_data['ids'])} 条旧记录")

            self.loaded_data_hash = None
            self.last_load_time = time.time()

        except Exception as e:
            logger.error(f"❌ 清空数据失败: {e}")
            try:
                self.client.delete_collection("sentiment_vectors")
                self.collection = self.client.get_or_create_collection(
                    name="sentiment_vectors",
                    metadata={
                        "hnsw:space": "cosine",
                        "hnsw:construction_ef": 200,
                        "hnsw:M": 16,
                        "hnsw:search_ef": 100
                    }
                )
                logger.info("🔄 通过重建集合清理数据")
            except Exception as e2:
                logger.error(f"❌ 重建集合失败: {e2}")

    def load_recent_articles(self, hours=24, limit=2000, force_reload=True):
        try:
            if not self.is_initialized:
                self.initialize()

            logger.info(f"📥 强制重新加载最近{hours}小时的文章...")

            if force_reload:
                self._clear_all_data()

            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()

            query = f"""
                SELECT platform_id, rank, title, author, url, crawl_time
                FROM hot_articles 
                WHERE crawl_time >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)
                ORDER BY crawl_time DESC
                LIMIT {limit}
            """

            cursor.execute(query)
            articles = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not articles:
                logger.warning(f"❌ 没有找到最近{hours}小时的数据")
                return False

            field_index = {name: idx for idx, name in enumerate(column_names)}
            processed_count = 0
            seen_titles = set()

            documents = []
            metadatas = []
            ids = []

            sentiment_stats = {"正面": 0, "负面": 0, "中性": 0}
            sentiment_samples = {"正面": [], "负面": [], "中性": []}

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

                sentiment_info = self.sentiment_analyzer.enhanced_analyze(title)
                sentiment_label = sentiment_info['label']
                sentiment_score = sentiment_info['score']
                sentiment_stats[sentiment_label] += 1

                if len(sentiment_samples[sentiment_label]) < 2:
                    sentiment_samples[sentiment_label].append(
                        {
                            'title': title[:50] + "..." if len(title) > 50 else title,
                            'score': sentiment_score,
                            'keywords': sentiment_info['keywords'][:3] if sentiment_info['keywords'] else []
                        })

                keywords = self._extract_keywords(title, topK=3)
                platform_context = self._get_platform_context(platform_id)

                enhanced_content = f"{title} {' '.join(keywords)} {platform_context} {sentiment_label}"

                documents.append(enhanced_content)

                metadata = {
                    'title': title,
                    'platform_id': platform_id,
                    'platform_name': self._get_platform_name(platform_id),
                    'url': url,
                    'author': author if author and author != 'N/A' else '未知',
                    'crawl_time': crawl_time.strftime('%Y-%m-%d %H:%M:%S') if crawl_time else "",
                    'rank': rank,
                    'sentiment_score': float(sentiment_score),
                    'sentiment_label': sentiment_label,
                    'intensity': float(sentiment_info.get('intensity', 1.0)),
                    'aspects': ','.join(sentiment_info['aspects']) if sentiment_info['aspects'] else '',
                    'keywords': ','.join(keywords),
                    'confidence': float(sentiment_info.get('confidence', 0.0)),
                    'load_time': time.time(),
                    'original_title': title
                }

                metadatas.append(metadata)
                ids.append(f"sentiment_{platform_id}_{processed_count}")
                processed_count += 1

            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                self.last_load_time = time.time()
                self.loaded_data_hash = self._calculate_data_hash(articles)

                total_articles = processed_count
                logger.info(f"📊 情感分析统计 (共{total_articles}条):")
                for sentiment, count in sentiment_stats.items():
                    percentage = (count / total_articles * 100) if total_articles > 0 else 0
                    logger.info(f"  {sentiment}: {count} 条 ({percentage:.1f}%)")

                logger.info(f"✅ 成功加载 {processed_count} 条数据到情感向量数据库")
            else:
                logger.warning("❌ 没有有效数据可添加到向量数据库")

            return True

        except Exception as e:
            logger.error(f"❌ 加载文章数据失败: {e}")
            return False

    def _enhance_search_query(self, query):
        keywords = self._extract_keywords(query, topK=3)
        enhanced_query = f"{query} {' '.join(keywords)}"
        return enhanced_query

    def _get_fallback_results(self, platform_ids, sentiment_filter, top_k):
        try:
            logger.info("🔄 使用数据库降级方案获取数据...")

            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()

            conditions = []
            params = []

            if platform_ids:
                placeholders = ','.join(['%s'] * len(platform_ids))
                conditions.append(f"platform_id IN ({placeholders})")
                params.extend(platform_ids)

            conditions.append("crawl_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT platform_id, rank, title, author, url, crawl_time
                FROM hot_articles 
                WHERE {where_clause}
                ORDER BY crawl_time DESC, rank ASC
                LIMIT %s
            """

            params.append(top_k * 2)

            cursor.execute(query, params)
            articles = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not articles:
                return []

            field_index = {name: idx for idx, name in enumerate(column_names)}
            formatted_results = []

            for article in articles:
                title = article[field_index['title']].strip()
                platform_id = article[field_index['platform_id']]

                sentiment_info = self.sentiment_analyzer.enhanced_analyze(title)

                formatted_results.append(
                    {
                        '标题': title,
                        '平台': self._get_platform_name(platform_id),
                        '平台ID': platform_id,
                        '排名': article[field_index.get('rank', '')],
                        '作者': article[field_index.get('author', '未知')],
                        'URL': article[field_index.get('url', 'N/A')],
                        '发布时间': article[field_index.get('crawl_time', '')],
                        '情感倾向': sentiment_info['label'],
                        '情感分数': sentiment_info['score'],
                        '语义相关度': 0.5,
                        '关键方面': sentiment_info.get('aspects', []),
                        '情感关键词': sentiment_info.get('keywords', []),
                        '置信度': sentiment_info.get('confidence', 0.0),
                        '来源': '降级搜索'
                    })

            if sentiment_filter == "正面":
                formatted_results.sort(key=lambda x: x['情感分数'], reverse=True)
            elif sentiment_filter == "负面":
                formatted_results.sort(key=lambda x: x['情感分数'])
            elif sentiment_filter == "中性":
                formatted_results.sort(key=lambda x: abs(x['情感分数']))
            else:
                formatted_results.sort(key=lambda x: abs(x['情感分数']), reverse=True)

            return formatted_results[:top_k]

        except Exception as e:
            logger.error(f"❌ 降级搜索失败: {e}")
            return []

    def _get_all_relevant_results(self, platform_ids, sentiment_filter, top_k, query):
        try:
            all_results = self.collection.get(limit=top_k * 2)

            if not all_results['ids']:
                return self._get_fallback_results(platform_ids, sentiment_filter, top_k)

            formatted_results = []
            for i, metadata in enumerate(all_results['metadatas']):
                if platform_ids and metadata.get('platform_id') not in platform_ids:
                    continue

                if sentiment_filter != "all" and metadata.get('sentiment_label') != sentiment_filter:
                    continue

                formatted_results.append(
                    {
                        '标题': metadata.get('title', '未知标题'),
                        '平台': metadata.get('platform_name', '未知平台'),
                        '平台ID': metadata.get('platform_id', ''),
                        '排名': metadata.get('rank', ''),
                        '作者': metadata.get('author', '未知'),
                        'URL': metadata.get('url', 'N/A'),
                        '发布时间': metadata.get('crawl_time', '未知'),
                        '情感倾向': metadata.get('sentiment_label', '中性'),
                        '情感分数': float(metadata.get('sentiment_score', 0)),
                        '语义相关度': 0.3,
                        '关键方面': metadata.get('aspects', '').split(',') if metadata.get('aspects') else [],
                        '情感关键词': metadata.get('keywords', '').split(',') if metadata.get('keywords') else [],
                        '置信度': float(metadata.get('confidence', '0.0')),
                        '来源': '全量搜索'
                    })

            if len(formatted_results) < top_k:
                fallback = self._get_fallback_results(
                    platform_ids,
                    sentiment_filter,
                    top_k - len(formatted_results)
                )
                formatted_results.extend(fallback)

            return self._sort_and_limit_results(formatted_results, True, top_k, sentiment_filter)

        except Exception as e:
            logger.error(f"❌ 全量搜索失败: {e}")
            return self._get_fallback_results(platform_ids, sentiment_filter, top_k)

    def _format_search_results(self, results, query, sentiment_filter):
        formatted_results = []
        for i, (doc_id, metadata, document, distance) in enumerate(
                zip(results['ids'][0], results['metadatas'][0], results['documents'][0], results['distances'][0])
        ):
            similarity = 1 - distance

            sentiment_score = float(metadata.get('sentiment_score', 0))

            aspects = metadata.get('aspects', '').split(',') if metadata.get('aspects') else []
            keywords = metadata.get('keywords', '').split(',') if metadata.get('keywords') else []

            formatted_results.append(
                {
                    'id': doc_id,
                    '标题': metadata.get('title', '未知标题'),
                    '平台': metadata.get('platform_name', '未知平台'),
                    '平台ID': metadata.get('platform_id', ''),
                    '排名': metadata.get('rank', ''),
                    '作者': metadata.get('author', '未知'),
                    'URL': metadata.get('url', 'N/A'),
                    '发布时间': metadata.get('crawl_time', '未知'),
                    '情感倾向': metadata.get('sentiment_label', '中性'),
                    '情感分数': sentiment_score,
                    '语义相关度': similarity,
                    '关键方面': aspects[:3] if aspects else [],
                    '情感关键词': keywords[:5] if keywords else [],
                    '置信度': float(metadata.get('confidence', '0.0')),
                    '来源': '向量搜索'
                })

        return formatted_results

    def _sort_and_limit_results(self, results, sort_by_sentiment, top_k, sentiment_filter):
        if not results:
            return []

        if sort_by_sentiment:
            if sentiment_filter == "正面":
                results.sort(key=lambda x: x['情感分数'], reverse=True)
            elif sentiment_filter == "负面":
                results.sort(key=lambda x: x['情感分数'])
            elif sentiment_filter == "中性":
                results.sort(key=lambda x: abs(x['情感分数']))
            else:
                results.sort(key=lambda x: abs(x['情感分数']), reverse=True)
        else:
            for result in results:
                similarity = result.get('语义相关度', 0)
                sentiment_score = result.get('情感分数', 0)

                normalized_sentiment = (sentiment_score + 1) / 2
                combined_score = (similarity * 0.7 + normalized_sentiment * 0.3)
                result['综合分数'] = combined_score

            results.sort(key=lambda x: x.get('综合分数', 0), reverse=True)

        return results[:top_k]

    def search_sentiment_articles(self, query: str, platform_ids: List[int], sentiment_filter: str = "all", top_k: int = 20, sort_by_sentiment: bool = False):
        try:
            if not self.is_initialized:
                self.initialize()

            logger.info("🔄 强制重新加载最新数据...")
            force_loaded = self.load_recent_articles(hours=24, limit=3000, force_reload=True)
            if not force_loaded:
                logger.warning("⚠️ 数据加载失败，尝试使用现有数据")

            count = self.collection.count()
            logger.info(f"🔍 开始情感向量搜索，数据库中有 {count} 条记录")

            if count == 0:
                logger.warning("⚠️ 情感向量数据库为空，使用降级方案")
                return self._get_fallback_results(platform_ids, sentiment_filter, top_k)

            where_conditions = None
            conditions = []

            if platform_ids:
                platform_ids_int = [int(pid) for pid in platform_ids]
                conditions.append({"platform_id": {"$in": platform_ids_int}})

            if sentiment_filter != "all":
                conditions.append({"sentiment_label": {"$eq": sentiment_filter}})

            if conditions:
                if len(conditions) == 1:
                    where_conditions = conditions[0]
                else:
                    where_conditions = {"$and": conditions}

            enhanced_query = self._enhance_search_query(query)

            n_results = max(top_k * 3, 100)

            results = self.collection.query(
                query_texts=[enhanced_query],
                n_results=n_results,
                where=where_conditions,
                include=["documents", "metadatas", "distances"]
            )

            if not results['ids'][0] or len(results['ids'][0]) < min(top_k, 5):
                logger.info(f"🔍 匹配结果不足{top_k}条，尝试放宽搜索条件...")

                relaxed_where = None
                if sentiment_filter != "all":
                    relaxed_where = {"sentiment_label": {"$eq": sentiment_filter}}

                relaxed_results = self.collection.query(
                    query_texts=[enhanced_query],
                    n_results=n_results,
                    where=relaxed_where,
                    include=["documents", "metadatas", "distances"]
                )

                if relaxed_results['ids'][0] and len(relaxed_results['ids'][0]) > 0:
                    results = relaxed_results

            if not results['ids'][0] or len(results['ids'][0]) == 0:
                logger.info("🔍 无匹配结果，返回所有相关数据...")
                return self._get_all_relevant_results(platform_ids, sentiment_filter, top_k, query)

            formatted_results = self._format_search_results(results, query, sentiment_filter)

            if len(formatted_results) < top_k and len(formatted_results) < 10:
                logger.info(f"🔍 结果不足，补充降级结果...")
                fallback_results = self._get_fallback_results(
                    platform_ids,
                    sentiment_filter,
                    top_k - len(formatted_results)
                )
                formatted_results.extend(fallback_results[:top_k - len(formatted_results)])

            return self._sort_and_limit_results(formatted_results, sort_by_sentiment, top_k, sentiment_filter)

        except Exception as e:
            logger.error(f"❌ 情感向量搜索失败: {e}")
            return self._get_fallback_results(platform_ids, sentiment_filter, top_k)

    def get_database_stats(self):
        if not self.is_initialized:
            self.initialize()

        try:
            count = self.collection.count()

            all_data = self.collection.get(include=['metadatas'])
            sentiment_stats = {}
            for metadata in all_data['metadatas']:
                label = metadata.get('sentiment_label', '中性')
                sentiment_stats[label] = sentiment_stats.get(label, 0) + 1

            platform_stats = {}
            for metadata in all_data['metadatas']:
                platform = metadata.get('platform_name', '未知平台')
                platform_stats[platform] = platform_stats.get(platform, 0) + 1

            return {
                'total_count': count,
                'sentiment_distribution': sentiment_stats,
                'platform_distribution': platform_stats,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            logger.error(f"❌ 获取数据库统计失败: {e}")
            return {}

    def clear_database(self):
        if not self.is_initialized:
            self.initialize()

        try:
            all_data = self.collection.get()
            ids = all_data['ids']

            if ids:
                self.collection.delete(ids=ids)
                logger.info(f"✅ 已清空 {len(ids)} 条记录")
                return True
            else:
                logger.info("ℹ️ 数据库已为空")
                return True

        except Exception as e:
            logger.error(f"❌ 清空数据库失败: {e}")
            return False

    def health_check(self):
        try:
            if not self.is_initialized:
                return {"status": "error", "message": "未初始化"}

            count = self.collection.count()

            test_results = self.collection.query(query_texts=["测试"], n_results=1)

            return {
                "status": "healthy",
                "collection_count": count,
                "test_query_successful": len(test_results['ids'][0]) > 0,
                "initialized": self.is_initialized,
                "last_load_time": self.last_load_time
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

sentiment_vector_manager = SentimentVectorDBManager()

def initialize_sentiment_vector_db():
    try:
        sentiment_vector_manager.initialize()

        count = sentiment_vector_manager.collection.count()
        if count == 0:
            logger.info("🔄 情感向量数据库为空，正在加载初始数据...")
            sentiment_vector_manager.load_recent_articles(hours=24, limit=500)

        stats = sentiment_vector_manager.get_database_stats()
        logger.info(f"📊 情感向量数据库统计: {stats}")

        return True
    except Exception as e:
        logger.error(f"❌ 初始化情感向量数据库失败: {e}")
        return False
