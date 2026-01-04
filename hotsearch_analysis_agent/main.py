import os
import sys
import signal
import atexit
import multiprocessing
import logging
from hotsearch_analysis_agent.core.agent import HotSearchAgent
from hotsearch_analysis_agent.vector_db.manager import VectorDBManager
from hotsearch_analysis_agent.vector_db.title_vector_manager import TitleVectorDBManager
from hotsearch_analysis_agent.config.validator import ConfigValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logging.getLogger('scrapy').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    multiprocessing.freeze_support()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class HotSearchAnalysisSystem:
    def __init__(self):
        logger.info("🚀 初始化 HotSearchAnalysisSystem...")

        if not ConfigValidator.print_config_status():
            print("\n❌ 配置检查失败，请修复上述问题后重新启动")
            sys.exit(1)

        self.agent = None
        self.vector_db = VectorDBManager()
        self.title_vector_db = TitleVectorDBManager()

        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        logger.info(f"接收到信号 {signum}，正在清理资源...")
        self.cleanup()
        sys.exit(0)

    def startup(self):
        logger.info("🚀 启动舆情分析系统...")

        logger.info("📚 初始化向量数据库...")
        self.vector_db.initialize()
        self.title_vector_db.initialize()

        logger.info("🤖 初始化智能体...")
        try:
            self.agent = HotSearchAgent()
            logger.info("✅ 智能体初始化成功")
        except Exception as e:
            logger.error(f"❌ 智能体初始化失败: {e}")
            sys.exit(1)

        logger.info("🎉 舆情分析系统启动完成")

    def cleanup(self):
        logger.info("🧹 正在清理资源...")
        logger.info("✅ 资源清理完成")

    def process_query(self, query):
        try:
            response = self.agent.process_query(query)
            return response
        except Exception as e:
            return f"处理查询时出错: {str(e)}"

    def run(self):
        try:
            while True:
                try:
                    query = input("\n🤖 请输入查询: ").strip()
                except EOFError:
                    print("\n👋 检测到EOF，正在退出...")
                    break

                if query.lower() in ['退出', 'quit', 'exit', 'q']:
                    print("\n👋 再见！")
                    break

                if not query:
                    continue

                response = self.process_query(query)

                print("\n" + "=" * 50)
                print("📊 查询结果:")
                print("=" * 50)
                print(response)

        except KeyboardInterrupt:
            print("\n\n👋 用户中断，正在退出...")
        finally:
            self.cleanup()

if __name__ == "__main__":
    system = HotSearchAnalysisSystem()
    system.startup()

    print("\n" + "=" * 50)
    print("🎉 舆情分析系统启动完成!")
    print("=" * 50)
    print("\n您可以询问：")
    print("1. '查询百度热搜榜单'")
    print("2. '搜索关于科技的相关话题'")
    print("3. '进行话题聚类分析'")
    print("4. '分析情感倾向'")
    print("5. '基于文章内容搜索...'")
    print("6. '基于标题搜索...'")
    print("\n输入 '退出' 或 'quit' 结束对话")
    print("=" * 50)

    system.run()
