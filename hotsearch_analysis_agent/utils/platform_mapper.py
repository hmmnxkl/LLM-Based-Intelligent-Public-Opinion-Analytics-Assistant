import re
from typing import Dict, List, Optional, Tuple
from hotsearch_analysis_agent.config.settings import PLATFORM_MAPPING

class PlatformMapper:

    def __init__(self):
        self.platform_mapping = PLATFORM_MAPPING
        self.name_to_id = self._create_name_mapping()
        self.keywords = self._create_keyword_mapping()

    def _create_name_mapping(self) -> Dict[str, int]:
        mapping = {}
        for pid, name in self.platform_mapping.items():
            mapping[name] = pid
            if "百度" in name:
                mapping["百度"] = pid
                mapping["百度热搜"] = pid
                mapping["baidu"] = pid
            elif "抖音" in name:
                mapping["抖音"] = pid
                if "娱乐" in name:
                    mapping["抖音娱乐"] = pid
                    mapping["抖音娱乐榜"] = pid
                elif "社会" in name:
                    mapping["抖音社会"] = pid
                    mapping["抖音社会榜"] = pid
                else:
                    mapping["抖音热榜"] = pid
            elif "头条" in name:
                mapping["头条"] = pid
                mapping["今日头条"] = pid
                if "娱乐" in name:
                    mapping["头条娱乐"] = pid
                    mapping["头条娱乐榜"] = pid
                elif "汽车" in name:
                    mapping["头条汽车"] = pid
                    mapping["头条汽车榜"] = pid
                elif "教育" in name:
                    mapping["头条教育"] = pid
                    mapping["头条教育榜"] = pid
                else:
                    mapping["头条热榜"] = pid
            elif "网易" in name:
                mapping["网易"] = pid
                if "热议" in name:
                    mapping["网易热议"] = pid
                elif "热闻" in name:
                    mapping["网易热闻"] = pid
                elif "热搜" in name:
                    mapping["网易热搜"] = pid
                elif "话题" in name:
                    mapping["网易话题"] = pid
            elif "知乎" in name:
                mapping["知乎"] = pid
                mapping["知乎热榜"] = pid
            elif "B站" in name:
                mapping["B站"] = pid
                mapping["哔哩哔哩"] = pid
                mapping["bilibili"] = pid
            elif "快手" in name:
                mapping["快手"] = pid
                mapping["快手热榜"] = pid
            elif "UC" in name:
                mapping["UC"] = pid
                if "互动" in name:
                    mapping["UC互动"] = pid
                elif "视频" in name:
                    mapping["UC视频"] = pid
                else:
                    mapping["UC热榜"] = pid
            elif "凤凰" in name:
                mapping["凤凰"] = pid
                mapping["凤凰热榜"] = pid
            elif "360" in name:
                mapping["360"] = pid
                mapping["360搜索"] = pid
            elif "腾讯" in name:
                mapping["腾讯"] = pid
                mapping["腾讯热点"] = pid
        return mapping

    def _create_keyword_mapping(self) -> Dict[str, List[int]]:
        return {
            "百度": [1],
            "抖音": [8, 9, 10],
            "头条": [3, 11, 12, 13],
            "网易": [4, 5, 6, 7],
            "知乎": [21, 22],
            "B站": [17],
            "哔哩哔哩": [17],
            "快手": [14],
            "UC": [2, 15, 16],
            "凤凰": [18],
            "360": [19],
            "腾讯": [20],
            "微博": [23],
            "weibo": [23],
            "小红书": [24],
            "xiaohongshu": [24],
            "搜狗": [25],
            "sogou": [25],
            "澎湃": [26],
            "thepaper": [26],
            "所有": list(PLATFORM_MAPPING.keys()),
            "全部": list(PLATFORM_MAPPING.keys()),
            "all": list(PLATFORM_MAPPING.keys()),
            "every": list(PLATFORM_MAPPING.keys())
        }

    def extract_platforms_from_text(self, text: str) -> List[int]:
        if not text or text.strip() == "":
            return list(PLATFORM_MAPPING.keys())

        text_lower = text.lower()
        found_platforms = set()

        for name, pid in self.name_to_id.items():
            if name.lower() in text_lower:
                found_platforms.add(pid)

        for keyword, pids in self.keywords.items():
            if keyword.lower() in text_lower:
                found_platforms.update(pids)

        numbers = re.findall(r'\b\d+\b', text)
        for num in numbers:
            pid = int(num)
            if pid in PLATFORM_MAPPING:
                found_platforms.add(pid)

        if not found_platforms:
            return list(PLATFORM_MAPPING.keys())

        return list(found_platforms)

    def get_platform_name(self, platform_id: int) -> str:
        return self.platform_mapping.get(platform_id, f"平台{platform_id}")

    def format_platform_list(self, platform_ids: List[int]) -> str:
        if len(platform_ids) == len(PLATFORM_MAPPING):
            return "所有平台"

        names = [self.get_platform_name(pid) for pid in platform_ids]
        if len(names) <= 3:
            return "、".join(names)
        else:
            return "、".join(names[:3]) + f" 等{len(names)}个平台"

platform_mapper = PlatformMapper()
