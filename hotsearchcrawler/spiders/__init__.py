# hotsearchcrawler/spiders/__init__.py

# 显式导入所有爬虫类
# hotsearchcrawler/spiders/__init__.py
#from .uc_spider import  UcHotSpider
from .uc_hotnew_spider import UCHotSpider
from .baidu_spider import BaiduHotSpider
from .toutiao_spider import ToutiaoHotSpider
from .wangyi_hottalk_spider import  NetEaseSpider
from.wangyi_hotnew_spider import NetEaseSpider1
from.wangyi_hotsearch_spider import NetEaseSpider2
from.wangyi_hottopic_spider import NetEaseSpider3
from .douyin_hot_spider import DouyinGeneralHotSpider
from.douyin_fun_spider import DouyinGeneralHotSpider1
from.douyin_society_spider import DouyinGeneralHotSpider2
from .toutiao_fun_spider import ToutiaoHotSpider1
from .toutiao_car_spider  import ToutiaoHotSpider2
from .toutiao_education_spider  import ToutiaoHotSpider3
from .uc_interact_spider import UCHotSpider1
from .uc_video_spider import UCVideoSpider
from .bilibili_spider import BilibiliSpider
from .ifeng_spider import IfengSpider
from .sll_spider import SllHotSpider
from .tencent_spider import TencentSpider
from .zhihu_hot_spider import ZhihuHotSpider
from .zhihu_search_spider import ZhihuSearchSpider
from .kuaishou_spider import KuaishouHotSpider
from .weibo import Weibo
from .pengpai import Pengpai
from .xiaohongshu import Xiaohongshu
from .sougou import Sougou
# 当添加其他爬虫时继续导入

