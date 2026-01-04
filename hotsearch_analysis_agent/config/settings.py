import json
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent

# 数据库配置
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'hotsearch_db'),
    'charset': 'utf8mb4',
    'port': int(os.getenv('MYSQL_PORT', 3306))
}

# 爬虫配置
SPIDER_CONFIG = {
    'project_path': str(BASE_DIR),
    'run_script': 'run_spiders.py',
    'schedule_interval': int(os.getenv('SPIDER_INTERVAL', 60))  # 分钟
}

# 平台ID映射
PLATFORM_MAPPING = {
    1: "百度热搜",
    2: "UC热榜",
    3: "头条热榜",
    4: "网易热议",
    5: "网易热闻",
    6: "网易热搜",
    7: "网易话题",
    8: "抖音热榜",
    9: "抖音娱乐榜",
    10: "抖音社会榜",
    11: "头条娱乐榜",
    12: "头条汽车榜",
    13: "头条教育榜",
    14: "快手热榜",
    15: "UC互动热榜",
    16: "UC视频热榜",
    17: "B站热搜榜",
    18: "凤凰热榜",
    19: "360搜索热点",
    20: "腾讯热点榜",
    21: "知乎热榜",
    22: "知乎热搜",
    23: "微博热搜",
    24: "小红书热榜",
    25: "搜狗热搜",
    26: "澎湃热榜"
}

# 向量数据库配置
VECTOR_DB_CONFIG = {
    'path': str(BASE_DIR / "vector_db" / "chroma_db"),
    'collection_name': 'hot_articles',
    'embedding_model': os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002')
}

# LLM配置
LLM_CONFIG = {
    'model_name': os.getenv('LLM_MODEL', 'gpt-4'),
    'temperature': float(os.getenv('LLM_TEMPERATURE', 0.1)),
    'max_tokens': int(os.getenv('LLM_MAX_TOKENS', 2000)),
    'api_key': os.getenv('OPENAI_API_KEY'),  # 从环境变量读取API密钥
    'api_base': os.getenv('OPENAI_API_BASE', None),  # 可选：自定义API端点
    'organization': os.getenv('OPENAI_ORG', None)  # 可选：组织ID
}


# # LLM配置 - 连接到远程盘古模型服务
# LLM_CONFIG = {
#     'model_name': 'pangu-embedded-7b',  # 服务器上注册的模型名称
#     'temperature': 0.2,
#     'max_tokens': 2000,
#     'api_key': 'dummy-key',  # 任意值，服务器不验证
#     'api_base': '',
#     'organization': None
# }

# 记忆配置
MEMORY_CONFIG = {
    'max_history': int(os.getenv('MAX_HISTORY', 3)),
    'memory_key': 'chat_history'
}

# 情感分析配置
SENTIMENT_CONFIG = {
    'positive_words': [
        '利好', '上涨', '成功', '突破', '创新', '增长', '优秀', '良好', '积极', '乐观',
        '胜利', '成就', '进步', '发展', '繁荣', '幸福', '满意', '称赞', '推荐', '支持'
    ],
    'negative_words': [
        '下跌', '失败', '危机', '暴跌', '问题', '困难', '挑战', '负面', '悲观', '担忧',
        '损失', '崩溃', '破产', '衰退', '痛苦', '不满', '批评', '反对', '拒绝', '危险'
    ],
    'analysis_thresholds': {
        'positive': 0.3,
        'negative': -0.3,
        'high_confidence': 0.7
    }
}

# 网络请求配置
REQUEST_CONFIG = {
    'timeout': int(os.getenv('REQUEST_TIMEOUT', 10)),
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 推送配置
PUSH_CONFIG = {
    'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'wecom_webhook': os.getenv('WECOM_WEBHOOK', ''),  # 企业微信群机器人
    'wecom_corp_id': os.getenv('WECOM_CORP_ID', ''),  # 新增：企业ID
    'wecom_agent_id': os.getenv('WECOM_AGENT_ID', ''),  # 新增：应用ID
    'wecom_secret': os.getenv('WECOM_SECRET', ''),  # 新增：应用密钥
    'wecom_user_id': os.getenv('WECOM_USER_ID', ''),  # 新增：接收用户ID（多个用|分隔）
    'email_host': os.getenv('EMAIL_HOST', ''),
    'email_port': int(os.getenv('EMAIL_PORT', 587)),
    'email_user': os.getenv('EMAIL_USER', ''),
    'email_password': os.getenv('EMAIL_PASSWORD', ''),
    'email_to': os.getenv('EMAIL_TO', '')
}


# 在settings.py中添加

# Cookies配置（从文件读取）
COOKIES_CONFIG = {
    'zhihu': {
        'description': '知乎cookies',
        'file': os.path.join(BASE_DIR, 'hotsearch_analysis_agent', 'config', 'cookies', 'zhihu.json'),
        'domains': ['zhihu.com']
    },
    'weibo': {
        'description': '微博cookies',
        'file': os.path.join(BASE_DIR, 'hotsearch_analysis_agent', 'config', 'cookies', 'weibo.json'),
        'domains': ['weibo.com']
    },
    'xiaohongshu': {
        'description': '小红书cookies',
        'file': os.path.join(BASE_DIR, 'hotsearch_analysis_agent', 'config', 'cookies', 'xiaohongshu.json'),
        'domains': ['xiaohongshu.com']
    }
}

# 平台URL匹配规则
PLATFORM_URL_PATTERNS = {
    'zhihu': [
        'zhihu.com/search',  # 知乎热搜
        'zhihu.com/question',  # 知乎问题
        'zhihu.com/topic',  # 知乎话题
        'zhihu.com/answer',  # 知乎回答
    ],
    'weibo': [
        'weibo.com',
        's.weibo.com'  # 微博搜索
    ],
    'xiaohongshu': [
        'xiaohongshu.com',
        'www.xiaohongshu.com'
    ]
}