# run_spiders.py
# !/usr/bin/env python3
"""
爬虫启动脚本
支持启动单个或多个爬虫，可自定义配置
"""

import sys
import os
import argparse
import subprocess
from scrapy.crawler import \
    CrawlerProcess
from scrapy.utils.project import \
    get_project_settings

# 预定义的爬虫列表
SPIDER_MAP = {

    # 'ifeng': 'ifeng',
    #  'zhihu': 'zhihu_spider',
    # 'zhihu_search': 'zhihu_search_spider',
    #'douyin_society': 'douyin_society_hot',
    # 'douyin_hot': 'douyin_hot_hot',
    # #'douyin_fun': 'douyin_fun_hot',
    # 'toutiao': 'Toutiao_hot',
    # #'toutiao_fun': 'Toutiao_fun_hot',
    # 'toutiao_car': 'Toutiao_car_hot',
    # #'toutiao_education': 'Toutiao_education_hot',
    'wangyi': 'wangyi_hotsearch_hot',
    # #'wangyi_new': 'wangyi_hotnew_hot',
    # 'wangyi_talk': 'wangyi_hottalk_hot',
    # #'wangyi_topic': 'wangyi_hottopic_hot',
    # #'uc': 'uc_interact_hot',
    # 'uc_video': 'uc_video',
    # 'uc_new': 'uc_hotnew_hot',
    # 'baidu': 'baidu_hot',
    # 'bilibili': 'bilibili',
    # 'sll': 'sll_hot',
    # 'tencent': 'tencent_news',
    # 'kuaishou': 'kuaishou_hot',
    # 'weibo':'weibo',
    # 'Xiaohongshu':'Xiaohongshu',
    # #'sougou':'sougou',
    # #'pengpai':'pengpai'
}

# 爬虫分组
SPIDER_GROUPS = {
    'group1': [
        "ifeng",
    ],
    'group2': [
        "zhihu_spider",
        "douyin_society_hot",
        "Toutiao_fun_hot",
        "wangyi_hotsearch_hot",
        "uc_interact_hot",
        "Toutiao_hot",
        "baidu_hot",
        "wangyi_hotnew_hot",
        # "Toutiao_car_hot",
        # "Toutiao_education_hot"
    ],
    'group3': [
        "zhihu_search_spider",
        "uc_video",
        "bilibili",
        "douyin_hot_hot",
        "sll_hot",
        "tencent_news",
        "douyin_fun_hot",
        "wangyi_hottalk_hot",
        "uc_hotnew_hot",
        "kuaishou_hot",
        "wangyi_hottopic_hot",
    ]
}


class SpiderRunner:
    def __init__(self):
        self.settings = get_project_settings()
        self.process = CrawlerProcess(
            self.settings)

    def run_single_spider(
            self,
            spider_name):
        """运行单个爬虫"""
        print(
            f"开始运行爬虫: {spider_name}")
        try:
            self.process.crawl(
                spider_name)
            self.process.start()
            print(
                f"爬虫 {spider_name} 运行完成")
        except Exception as e:
            print(
                f"运行爬虫 {spider_name} 时出错: {str(e)}")

    def run_multiple_spiders(
            self,
            spider_names):
        """运行多个爬虫"""
        print(
            f"开始运行多个爬虫: {', '.join(spider_names)}")
        try:
            for spider_name in spider_names:
                self.process.crawl(
                    spider_name)
            self.process.start()
            print(
                "所有爬虫运行完成")
        except Exception as e:
            print(
                f"运行爬虫时出错: {str(e)}")

    def run_by_alias(self,
                     aliases):
        """通过别名运行爬虫"""
        spider_names = []
        for alias in aliases:
            if alias in SPIDER_MAP:
                spider_names.append(
                    SPIDER_MAP[
                        alias])
            else:
                print(
                    f"警告: 未找到别名 '{alias}' 对应的爬虫")

        if spider_names:
            self.run_multiple_spiders(
                spider_names)
        else:
            print(
                "没有有效的爬虫可运行")

    def run_by_group(self,
                     group_names):
        """通过分组运行爬虫"""
        spider_names = []
        for group_name in group_names:
            if group_name in SPIDER_GROUPS:
                spider_names.extend(
                    SPIDER_GROUPS[
                        group_name])
                print(
                    f"已添加分组 '{group_name}' 的爬虫")
            else:
                print(
                    f"警告: 未找到分组 '{group_name}'")

        if spider_names:
            # 去重
            spider_names = list(
                set(spider_names))
            self.run_multiple_spiders(
                spider_names)
        else:
            print(
                "没有有效的爬虫可运行")


def main():
    parser = argparse.ArgumentParser(
        description='爬虫启动脚本')
    parser.add_argument(
        'spiders',
        nargs='*',
        help='要运行的爬虫名称或别名'
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='列出所有可用的爬虫和别名'
    )
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='运行所有爬虫'
    )
    parser.add_argument(
        '--aliases',
        nargs='+',
        help='通过别名运行爬虫 (例如: kuaishou weibo zhihu)'
    )
    parser.add_argument(
        '--groups',
        nargs='+',
        choices=['group1',
                 'group2',
                 'group3'],
        help='通过分组运行爬虫 (例如: group1 group2)'
    )
    parser.add_argument(
        '--list-groups',
        action='store_true',
        help='列出所有爬虫分组'
    )

    args = parser.parse_args()

    runner = SpiderRunner()

    if args.list:
        print(
            "可用的爬虫别名:")
        for alias, spider_name in SPIDER_MAP.items():
            print(
                f"  {alias}: {spider_name}")
        return

    if args.list_groups:
        print(
            "可用的爬虫分组:")
        for group_name, spiders in SPIDER_GROUPS.items():
            print(
                f"  {group_name}: {', '.join(spiders)}")
        return

    if args.all:
        # 运行所有预定义的爬虫
        all_spiders = list(
            SPIDER_MAP.values())
        runner.run_multiple_spiders(
            all_spiders)
        return

    if args.aliases:
        runner.run_by_alias(
            args.aliases)
        return

    if args.groups:
        runner.run_by_group(
            args.groups)
        return

    if args.spiders:
        # 直接运行指定的爬虫名称
        runner.run_multiple_spiders(
            args.spiders)
        return

    # 如果没有参数，显示帮助信息
    parser.print_help()


if __name__ == '__main__':
    # 添加项目路径到Python路径
    project_path = os.path.dirname(
        os.path.abspath(
            __file__))
    sys.path.insert(0,
                    project_path)

    main()