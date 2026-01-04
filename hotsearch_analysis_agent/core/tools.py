import time
import pymysql
from langchain.chains import llm
from langchain.tools import BaseTool
from typing import Optional, List, Dict, Any
import re
from hotsearch_analysis_agent.config.settings import MYSQL_CONFIG, PLATFORM_MAPPING
from hotsearch_analysis_agent.utils import content_extractor
from hotsearch_analysis_agent.utils.content_extractor import ContentExtractor
from hotsearch_analysis_agent.utils.sentiment_analyzer import SentimentAnalyzer
from hotsearch_analysis_agent.utils.clustering import TopicClustering
from hotsearch_analysis_agent.vector_db.manager import VectorDBManager
from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper
import logging

logger = logging.getLogger(__name__)


class DatabaseHelper:

    @staticmethod
    def execute_query(query, params=None):
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            return column_names, results
        except Exception as e:
            raise e
        finally:
            conn.close()

    @staticmethod
    def create_field_index(column_names):
        return {name: idx for idx, name in enumerate(column_names)}

    @staticmethod
    def get_article_dict(article, field_index, include_all_fields=False):
        result_dict = {}

        if 'platform_id' in field_index:
            platform_id = article[field_index['platform_id']]
            result_dict['平台'] = PLATFORM_MAPPING.get(platform_id, f"平台{platform_id}")

        if 'rank' in field_index:
            result_dict['排名'] = article[field_index['rank']]

        if 'title' in field_index:
            result_dict['标题'] = article[field_index['title']]

        if 'author' in field_index:
            author = article[field_index['author']]
            result_dict['作者'] = author if author and author != 'N/A' else '未知'

        if 'url' in field_index:
            url = article[field_index['url']]
            result_dict['URL'] = url if url else 'N/A'

        if 'crawl_time' in field_index:
            crawl_time = article[field_index['crawl_time']]
            result_dict['爬取时间'] = crawl_time.strftime('%Y-%m-%d %H:%M:%S') if crawl_time else 'N/A'

        if include_all_fields:
            for field_name, idx in field_index.items():
                if field_name not in ['platform_id', 'rank', 'title', 'author', 'url', 'crawl_time']:
                    result_dict[field_name] = article[idx]

        return result_dict

    @staticmethod
    def build_platform_query(platform_ids, additional_conditions="", limit=100):
        placeholders = ','.join(['%s'] * len(platform_ids))
        base_query = f"""
            SELECT platform_id, rank, title, author, url, crawl_time 
            FROM hot_articles 
            WHERE platform_id IN ({placeholders})
            {additional_conditions}
            ORDER BY platform_id, rank
            LIMIT {limit}
        """
        return base_query, platform_ids


class PlatformQueryTool(BaseTool):
    name = "platform_query"
    description = "查询特定平台的榜单数据。输入可以是平台名称、ID或自然语言描述，例如：'百度热搜'、'1,2,3'、'查询抖音和头条的热搜'"

    def _run(self, input_str: str) -> str:
        try:
            platform_ids = platform_mapper.extract_platforms_from_text(input_str)
            logger.info(f"🔍 检测到的平台ID: {platform_ids}")
            platform_names = platform_mapper.format_platform_list(platform_ids)
            logger.info(f"🔍 平台名称: {platform_names}")

            if not platform_ids:
                return "未找到匹配的平台，请输入有效的平台名称或ID"

            placeholders = ','.join(['%s'] * len(platform_ids))
            query = f"""
                SELECT platform_id, rank, title, author, url, crawl_time 
                FROM hot_articles 
                WHERE platform_id IN ({placeholders})
                ORDER BY platform_id, rank
                LIMIT 1000
            """
            logger.info(f"🔍 执行SQL查询: {query}")
            logger.info(f"🔍 查询参数: {platform_ids}")

            column_names, results = DatabaseHelper.execute_query(query, platform_ids)
            logger.info(f"🔍 查询结果数量: {len(results) if results else 0}")

            if not results:
                return f"在{platform_names}上没有找到热搜数据"

            field_index = DatabaseHelper.create_field_index(column_names)
            output = []
            platform_data_count = {}

            for row in results:
                article_dict = DatabaseHelper.get_article_dict(row, field_index, include_all_fields=True)
                output.append(article_dict)
                platform = article_dict['平台']
                platform_data_count[platform] = platform_data_count.get(platform, 0) + 1

            logger.info(f"🔍 各平台数据统计: {platform_data_count}")

            result_str = f"📊 {platform_names} 热搜榜单：\n"
            platform_groups = {}

            for article in output:
                platform = article['平台']
                if platform not in platform_groups:
                    platform_groups[platform] = []
                platform_groups[platform].append(article)

            detected_platform_names = [platform_mapper.get_platform_name(pid) for pid in platform_ids]

            for platform_name in detected_platform_names:
                if platform_name in platform_groups:
                    articles = platform_groups[platform_name]
                    result_str += f"🏆 {platform_name}（{len(articles)}条）：\n"
                    for article in articles[:15]:
                        result_str += f"  {article['排名']}. {article['标题']}\n"
                        if article.get('URL') and article['URL'] != 'N/A':
                            result_str += f"     链接: {article['URL']}\n"
                        if article.get('作者') and article['作者'] != '未知':
                            result_str += f"     作者：{article['作者']}\n"
                        result_str += f"     时间：{article['爬取时间']}\n"
                    if len(articles) > 15:
                        result_str += f"  ... 还有{len(articles) - 15}条\n"
                else:
                    result_str += f"🏆 {platform_name}（0条）：\n"
                    result_str += f"  暂无数据\n"

            total_articles = len(output)
            result_str += f"📈 总计: {total_articles} 条热搜，涵盖 {len(platform_groups)} 个平台\n"

            if platform_data_count:
                result_str += "📊 数据分布: "
                dist_info = []
                for platform, count in platform_data_count.items():
                    dist_info.append(f"{platform}({count}条)")
                result_str += " | ".join(dist_info) + "\n"

            return result_str
        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            return f"查询失败: {str(e)}"


class TopicClusteringTool(BaseTool):
    name = "topic_clustering"
    description = "对热搜话题进行聚类分析。输入可以是聚类数量、平台筛选或自然语言，例如：'5'、'分析抖音和头条的话题'、'对所有平台进行聚类分析'"

    def __init__(self):
        super().__init__()

    def _run(self, input_str: str) -> str:
        try:
            parts = input_str.split('|')
            n_clusters_str = parts[0].strip() if len(parts) > 0 else "5"
            platform_filter = parts[1].strip() if len(parts) > 1 else "all"

            n_clusters = int(n_clusters_str) if n_clusters_str.isdigit() else 5

            platform_ids = platform_mapper.extract_platforms_from_text(platform_filter)
            platform_names = platform_mapper.format_platform_list(platform_ids)

            clustering = TopicClustering()

            additional_conditions = "AND crawl_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)"
            query_sql, params = DatabaseHelper.build_platform_query(platform_ids, additional_conditions, limit=200)
            column_names, articles = DatabaseHelper.execute_query(query_sql, params)
            field_index = DatabaseHelper.create_field_index(column_names)

            if not articles:
                return f"在{platform_names}上没有找到足够的数据进行聚类分析"

            titles = []
            platforms = []
            articles_data = []

            for article in articles:
                title = article[field_index['title']]
                platform_id = article[field_index['platform_id']]
                platform_name = PLATFORM_MAPPING.get(platform_id, f"平台{platform_id}")
                titles.append(title)
                platforms.append(platform_name)

                article_info = DatabaseHelper.get_article_dict(article, field_index, include_all_fields=True)
                articles_data.append(article_info)

            clusters = clustering.cluster_titles(titles, platforms, articles_data, n_clusters)

            result_str = f"🎯 {platform_names} 话题聚类分析（{len(clusters)}个主题）：\n"
            total_articles = 0

            for cluster_name, cluster_info in clusters.items():
                articles_list = cluster_info['articles']
                total_articles += len(articles_list)
                result_str += f"📂 {cluster_name}（{len(articles_list)}篇文章）\n"
                result_str += f"关键词: {', '.join(cluster_info['keywords'][:5])}\n"
                result_str += "代表性文章:\n"

                displayed_count = 0
                for i, article in enumerate(articles_list[:6]):
                    platform = article['平台']
                    title = article['标题']
                    rank = article.get('排名', '')
                    url = article.get('URL', '')
                    rank_info = f"排名{rank}" if rank else ""

                    result_str += f"[文章{displayed_count + 1}] {platform}: {title} {rank_info}\n"
                    if url and url != 'N/A':
                        result_str += f"     链接: {url}\n"
                    displayed_count += 1

                if len(articles_list) > displayed_count:
                    result_str += f"... 还有{len(articles_list) - displayed_count}条相关话题\n"
                result_str += "\n"

            result_str += f"📊 总计分析了{total_articles}篇文章，发现了{len(clusters)}个主要话题\n"

            return result_str
        except Exception as e:
            logger.error(f"聚类分析失败: {str(e)}")
            return f"聚类分析失败: {str(e)}"

    async def _arun(self, input_str: str) -> str:
        return self._run(input_str)


class SentimentAnalysisTool(BaseTool):
    name = "sentiment_analysis"
    description = "分析新闻标题的情感倾向。输入可以是平台名称、ID或自然语言描述，例如：'百度'、'1,2,3'、'分析抖音和头条的情感倾向'"

    def __init__(self):
        super().__init__()

    def _run(self, input_str: str) -> str:
        try:
            platform_ids = platform_mapper.extract_platforms_from_text(input_str)
            platform_names = platform_mapper.format_platform_list(platform_ids)

            analyzer = SentimentAnalyzer()

            additional_conditions = "AND crawl_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)"
            query_sql, params = DatabaseHelper.build_platform_query(platform_ids, additional_conditions, limit=100)
            column_names, articles = DatabaseHelper.execute_query(query_sql, params)
            field_index = DatabaseHelper.create_field_index(column_names)

            if not articles:
                return f"在{platform_names}上没有找到数据进行分析"

            results = []
            for article in articles:
                platform_id = article[field_index['platform_id']]
                title = article[field_index['title']]
                author = article[field_index.get('author', '')] or '未知'
                crawl_time = article[field_index.get('crawl_time', '')]

                sentiment = analyzer.analyze(title)
                platform_name = PLATFORM_MAPPING.get(platform_id, f"平台{platform_id}")

                results.append({
                    '平台': platform_name,
                    '标题': title,
                    '作者': author,
                    '时间': crawl_time.strftime('%Y-%m-%d %H:%M') if crawl_time else '未知',
                    '情感倾向': sentiment
                })

            sentiment_count = {'正面': 0, '负面': 0, '中性': 0}
            for result in results:
                sentiment_count[result['情感倾向']] += 1

            total = len(results)
            result_str = f"📈 {platform_names} 情感分析报告：\n"
            result_str += f"📊 情感分布统计：\n"
            result_str += f"   😊 正面: {sentiment_count['正面']} 条 ({sentiment_count['正面'] / total * 100:.1f}%)\n"
            result_str += f"   😞 负面: {sentiment_count['负面']} 条 ({sentiment_count['负面'] / total * 100:.1f}%)\n"
            result_str += f"   😐 中性: {sentiment_count['中性']} 条 ({sentiment_count['中性'] / total * 100:.1f}%)\n"

            platform_sentiment = {}
            for result in results:
                platform = result['平台']
                if platform not in platform_sentiment:
                    platform_sentiment[platform] = {'正面': 0, '负面': 0, '中性': 0}
                platform_sentiment[platform][result['情感倾向']] += 1

            result_str += f"📱 各平台情感分布：\n"
            for platform, counts in platform_sentiment.items():
                platform_total = sum(counts.values())
                result_str += f"   {platform}: "
                result_str += f"😊{counts['正面']} 😞{counts['负面']} 😐{counts['中性']}"
                result_str += f" (正面{counts['正面'] / platform_total * 100:.1f}%)\n"

            result_str += "\n"
            result_str += f"🔍 详细分析结果（前10条）：\n"
            for i, result in enumerate(results[:10]):
                emotion_icon = "😊" if result['情感倾向'] == '正面' else "😞" if result['情感倾向'] == '负面' else "😐"
                result_str += f"  {i + 1}. {emotion_icon} [{result['情感倾向']}] {result['标题']}\n"
                result_str += f"     👤 {result['作者']} | ⏰ {result['时间']} | 📱 {result['平台']}\n"

            return result_str
        except Exception as e:
            return f"情感分析失败: {str(e)}"


class VectorSearchTool(BaseTool):
    name = "vector_search"
    description = "基于文章详情内容的语义搜索。输入可以是查询词、平台筛选和数量，例如：'人工智能应用'、'科技|抖音,头条|5'、'搜索教育相关内容'"

    def __init__(self):
        super().__init__()

    def _run(self, input_str: str) -> str:
        try:
            parts = input_str.split('|')
            query = parts[0].strip() if len(parts) > 0 else ""
            platform_filter = parts[1].strip() if len(parts) > 1 else "all"
            top_k = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 5

            if not query:
                return "请输入搜索关键词"

            platform_ids = platform_mapper.extract_platforms_from_text(platform_filter)
            platform_names = platform_mapper.format_platform_list(platform_ids)

            vector_db = VectorDBManager()
            if not vector_db.is_initialized:
                vector_db.initialize()

            results = vector_db.similarity_search(query, top_k)

            if isinstance(results, str):
                return results

            filtered_results = []
            for result in results:
                filtered_results.append(result)

            if not filtered_results:
                return f"在{platform_names}上没有找到与'{query}'相关的文章内容"

            result_str = f"🔍 在{platform_names}基于文章内容搜索 '{query}' 的结果：\n"
            for i, result in enumerate(filtered_results):
                result_str += f"{i + 1}. 📖 {result.get('标题', '未知标题')}\n"
                result_str += f"   📱 平台: {result.get('平台', '未知平台')}\n"
                result_str += f"   🔗 URL: {result.get('URL', 'N/A')}\n"
                result_str += f"   📄 相关内容: {result.get('相关内容', '无内容')}\n"

            return result_str
        except Exception as e:
            return f"向量搜索失败: {str(e)}"


class PlatformListTool(BaseTool):
    name = "platform_list"
    description = "列出所有可用的平台及其ID，用于帮助用户了解支持哪些平台"

    def _run(self, input_str: str = "") -> str:
        try:
            result_str = "📋 支持的平台列表：\n"
            platform_groups = {
                "搜索引擎": [],
                "短视频": [],
                "新闻资讯": [],
                "社交平台": [],
                "其他平台": []
            }

            for pid, name in PLATFORM_MAPPING.items():
                if "百度" in name or "360" in name:
                    platform_groups["搜索引擎"].append((pid, name))
                elif "抖音" in name or "快手" in name or "B站" in name:
                    platform_groups["短视频"].append((pid, name))
                elif "头条" in name or "网易" in name or "凤凰" in name or "腾讯" in name:
                    platform_groups["新闻资讯"].append((pid, name))
                elif "知乎" in name or "UC" in name:
                    platform_groups["社交平台"].append((pid, name))
                else:
                    platform_groups["其他平台"].append((pid, name))

            for group_name, platforms in platform_groups.items():
                if platforms:
                    result_str += f"🏷️ {group_name}：\n"
                    for pid, name in sorted(platforms):
                        result_str += f"   ID {pid:2d}: {name}\n"
                    result_str += "\n"

            result_str += "💡 使用提示：您可以直接使用平台名称进行查询，如'查询百度热搜'、'分析抖音情感'等"
            return result_str
        except Exception as e:
            return f"获取平台列表失败: {str(e)}"


class IntelligentContentAnalysisTool(BaseTool):
    name = "intelligent_content_analysis"
    description = "基于URL进行新闻内容分析和概括。输入格式：'平台名称|新闻标题|URL|用户具体问题'"

    def _run(self, input_str: str) -> str:
        try:
            from hotsearch_analysis_agent.utils.content_extractor import ContentExtractor
            from hotsearch_analysis_agent.config.settings import LLM_CONFIG
            from langchain.chat_models import ChatOpenAI
            from langchain.schema import HumanMessage
            import re

            content_extractor = ContentExtractor()
            llm = ChatOpenAI(
                model_name=LLM_CONFIG['model_name'],
                temperature=0.3,
                max_tokens=400,
                openai_api_key=LLM_CONFIG['api_key'],
                openai_api_base=LLM_CONFIG.get('api_base'),
                openai_organization=LLM_CONFIG.get('organization')
            )

            parts = input_str.split('|')
            if len(parts) < 4:
                return "输入格式错误，请使用：平台名称|新闻标题|URL|用户具体问题"

            platform_filter = parts[0].strip()
            title = parts[1].strip()
            url = parts[2].strip()
            user_question = parts[3].strip()

            if not platform_filter or not title or not url:
                return "请提供平台名称、新闻标题和URL"

            logger.info(f"开始处理内容分析：平台={platform_filter}, 标题={title}, URL={url}")
            return self._process_article_with_url(
                platform_filter, title, url, user_question, content_extractor, llm
            )
        except Exception as e:
            logger.error(f"智能内容分析失败: {str(e)}")
            return f"智能内容分析失败: {str(e)}"

    def _process_article_with_url(self, platform: str, title: str, url: str, user_question: str, content_extractor, llm) -> str:
        try:
            result_str = f"📰 **{title}**\n"
            result_str += f"📱 平台: {platform}\n"
            result_str += f"🔗 原文链接: {url}\n"

            try:
                logger.info(f"开始从URL提取内容: {url}")
                content, is_video, video_url = content_extractor.extract_text_content(url)

                if content and len(content.strip()) > 50:
                    logger.info(f"成功提取内容，长度: {len(content)}")
                    analysis_result = self._analyze_and_summarize(content, title, user_question, is_video, llm)
                    result_str += f"💡 智能分析:\n{analysis_result}"
                else:
                    logger.warning("提取的内容过短或为空")
                    result_str += "❌ 无法从链接提取到足够的文章内容\n"
                    result_str += "建议您直接访问原文链接查看详细内容。"
            except Exception as e:
                logger.error(f"URL内容提取失败: {e}")
                result_str += f"❌ 内容提取失败: {str(e)}\n"
                result_str += "建议您直接访问原文链接查看详细内容。"

            return result_str
        except Exception as e:
            logger.error(f"处理文章内容失败: {e}")
            return f"处理文章内容时出现错误: {str(e)}"

    def _analyze_and_summarize(self, raw_content: str, title: str, user_question: str, is_video: bool, llm) -> str:
        try:
            cleaned_content = self._clean_content(raw_content)
            if len(cleaned_content) < 20:
                return "内容过短，无法进行有效分析"

            if is_video:
                prompt = self._build_video_analysis_prompt(title, cleaned_content, user_question)
            else:
                prompt = self._build_article_analysis_prompt(title, cleaned_content, user_question)

            from langchain.schema import HumanMessage
            message = HumanMessage(content=prompt)
            response = llm([message])

            return response.content.strip()
        except Exception as e:
            return f"内容分析过程中出现错误: {str(e)}"

    def _clean_content(self, content: str) -> str:
        import re
        patterns_to_remove = [
            r'<script.*?>.*?</script>',
            r'<style.*?>.*?</style>',
            r'<!--.*?-->',
            r'广告|推广|赞助',
            r'关注我们|扫码下载|下载APP',
            r'【.*?】',
            r'[0-9]{11}',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ]

        cleaned = content
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)

        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if len(cleaned) > 3000:
            cleaned = cleaned[:3000] + "..."

        return cleaned

    def _build_article_analysis_prompt(self, title: str, content: str, user_question: str) -> str:
        return f"""请基于以下新闻内容，针对用户的问题进行智能分析和概括：
新闻标题：{title}
用户问题：{user_question}
新闻内容：
{content}
请根据上述内容：
1. 首先理解用户的具体问题指向
2. 提取内容中的关键信息，过滤无关的网页元素和广告
3. 用100-200字进行自然、流畅的概括
4. 重点回答用户关心的问题
5. 保持客观准确，不要添加原文中没有的信息
请直接给出分析概括结果："""

    def _build_video_analysis_prompt(self, title: str, content: str, user_question: str) -> str:
        return f"""请基于以下视频内容描述，针对用户的问题进行智能分析：
视频标题：{title}
用户问题：{user_question}
视频内容描述：
{content}
这是一个视频内容，请：
1. 根据可获得的元数据理解视频主题
2. 用100-200字概括视频可能包含的主要内容
3. 针对用户问题提供相关信息
4. 明确说明这是基于视频描述的分析
请直接给出分析概括结果："""

    async def _arun(self, input_str: str) -> str:
        return self._run(input_str)


class SemanticSearchTool(BaseTool):
    name = "semantic_search"
    description = "基于语义搜索相关话题。输入可以是查询词、平台筛选和数量，例如：'科技新闻'、'科技|抖音,头条'、'人工智能|所有平台|20'"

    def _run(self, input_str: str) -> str:
        try:
            parts = input_str.split('|')
            query = parts[0].strip() if len(parts) > 0 else ""
            platform_filter = parts[1].strip() if len(parts) > 1 else "all"
            top_k = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 15

            if not query:
                return "请输入搜索关键词"

            from hotsearch_analysis_agent.vector_db.title_vector_manager import title_vector_db_manager
            vector_db = title_vector_db_manager

            if not vector_db.is_initialized:
                vector_db.initialize()

            logger.info("🔄 即时加载标题数据...")
            vector_db.load_recent_titles(hours=24, limit=3000)

            results = vector_db.semantic_title_search(query, top_k, platform_filter, auto_load=False)

            if isinstance(results, str):
                return results

            if not results:
                from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper
                platform_ids = platform_mapper.extract_platforms_from_text(platform_filter)
                platform_names = platform_mapper.format_platform_list(platform_ids)
                return f"在{platform_names}上没有找到与'{query}'相关的内容"

            return self._format_semantic_results(results, query, platform_filter)
        except Exception as e:
            return f"语义搜索失败: {str(e)}"

    def _format_semantic_results(self, results: List[Dict], query: str, platform_filter: str) -> str:
        from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper
        platform_ids = platform_mapper.extract_platforms_from_text(platform_filter)
        platform_names = platform_mapper.format_platform_list(platform_ids)

        platform_groups = {}
        for result in results:
            platform = result['平台']
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(result)

        result_str = f"🔍 在{platform_names}基于语义搜索 '{query}' 的结果 (已加载最新数据)：\n"

        total_displayed = 0
        for platform, articles in platform_groups.items():
            result_str += f"🏆 {platform}：\n"
            platform_count = 0
            for article in articles:
                if total_displayed >= 20:
                    break
                rank_icon = "🔥" if article['排名位置'] <= 10 else "⭐"
                try:
                    relevance_score = float(article['相关度'])
                    relevance_stars = "⭐" * min(int(relevance_score * 5) + 1, 5)
                except:
                    relevance_stars = "⭐"
                result_str += f"  {rank_icon} {relevance_stars} 排名{article['排名位置']}: {article['标题']}\n"

                if article.get('URL') and article['URL'] != 'N/A':
                    result_str += f"     链接: {article['URL']}\n"
                if article['作者'] != '未知':
                    result_str += f"     作者：{article['作者']} | 时间：{article['发布时间']}\n"
                result_str += f"     语义相关度：{article['相关度']}\n"
                platform_count += 1
                total_displayed += 1
            if platform_count == 0:
                result_str += f"  暂无相关结果\n"

        total_results = len(results)
        result_str += f"📊 共找到 {total_results} 条语义相关标题\n"
        result_str += "🔗 提示: 您可以直接点击上面的链接查看原文"
        return result_str

    async def _arun(self, input_str: str) -> str:
        return self._run(input_str)


class TitleSemanticSearchTool(BaseTool):
    name = "title_semantic_search"
    description = "基于标题语义理解搜索相关新闻。输入格式：'搜索词|平台筛选|数量'，例如：'哇哈哈|所有平台|20'、'科技新闻|抖音,头条|10'、'人工智能发展'"

    def _run(self, input_str: str) -> str:
        try:
            parts = input_str.split('|')
            query = parts[0].strip() if len(parts) > 0 else ""
            platform_filter = parts[1].strip() if len(parts) > 1 else "all"
            top_k = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 15

            if not query:
                return "请输入搜索关键词"

            from hotsearch_analysis_agent.vector_db.title_vector_manager import title_vector_db_manager
            vector_db = title_vector_db_manager

            if not vector_db.is_initialized:
                vector_db.initialize()

            logger.info("🔄 即时加载标题数据...")
            vector_db.load_recent_titles(hours=24, limit=3000)

            results = vector_db.semantic_title_search(query, top_k, platform_filter, auto_load=False)

            if isinstance(results, str):
                return results

            if not results:
                return f"没有找到与 '{query}' 相关的新闻标题"

            return self._format_search_results(results, query, platform_filter)
        except Exception as e:
            return f"标题语义搜索失败: {str(e)}"

    def _format_search_results(self, results: List[Dict], query: str, platform_filter: str) -> str:
        from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper
        platform_names = platform_mapper.format_platform_list(
            platform_mapper.extract_platforms_from_text(platform_filter)
        )
        result_str = f"🔍 在{platform_names}搜索 '{query}' 的语义匹配结果 (已加载最新数据)：\n"

        platform_groups = {}
        for result in results:
            platform = result['平台']
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(result)

        for platform, articles in platform_groups.items():
            result_str += f"🏆 {platform}：\n"
            for article in articles[:8]:
                rank_icon = "🔥" if article['排名位置'] <= 10 else "⭐"
                result_str += f"  {rank_icon} 排名{article['排名位置']}: {article['标题']}\n"

                if article.get('URL') and article['URL'] != 'N/A':
                    result_str += f"     链接: {article['URL']}\n"
                if article['作者'] != '未知':
                    result_str += f"     作者：{article['作者']} | 时间：{article['发布时间']}\n"
                result_str += f"     相关度：{article['相关度']}/1.0\n"

            if len(articles) > 8:
                result_str += f"  ... 还有{len(articles) - 8}条相关标题\n"

        total_results = len(results)
        top_platforms = sorted(
            platform_groups.keys(),
            key=lambda x: len(platform_groups[x]),
            reverse=True
        )[:3]
        result_str += f"📊 搜索统计：共找到 {total_results} 条相关标题，"
        if top_platforms:
            result_str += f"主要分布在{'、'.join(top_platforms[:2])}等平台\n"
        result_str += "🔗 提示: 您可以直接点击上面的链接查看原文"
        return result_str

    async def _arun(self, input_str: str) -> str:
        return self._run(input_str)


class IntelligentSentimentAnalysisTool(BaseTool):
    name = "intelligent_sentiment_analysis"
    description = "基于向量检索的智能情感分析。输入格式：'查询词|平台筛选|情感倾向|数量'，例如：'科技发展|百度,抖音|正面|10'、'疫情|所有平台|负面'、'经济政策|中性'"

    def __init__(self):
        super().__init__()

    def _run(self, input_str: str) -> str:
        try:
            parts = input_str.split('|')
            query = parts[0].strip() if len(parts) > 0 else ""
            platform_filter = parts[1].strip() if len(parts) > 1 else "all"
            sentiment_filter = parts[2].strip() if len(parts) > 2 else "all"
            top_k = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 10

            from hotsearch_analysis_agent.vector_db.sentiment_vector_manager import sentiment_vector_manager
            from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper

            platform_ids = platform_mapper.extract_platforms_from_text(platform_filter)
            platform_names = platform_mapper.format_platform_list(platform_ids)

            logger.info("🔄 强制重新加载最新数据...")
            sentiment_vector_manager.load_recent_articles(hours=24, limit=3000, force_reload=True)

            results = sentiment_vector_manager.search_sentiment_articles(
                query, platform_ids, sentiment_filter, top_k=top_k, sort_by_sentiment=True
            )

            if isinstance(results, str):
                return results

            if not results:
                logger.warning("⚠️ 搜索结果为空，尝试获取最新数据...")
                return self._get_latest_articles_fallback(platform_ids, platform_names, sentiment_filter)

            if len(results) < min(top_k, 5):
                logger.info(f"🔍 结果不足，补充最新数据...")
                fallback_results = self._get_fallback_articles(platform_ids, sentiment_filter, top_k - len(results))
                results.extend(fallback_results[:top_k - len(results)])

            analysis_result = self._analyze_with_llm(query, platform_names, sentiment_filter, results[:top_k])
            return analysis_result
        except Exception as e:
            return f"智能情感分析失败: {str(e)}"

    def _analyze_with_llm(self, query: str, platform_names: str, sentiment_filter: str, articles: List[Dict]) -> str:
        from langchain.chat_models import ChatOpenAI
        from hotsearch_analysis_agent.config.settings import LLM_CONFIG

        llm = ChatOpenAI(
            model_name=LLM_CONFIG['model_name'],
            temperature=0.3,
            max_tokens=800,
            openai_api_key=LLM_CONFIG['api_key'],
            openai_api_base=LLM_CONFIG.get('api_base'),
            openai_organization=LLM_CONFIG.get('organization')
        )

        articles_text = ""
        for i, article in enumerate(articles[:10], 1):
            articles_text += f"{i}. 【{article['平台']}】{article['标题']}\n"
            articles_text += f"   情感分数: {article['情感分数']:.3f} ({article['情感倾向']})\n"
            if article['URL'] != 'N/A':
                articles_text += f"   链接: {article['URL']}\n"
            articles_text += "\n"

        prompt = f"""请分析以下关于'{query}'的{sentiment_filter if sentiment_filter != 'all' else ''}新闻报道：
{articles_text}
分析要求：
1. 总结这些新闻报道的主要内容和主题
2. 分析情感倾向的分布情况（基于情感分数）
3. 识别出最具代表性的正面/负面/中性报道
4. 提供对这些报道的综合分析
5. 每个新闻都给出URL
请用清晰、有条理的方式进行回答，不超过500字。"""

        try:
            from langchain.schema import HumanMessage
            message = HumanMessage(content=prompt)
            response = llm([message])

            result_str = f"🧠 基于大模型的智能情感分析报告\n"
            result_str += f"🔍 分析主题: '{query}'\n"
            result_str += f"📱 分析平台: {platform_names}\n"
            result_str += f"💓 情感倾向: {sentiment_filter if sentiment_filter != 'all' else '全部情感'}\n"
            result_str += f"📊 分析样本: 前{len(articles)}条最具代表性的新闻\n"
            result_str += "=" * 50 + "\n"
            result_str += response.content.strip() + "\n"
            result_str += "=" * 50 + "\n"
            result_str += "📋 分析来源（按情感分数排序）：\n"

            for i, article in enumerate(articles[:10], 1):
                emotion_icon = "😊" if article['情感倾向'] == "正面" else "😞" if article['情感倾向'] == "负面" else "😐"
                rank_icon = "🔥" if i <= 3 else "⭐"
                result_str += f"{rank_icon} {i}. {emotion_icon} {article['标题']}\n"
                result_str += f"   📱 {article['平台']} | 💓 {article['情感倾向']} (分数: {article['情感分数']:.3f})\n"
                if article['URL'] != 'N/A':
                    result_str += f"   🔗 {article['URL']}\n"
                result_str += "\n"

            sentiment_stats = {}
            for article in articles:
                sentiment = article['情感倾向']
                sentiment_stats[sentiment] = sentiment_stats.get(sentiment, 0) + 1

            if sentiment_stats:
                result_str += "📈 情感分布统计:\n"
                for sentiment, count in sentiment_stats.items():
                    percentage = (count / len(articles)) * 100
                    emotion_icon = "😊" if sentiment == "正面" else "😞" if sentiment == "负面" else "😐"
                    result_str += f"   {emotion_icon} {sentiment}: {count} 条 ({percentage:.1f}%)\n"

            return result_str
        except Exception as e:
            logger.error(f"大模型分析失败: {str(e)}")
            return self._format_basic_analysis(query, platform_names, sentiment_filter, articles)

    def _format_basic_analysis(self, query: str, platform_names: str, sentiment_filter: str, articles: List[Dict]) -> str:
        result_str = f"🎭 智能情感分析报告\n"
        result_str += f"🔍 搜索词: '{query}'\n"
        result_str += f"📱 平台范围: {platform_names}\n"
        result_str += f"💓 情感筛选: {sentiment_filter if sentiment_filter != 'all' else '全部情感'}\n"
        result_str += f"📊 分析样本: 前{len(articles)}条最具代表性的新闻（按情感分数排序）\n"

        sentiment_stats = {}
        for article in articles:
            sentiment = article['情感倾向']
            sentiment_stats[sentiment] = sentiment_stats.get(sentiment, 0) + 1

        result_str += "📈 情感分布:\n"
        for sentiment, count in sentiment_stats.items():
            percentage = (count / len(articles)) * 100
            emotion_icon = "😊" if sentiment == "正面" else "😞" if sentiment == "负面" else "😐"
            result_str += f"   {emotion_icon} {sentiment}: {count} 条 ({percentage:.1f}%)\n"

        result_str += "\n"
        result_str += "🔍 代表性新闻分析（按情感强度排序）:\n"

        for i, article in enumerate(articles[:10], 1):
            emotion_icon = "😊" if article['情感倾向'] == "正面" else "😞" if article['情感倾向'] == "负面" else "😐"
            rank_icon = "🔥" if i <= 3 else "⭐"
            result_str += f"{rank_icon} {i}. {emotion_icon} {article['标题']}\n"
            result_str += f"   📱 {article['平台']} | 💓 {article['情感倾向']} (分数: {article['情感分数']:.3f})\n"
            if article['URL'] != 'N/A':
                result_str += f"   🔗 {article['URL']}\n"
            if article.get('关键方面'):
                result_str += f"   🎯 关键方面: {', '.join(article['关键方面'][:3])}\n"
            if article.get('情感关键词'):
                result_str += f"   🔑 情感词: {', '.join(article['情感关键词'][:3])}\n"
            result_str += "\n"

        if len(articles) >= 5:
            avg_score = sum(a['情感分数'] for a in articles) / len(articles)
            result_str += f"💡 分析洞察:\n"
            result_str += f"   • 平均情感分数: {avg_score:.3f}\n"
            if avg_score > 0.1:
                result_str += f"   • 整体情绪偏向正面\n"
            elif avg_score < -0.1:
                result_str += f"   • 整体情绪偏向负面\n"
            else:
                result_str += f"   • 整体情绪相对中性\n"

            strongest_pos = max((a for a in articles if a['情感分数'] > 0), key=lambda x: x['情感分数'], default=None)
            strongest_neg = min((a for a in articles if a['情感分数'] < 0), key=lambda x: x['情感分数'], default=None)
            if strongest_pos:
                result_str += f"   • 最正面: {strongest_pos['标题'][:30]}... (分数: {strongest_pos['情感分数']:.3f})\n"
            if strongest_neg:
                result_str += f"   • 最负面: {strongest_neg['标题'][:30]}... (分数: {strongest_neg['情感分数']:.3f})\n"

        return result_str

    async def _arun(self, input_str: str) -> str:
        return self._run(input_str)
