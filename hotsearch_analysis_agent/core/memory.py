# memory.py
from typing import List, Dict, \
    Any
from langchain.schema import \
    BaseMessage
from hotsearch_analysis_agent.config.settings import \
    MEMORY_CONFIG
import re



class ConversationMemory:
    def __init__(self):
        self.max_history = MEMORY_CONFIG['max_history']
        self.chat_history: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str, metadata: Dict = None):
        """添加消息到记忆"""
        message = {
            'role': role,
            'content': content,
            'metadata': metadata or {}
        }
        self.chat_history.append(message)

        # 保持最多max_history轮对话
        if len(self.chat_history) > self.max_history * 2:
            self.chat_history = self.chat_history[-(self.max_history * 2):]

    def get_recent_history(self, n: int = None) -> List[Dict]:
        """获取最近的对话历史"""
        if n is None:
            n = self.max_history
        return self.chat_history[-(n * 2):] if len(self.chat_history) >= n * 2 else self.chat_history

    def clear_old_memory(self):
        """清理旧记忆"""
        if len(self.chat_history) > self.max_history * 2:
            self.chat_history = self.chat_history[-(self.max_history * 2):]

    def get_context(self) -> str:
        """获取对话上下文"""
        recent_history = self.get_recent_history()
        context = "最近的对话历史:\n"
        for msg in recent_history:
            context += f"{msg['role']}: {msg['content']}\n"
        return context

    # 在 memory.py 中修改 extract_recent_news_references 方法

    def extract_recent_news_references(
            self) -> List[
        Dict]:
        """从对话历史中提取最近提到的新闻信息 - 增强版，提取完整标题和URL"""
        recent_history = self.get_recent_history(
            5)
        news_references = []

        for msg in recent_history:
            if msg[
                'role'] == 'assistant':
                content = msg[
                    'content']
                lines = content.split(
                    '\n')
                current_platform = None
                current_url = None

                for line in lines:
                    line = line.strip()

                    # 检测平台标题 - 适配实际格式
                    if '🏆' in line or '：' in line:
                        platform_match = re.search(
                            r'([^\s：]+)\s*[：:]',
                            line)
                        if platform_match:
                            platform_name = platform_match.group(
                                1)
                            # 规范化平台名称
                            if '抖音' in platform_name:
                                current_platform = '抖音'
                            elif '头条' in platform_name:
                                current_platform = '头条'
                            elif '百度' in platform_name:
                                current_platform = '百度'
                            # 其他平台映射...
                            else:
                                current_platform = platform_name

                    # 检测URL行
                    elif line.startswith(
                            '链接:'):
                        current_url = line.replace(
                            '链接:',
                            '').strip()

                    # 检测新闻条目 - 适配各种格式
                    elif re.match(
                            r'^\d+\.\s',
                            line) or re.match(
                            r'^\[\w+\d+\]',
                            line):
                        if current_platform:
                            # 提取标题，移除可能的排名和图标
                            title_match = re.search(
                                r'(?:\d+\.\s*|\[\w+\d+\]\s*)([^🔗链接].+?)(?:\s*排名\d+)?\s*$',
                                line)
                            if title_match:
                                title = title_match.group(
                                    1).strip()

                                news_info = {
                                    'platform': current_platform,
                                    'title': title,
                                    'original_title': title,
                                    'url': current_url if current_url else None,
                                    'content': line,
                                    'full_context': f"{current_platform}: {title}" + (
                                        f" | 链接: {current_url}" if current_url else "")
                                }
                                news_references.append(
                                    news_info)
                                current_url = None  # 重置URL

        return news_references