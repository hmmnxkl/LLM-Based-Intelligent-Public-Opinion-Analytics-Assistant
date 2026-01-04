import jieba
import jieba.analyse
from typing import Dict, List
from hotsearch_analysis_agent.config.settings import SENTIMENT_CONFIG

class SentimentAnalyzer:
    def __init__(self):
        self.positive_words = set(SENTIMENT_CONFIG['positive_words'])
        self.negative_words = set(SENTIMENT_CONFIG['negative_words'])

    def analyze(self, text: str) -> str:
        words = jieba.lcut(text)
        positive_count = sum(1 for word in words if word in self.positive_words)
        negative_count = sum(1 for word in words if word in self.negative_words)

        if positive_count > negative_count:
            return "正面"
        elif negative_count > positive_count:
            return "负面"
        else:
            return "中性"
