import jieba
import jieba.analyse
import re
from typing import Dict, List, Tuple
from collections import Counter
import math

class AdvancedSentimentAnalyzer:
    def __init__(self):
        self.positive_words = self._load_sentiment_words('positive')
        self.negative_words = self._load_sentiment_words('negative')
        self.intensifiers = self._load_intensifiers()
        self.negators = self._load_negators()
        self.aspect_keywords = self._load_aspect_keywords()

    def _load_sentiment_words(self, sentiment_type):
        base_words = {
            'positive': {
                '利好', '上涨', '成功', '突破', '创新', '增长', '优秀', '良好', '积极', '乐观', '胜利', '成就', '进步', '发展', '繁荣', '幸福', '满意', '称赞', '推荐', '支持', '突破', '领先', '卓越', '精彩', '完美', '强大', '稳健', '可靠', '安全', '便捷'
            },
            'negative': {
                '下跌', '失败', '危机', '暴跌', '问题', '困难', '挑战', '负面', '悲观', '担忧', '损失', '下跌', '崩溃', '破产', '衰退', '痛苦', '不满', '批评', '反对', '拒绝', '危险', '威胁', '冲突', '争议', '丑闻', '腐败', '欺诈', '违法', '违规', '侵权'
            }
        }
        return base_words[sentiment_type]

    def _load_intensifiers(self):
        return {
            '极其', '非常', '十分', '特别', '相当', '比较', '稍微', '略微', '完全', '绝对', '彻底', '强烈', '高度', '深度', '严重'
        }

    def _load_negators(self):
        return {
            '不', '没', '未', '无', '非', '勿', '莫', '别', '休', '免'
        }

    def _load_aspect_keywords(self):
        return {
            '经济': ['价格', '成本', '利润', '收入', '市场', '经济', '金融', '投资'],
            '技术': ['技术', '创新', '研发', '科技', '智能', '数字', '网络', '系统'],
            '社会': ['社会', '民生', '公众', '群众', '人民', '公民', '社区', '群体'],
            '政治': ['政府', '政策', '法律', '法规', '监管', '治理', '领导', '国家'],
            '环境': ['环境', '生态', '污染', '气候', '能源', '资源', '可持续', '绿色']
        }

    def enhanced_analyze(self, text: str) -> Dict[str, any]:
        words = list(jieba.cut(text))

        base_score = self._calculate_base_sentiment(words)
        intensity_score = self._calculate_intensity(words, base_score)
        aspects = self._extract_aspects(text)
        keywords = jieba.analyse.extract_tags(text, topK=10)
        final_score = self._normalize_score(base_score * intensity_score)

        return {
            'score': final_score,
            'label': self._get_sentiment_label(final_score),
            'intensity': intensity_score,
            'aspects': aspects,
            'keywords': keywords,
            'confidence': self._calculate_confidence(words, final_score)
        }

    def _calculate_base_sentiment(self, words: List[str]) -> float:
        score = 0
        for i, word in enumerate(words):
            if word in self.positive_words:
                multiplier = 1
                if i > 0 and words[i - 1] in self.negators:
                    multiplier = -1
                intensity = 1
                if i > 0 and words[i - 1] in self.intensifiers:
                    intensity = 1.5
                score += 1 * multiplier * intensity

            elif word in self.negative_words:
                multiplier = -1
                if i > 0 and words[i - 1] in self.negators:
                    multiplier = 1
                intensity = 1
                if i > 0 and words[i - 1] in self.intensifiers:
                    intensity = 1.5
                score += 1 * multiplier * intensity

        return math.tanh(score / 10)

    def _calculate_intensity(self, words: List[str], base_score: float) -> float:
        intensity_count = sum(1 for word in words if word in self.intensifiers)
        return 1.0 + (intensity_count * 0.2)

    def _extract_aspects(self, text: str) -> List[str]:
        aspects_found = []
        for aspect, keywords in self.aspect_keywords.items():
            if any(keyword in text for keyword in keywords):
                aspects_found.append(aspect)
        return aspects_found

    def _normalize_score(self, score: float) -> float:
        return max(-1.0, min(1.0, score))

    def _get_sentiment_label(self, score: float) -> str:
        if score > 0.05:
            return "正面"
        elif score < -0.05:
            return "负面"
        else:
            return "中性"

    def _calculate_confidence(self, words: List[str], score: float) -> float:
        sentiment_words_count = sum(1 for word in words if word in self.positive_words or word in self.negative_words)
        total_words = len(words)

        if total_words == 0:
            return 0.0

        base_confidence = sentiment_words_count / total_words
        intensity_confidence = min(1.0, sentiment_words_count / 5)

        return (base_confidence * 0.6 + intensity_confidence * 0.4)
