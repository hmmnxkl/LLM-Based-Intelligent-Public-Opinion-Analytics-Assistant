import time
import subprocess
import sys
import os
import logging
import signal
import threading
import json
from datetime import datetime
import psutil

# 状态文件路径
STATE_FILE = os.path.join(
    os.path.dirname(
        os.path.abspath(
            __file__)),
    'spider_state.json'
)


class SimpleSpiderState:
    """简化的爬虫状态管理"""

    def __init__(self):
        self.cycle = 0  # 当前轮次
        self.index = 0  # 当前爬虫索引
        self.spiders = [
            # 爬虫列表（固定顺序）
            "ifeng",
            "wangyi_hotnew_hot",
            "weibo",
            "sougou",
            "uc_video",
            "Toutiao_fun_hot",
            "zhihu_spider",
            "wangyi_hotsearch_hot",
            "douyin_society_hot",
            "uc_interact_hot",
            "Toutiao_hot",
            "baidu_hot",
            "xiaohongshu",
            "zhihu_search_spider",
            "bilibili",
            "douyin_hot_hot",
            "sll_hot",
            "Toutiao_education_hot",
            "tencent_news",
            "douyin_fun_hot",
            "wangyi_hottalk_hot",
            "uc_hotnew_hot",
            "pengpai",
            "kuaishou_hot",
            "wangyi_hottopic_hot",
            "Toutiao_car_hot"
        ]
        self.last_update = datetime.now().isoformat()

    def save(self):
        """保存状态"""
        try:
            state = {
                'cycle': self.cycle,
                'index': self.index,
                'last_update': datetime.now().isoformat(),
                'spider_count': len(
                    self.spiders)
            }
            with open(
                    STATE_FILE,
                    'w',
                    encoding='utf-8') as f:
                json.dump(
                    state, f,
                    indent=2,
                    ensure_ascii=False)
            return True
        except Exception:
            return False

    def load(self):
        """加载状态"""
        try:
            if os.path.exists(
                    STATE_FILE):
                with open(
                        STATE_FILE,
                        'r',
                        encoding='utf-8') as f:
                    state = json.load(
                        f)
                    self.cycle = state.get(
                        'cycle',
                        0)
                    self.index = state.get(
                        'index',
                        0)
                return True
        except Exception:
            pass
        return False

    def next(self):
        """移动到下一个爬虫"""
        self.index += 1
        if self.index >= len(
                self.spiders):
            self.cycle += 1
            self.index = 0
        self.save()

    def get_current_spider(
            self):
        """获取当前爬虫"""
        if self.index < len(
                self.spiders):
            return \
            self.spiders[
                self.index]
        return None


# 配置日志
def setup_logging():
    log_dir = os.path.join(
        os.path.dirname(
            os.path.abspath(
                __file__)),
        'logs')
    if not os.path.exists(
            log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(
        log_dir,
        f'spider_{datetime.now().strftime("%Y%m%d")}.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                log_file,
                encoding='utf-8'),
            logging.StreamHandler(
                sys.stdout)
        ]
    )

    # 设置Scrapy日志级别
    logging.getLogger(
        'scrapy').setLevel(
        logging.WARNING)

    return logging.getLogger()


logger = setup_logging()


def run_spider_simple(
        spider_name,
        timeout=300):
    """执行爬虫，使用Scrapy统一的日志系统"""
    try:
        project_dir = os.path.dirname(
            os.path.abspath(
                __file__))

        logger.info(
            f"开始执行: {spider_name}")

        # 设置环境变量
        env = os.environ.copy()

        # 构建命令，使用Scrapy的日志配置
        cmd = [
            sys.executable,
            "-m", "scrapy",
            "crawl",
            spider_name
        ]


        start_time = time.time()

        # 执行命令
        process = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL,

            env=env
        )

        try:
            # 等待进程结束
            process.wait(
                timeout=timeout)
            elapsed = time.time() - start_time

            if process.returncode == 0:
                logger.info(
                    f"执行成功: {spider_name}, 耗时: {elapsed:.1f}秒")
                return True, elapsed
            else:
                logger.warning(
                    f"执行失败: {spider_name}, 返回码: {process.returncode}, 耗时: {elapsed:.1f}秒")
                return False, elapsed

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            logger.warning(
                f"执行超时: {spider_name}, 已运行: {elapsed:.1f}秒")

            # 终止进程
            process.terminate()
            try:
                process.wait(
                    timeout=5)
            except:
                process.kill()

            return False, elapsed

    except Exception as e:
        logger.error(
            f"执行异常: {spider_name}, 错误: {str(e)}")
        return False, 0


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info(
        "启动连续爬虫执行器")
    logger.info(
        f"工作目录: {os.getcwd()}")
    logger.info(
        f"Python路径: {sys.executable}")
    logger.info("=" * 60)

    # 初始化状态
    state = SimpleSpiderState()
    if state.load():
        logger.info(
            f"加载状态: 第{state.cycle + 1}轮, 第{state.index + 1}/{len(state.spiders)}个爬虫")
    else:
        logger.info(
            "新启动: 从头开始执行")

    log_dir = os.path.join(
        os.path.dirname(
            os.path.abspath(
                __file__)),
        'logs')
    if not os.path.exists(
            log_dir):
        os.makedirs(log_dir)
        logger.info(
            f"创建目录: {log_dir}")

    # 信号处理
    def signal_handler(sig,
                       frame):
        logger.info(
            f"接收到信号 {sig}, 保存状态后退出...")
        state.save()
        sys.exit(0)

    signal.signal(
        signal.SIGINT,
        signal_handler)
    signal.signal(
        signal.SIGTERM,
        signal_handler)

    # 主循环
    error_count = 0
    max_errors = 10

    while error_count < max_errors:
        try:
            # 无限循环执行
            while True:
                cycle_start = time.time()
                logger.info(
                    f"开始第 {state.cycle + 1} 轮执行")

                # 执行当前轮次的所有爬虫
                for i in range(
                        state.index,
                        len(state.spiders)):
                    spider_name = \
                    state.spiders[
                        i]

                    logger.info(
                        f"[{state.cycle + 1}.{i + 1}/{len(state.spiders)}] 执行爬虫: {spider_name}")

                    # 执行爬虫
                    success, duration = run_spider_simple(
                        spider_name,
                        300)

                    # 更新状态
                    state.next()

                    # 爬虫间间隔
                    if i < len(
                            state.spiders) - 1:
                        time.sleep(
                            2)

                # 一轮完成，重置索引
                state.index = 0
                state.cycle += 1
                state.save()

                cycle_time = time.time() - cycle_start
                logger.info(
                    f"第 {state.cycle} 轮完成, 耗时: {cycle_time / 60:.1f}分钟")
                logger.info(
                    f"等待3分钟后开始下一轮...")
                time.sleep(
                    180)  # 等待3分钟

        except KeyboardInterrupt:
            logger.info(
                "用户中断, 保存状态后退出...")
            state.save()
            break

        except Exception as e:
            error_count += 1
            logger.error(
                f"发生错误 ({error_count}/{max_errors}): {e}")

            # 保存当前状态
            state.save()

            # 等待后重试
            wait_time = min(
                60 * error_count,
                300)  # 最多等待5分钟
            logger.info(
                f"等待 {wait_time} 秒后重试...")
            time.sleep(
                wait_time)

    if error_count >= max_errors:
        logger.error(
            f"达到最大错误次数 {max_errors}, 程序退出")
    else:
        logger.info(
            "程序正常退出")


if __name__ == "__main__":
    main()