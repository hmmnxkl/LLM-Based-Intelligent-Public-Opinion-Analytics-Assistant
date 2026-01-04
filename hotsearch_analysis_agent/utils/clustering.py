from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np
from typing import List, Dict, Any
import jieba
import jieba.analyse

class TopicClustering:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words=['的', '了', '在', '是', '有']
        )
        jieba.initialize()

    def _extract_keywords(self, text, topK=3):
        try:
            keywords = jieba.analyse.extract_tags(text, topK=topK)
            return keywords
        except:
            return []

    def cluster_titles(self, titles: List[str], platforms: List[str], articles_data: List[Dict] = None, n_clusters: int = 5) -> Dict[str, Any]:
        if len(titles) < n_clusters:
            n_clusters = len(titles)

        enhanced_texts = []
        for title in titles:
            keywords = self._extract_keywords(title)
            enhanced_text = f"{title} {' '.join(keywords)}"
            enhanced_texts.append(enhanced_text)

        X = self.vectorizer.fit_transform(enhanced_texts)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(X)

        clusters = {}
        cluster_keywords = {}

        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
                cluster_keywords[label] = set()

            clusters[label].append(idx)

            title_keywords = self._extract_keywords(titles[idx])
            cluster_keywords[label].update(title_keywords)

        structured_clusters = {}
        for cluster_id, indices in clusters.items():
            cluster_articles = []
            for idx in indices:
                article_info = {
                    'title': titles[idx],
                    'platform': platforms[idx],
                    'index': idx
                }
                if articles_data and idx < len(articles_data):
                    article_info.update(articles_data[idx])

                cluster_articles.append(article_info)

            top_keywords = list(cluster_keywords[cluster_id])[:3]
            cluster_name = f"主题{cluster_id + 1}({'、'.join(top_keywords)})"

            structured_clusters[cluster_name] = {
                'articles': cluster_articles,
                'count': len(cluster_articles),
                'keywords': list(cluster_keywords[cluster_id])
            }

        return structured_clusters
