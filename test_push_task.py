# test_push_task.py
import requests
import json
import time
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(
    os.path.dirname(
        os.path.abspath(
            __file__)))


class PushTaskTester:
    def __init__(self,
                 base_url="http://localhost:5000"):
        self.base_url = base_url
        self.test_prompts = [
            "关于特朗普和美国相关的消息"

        ]

    def test_crawler_status(
            self):
        """测试爬虫状态"""
        try:
            response = requests.get(
                f"{self.base_url}/api/crawler/status")
            data = response.json()
            print(
                f"爬虫状态: {'运行中' if data.get('running') else '未运行'}")
            return data.get(
                'running',
                False)
        except Exception as e:
            print(
                f"检查爬虫状态失败: {e}")
            return False

    def start_crawler(self):
        """启动爬虫"""
        try:
            response = requests.post(
                f"{self.base_url}/api/crawler/start")
            data = response.json()
            print(
                f"启动爬虫结果: {data}")
            return data.get(
                'status') == 'success'
        except Exception as e:
            print(
                f"启动爬虫失败: {e}")
            return False

    def create_push_task(self,
                         user_prompt,
                         push_time=None):
        """创建推送任务"""
        try:
            # 如果没有指定时间，使用当前时间+2分钟
            if not push_time:
                from datetime import \
                    datetime, \
                    timedelta
                now_plus_2min = datetime.now() + timedelta(
                    minutes=2)
                push_time = now_plus_2min.strftime(
                    "%H:%M")

            payload = {
                "user_prompt": user_prompt,
                "push_time": push_time
            }

            response = requests.post(
                f"{self.base_url}/api/push_tasks",
                json=payload,
                headers={
                    'Content-Type': 'application/json'}
            )
            data = response.json()
            print(
                f"创建推送任务 '{user_prompt}' 结果: {data}")
            return data
        except Exception as e:
            print(
                f"创建推送任务失败: {e}")
            return {
                "status": "error",
                "message": str(
                    e)}

    def get_all_tasks(self):
        """获取所有推送任务"""
        try:
            response = requests.get(
                f"{self.base_url}/api/push_tasks")
            data = response.json()
            print(
                f"当前推送任务: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return data
        except Exception as e:
            print(
                f"获取推送任务失败: {e}")
            return {
                "status": "error",
                "message": str(
                    e)}

    def delete_task(self,
                    task_id):
        """删除推送任务"""
        try:
            response = requests.delete(
                f"{self.base_url}/api/push_tasks/{task_id}")
            data = response.json()
            print(
                f"删除任务 {task_id} 结果: {data}")
            return data
        except Exception as e:
            print(
                f"删除任务失败: {e}")
            return {
                "status": "error",
                "message": str(
                    e)}

    def test_chat_interface(
            self, message):
        """测试聊天接口"""
        try:
            payload = {
                "message": message
            }
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={
                    'Content-Type': 'application/json'}
            )
            data = response.json()
            print(
                f"聊天接口测试结果: {data.get('status')}")
            if data.get(
                    'status') == 'success':
                print(
                    f"AI回复: {data.get('response', '')[:100]}...")
            return data
        except Exception as e:
            print(
                f"聊天接口测试失败: {e}")
            return {
                "status": "error",
                "message": str(
                    e)}

    def run_quick_test(self):
        """运行快速测试"""
        print("=" * 50)
        print(
            "热点推送功能快速测试")
        print("=" * 50)

        # 1. 检查服务是否可用
        print(
            "\n1. 检查服务状态...")
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=5)
            if response.status_code == 200:
                print(
                    "✅ 服务正常运行")
            else:
                print(
                    f"❌ 服务异常，状态码: {response.status_code}")
                return False
        except Exception as e:
            print(
                f"❌ 无法连接到服务: {e}")
            print(
                "请确保Flask应用正在运行: python app.py")
            return False

        # 2. 检查爬虫状态
        print(
            "\n2. 检查爬虫状态...")
        crawler_running = self.test_crawler_status()

        if not crawler_running:
            print(
                "启动爬虫中...")
            if not self.start_crawler():
                print(
                    "❌ 爬虫启动失败，但继续测试推送任务创建...")
            else:
                # 等待爬虫启动
                time.sleep(3)

        # 3. 创建多个测试推送任务
        print(
            "\n3. 创建测试推送任务...")
        from datetime import \
            datetime, \
            timedelta

        # 创建立即执行的任务（当前时间+12分钟）
        now_plus_1min = datetime.now() + timedelta(
            minutes=11)
        immediate_time = now_plus_1min.strftime(
            "%H:%M")

        created_tasks = []
        for i, prompt in enumerate(
                self.test_prompts[
                :2]):  # 只创建前2个避免过多
            print(
                f"创建任务 {i + 1}: {prompt}")
            result = self.create_push_task(
                prompt,
                immediate_time)
            if result.get(
                    'status') == 'success':
                created_tasks.append(
                    {
                        'task_id': result.get(
                            'task_id'),
                        'prompt': prompt
                    })
                print(
                    f"✅ 任务创建成功: {result.get('task_id')}")
            else:
                print(
                    f"❌ 任务创建失败: {result.get('message')}")

            time.sleep(
                1)  # 避免请求过快

        # 4. 验证任务创建
        print(
            "\n4. 验证任务创建...")
        tasks_data = self.get_all_tasks()
        if tasks_data.get(
                'status') == 'success':
            task_count = len(
                tasks_data.get(
                    'tasks',
                    []))
            print(
                f"✅ 当前共有 {task_count} 个活跃推送任务")
        else:
            print(
                "❌ 获取任务列表失败")

        # 5. 测试聊天接口
        print(
            "\n5. 测试聊天接口...")
        chat_result = self.test_chat_interface(
            "今天有什么热点新闻？")

        # 6. 显示测试摘要
        print("\n" + "=" * 50)
        print("测试摘要")
        print("=" * 50)
        print(
            f"✅ 服务状态: 正常")
        print(
            f"✅ 爬虫状态: {'运行中' if crawler_running else '未运行'}")
        print(
            f"✅ 创建任务: {len(created_tasks)} 个")
        print(
            f"✅ 聊天接口: {'正常' if chat_result.get('status') == 'success' else '异常'}")

        if created_tasks:
            print(
                f"\n创建的推送任务将在 {immediate_time} 执行")
            print(
                "请观察控制台输出和推送渠道是否收到消息")

        return True

    def cleanup_test_tasks(
            self):
        """清理测试任务"""
        print(
            "\n清理测试任务...")
        tasks_data = self.get_all_tasks()
        if tasks_data.get(
                'status') == 'success':
            for task in tasks_data.get(
                    'tasks',
                    []):
                if any(
                        prompt in task.get(
                                'user_prompt',
                                '')
                        for
                        prompt
                        in
                        self.test_prompts):
                    self.delete_task(
                        task[
                            'task_id'])


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='热点推送功能测试脚本')
    parser.add_argument(
        '--url',
        default='http://localhost:5000',
        help='Flask应用URL')
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='清理测试任务')

    args = parser.parse_args()

    tester = PushTaskTester(
        base_url=args.url)

    if args.cleanup:
        tester.cleanup_test_tasks()
    else:
        tester.run_quick_test()


if __name__ == "__main__":
    main()