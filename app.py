import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import threading
import time
import subprocess
import os
import sys
import signal
import atexit
from hotsearch_analysis_agent.main import HotSearchAnalysisSystem
import pymysql
import json
import uuid
from datetime import datetime
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from hotsearch_analysis_agent.utils.content_extractor import ContentExtractor

app = Flask(__name__)
app.secret_key = 'hotsearch_analysis_system_secret_key'
CORS(app)

# Global variables
crawler_process = None
crawler_thread = None
crawler_running = False
system_instance = None

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Push task storage
push_tasks = {}

HISTORY_FILE = 'chat_history.json'


class HistoryManager:
    """Manages chat history."""

    def __init__(self, history_file=HISTORY_FILE):
        self.history_file = history_file
        self._ensure_history_file()

    def _ensure_history_file(self):
        """Ensures the history file exists."""
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def save_conversation(self, user_message, bot_response, conversation_id=None):
        """Saves a complete conversation entry."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            if conversation_id is None:
                conversation_id = str(uuid.uuid4())

            # Check for duplicates within a short timeframe
            existing_record = None
            for i, record in enumerate(history):
                if (record.get('user_message') == user_message and
                        record.get('bot_response') == bot_response and
                        (datetime.now() - datetime.fromisoformat(record['timestamp'])).seconds < 600):
                    existing_record = i
                    break

            conversation_record = {
                'id': conversation_id if existing_record is None else history[existing_record]['id'],
                'user_message': user_message,
                'bot_response': bot_response,
                'timestamp': datetime.now().isoformat(),
                'display_text': user_message[:50] + ('...' if len(user_message) > 50 else '')
            }

            if existing_record is not None:
                history[existing_record] = conversation_record
            else:
                history.insert(0, conversation_record)

            # Keep only the last 100 records
            if len(history) > 100:
                history = history[:100]

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            return conversation_id if existing_record is None else history[existing_record]['id']
        except Exception as e:
            print(f"Failed to save conversation: {str(e)}")
            return None

    def load_history(self):
        """Loads all history records."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return history
        except Exception as e:
            print(f"Failed to load history: {str(e)}")
            return []

    def delete_conversation(self, conversation_id):
        """Deletes a specific conversation record."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            new_history = [conv for conv in history if conv.get('id') != conversation_id]

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(new_history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Failed to delete conversation: {str(e)}")
            return False

    def clear_all_history(self):
        """Clears all history records."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Failed to clear history: {str(e)}")
            return False


history_manager = HistoryManager()


@app.route('/api/history/save_conversation', methods=['POST'])
def save_conversation():
    try:
        data = request.json
        if not data or 'user_message' not in data or 'bot_response' not in data:
            return jsonify({"status": "error", "message": "Invalid data"})

        conversation_id = data.get('conversation_id')
        saved_id = history_manager.save_conversation(data['user_message'], data['bot_response'], conversation_id)

        if saved_id:
            return jsonify({"status": "success", "message": "Conversation saved", "conversation_id": saved_id})
        else:
            return jsonify({"status": "error", "message": "Failed to save"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error saving: {str(e)}"})


@app.route('/api/history/load', methods=['GET'])
def load_history():
    try:
        history = history_manager.load_history()
        return jsonify({"status": "success", "history": history})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error loading: {str(e)}"})


@app.route('/api/history/delete/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    try:
        success = history_manager.delete_conversation(conversation_id)
        if success:
            return jsonify({"status": "success", "message": "Deleted"})
        else:
            return jsonify({"status": "error", "message": "Deletion failed"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error deleting: {str(e)}"})


@app.route('/api/history/delete_all', methods=['DELETE'])
def delete_all_conversations():
    try:
        success = history_manager.clear_all_history()
        if success:
            return jsonify({"status": "success", "message": "All deleted"})
        else:
            return jsonify({"status": "error", "message": "Deletion failed"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error deleting all: {str(e)}"})


class CrawlerManager:
    def __init__(self):
        self.process = None
        self.running = False
        self.pid = None
        self.log_file = None
        self.log_thread = None

    def start_crawlers(self):
        """Starts the crawler process."""
        if self.running:
            return {"status": "error", "message": "Already running"}

        try:
            project_dir = os.path.dirname(os.path.abspath(__file__))
            crawler_script = os.path.join(project_dir, 'run_spiders.py')

            log_dir = os.path.join(project_dir, 'logs')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(log_dir, f'crawler_{timestamp}.log')

            with open(self.log_file, 'w', encoding='utf-8') as log_f:
                self.process = subprocess.Popen(
                    [sys.executable, crawler_script],
                    cwd=project_dir,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    universal_newlines=True
                )

            self.pid = self.process.pid
            self.running = True
            self._start_log_monitor()

            return {"status": "success", "message": f"Started (PID: {self.pid})", "pid": self.pid, "log_file": self.log_file}
        except Exception as e:
            print(f"Failed to start crawler: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Start failed: {str(e)}"}

    def _start_log_monitor(self):
        """Monitors the crawler process."""
        def monitor_log():
            try:
                if self.process:
                    returncode = self.process.wait(timeout=5)
                    if returncode is not None:
                        print(f"Crawler exited, code: {returncode}")
                        self.running = False
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                print(f"Log monitor error: {e}")

        self.log_thread = threading.Thread(target=monitor_log, daemon=True)
        self.log_thread.start()

    def stop_crawlers(self):
        """Stops the crawler process."""
        if not self.running or not self.process:
            return {"status": "error", "message": "Not running"}

        try:
            print(f"Stopping crawler (PID: {self.pid})...")
            self.process.terminate()

            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("Force kill...")
                self.process.kill()
                self.process.wait(timeout=5)

            self.running = False
            self.process = None
            self.pid = None
            return {"status": "success", "message": "Stopped"}
        except Exception as e:
            print(f"Stop failed: {e}")
            if self.pid:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                except:
                    pass
            self.running = False
            self.process = None
            self.pid = None
            return {"status": "error", "message": f"Stop error: {str(e)}"}

    def get_crawler_status(self):
        """Returns crawler status."""
        if not self.running or not self.process:
            return {"running": False, "pid": None, "log_file": self.log_file}

        is_alive = False
        if self.process:
            returncode = self.process.poll()
            if returncode is None:
                is_alive = True
            else:
                is_alive = False
                self.running = False

        if not is_alive and self.running:
            self.running = False
            self.process = None
            self.pid = None

        return {
            "running": is_alive,
            "pid": self.pid,
            "log_file": self.log_file,
            "returncode": self.process.poll() if self.process else None
        }

    def get_recent_logs(self, lines=100):
        """Gets recent log content."""
        if not self.log_file or not os.path.exists(self.log_file):
            return ""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                from collections import deque
                last_lines = deque(f, maxlen=lines)
                return ''.join(last_lines)
        except Exception as e:
            print(f"Read log failed: {e}")
            return f"Cannot read log: {str(e)}"


class DatabaseHelper:
    """Database helper class."""

    @staticmethod
    def execute_query(query, params=None):
        """Executes a query and returns column names and results."""
        from hotsearch_analysis_agent.config.settings import MYSQL_CONFIG
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            return column_names, results
        except Exception as e:
            raise e
        finally:
            conn.close()


class PushTaskManager:
    def __init__(self):
        self.db_helper = DatabaseHelper()

    def create_push_task(self, user_prompt, push_time):
        """Creates a push task."""
        try:
            task_id = str(uuid.uuid4())

            from hotsearch_analysis_agent.config.settings import MYSQL_CONFIG
            query = """
                    INSERT INTO push_tasks (task_id, user_prompt, push_time, status)
                    VALUES (%s, %s, %s, 'active')
                    """
            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()
            cursor.execute(query, (task_id, user_prompt, push_time))
            conn.commit()
            conn.close()

            self._schedule_push_task(task_id, user_prompt, push_time)

            return {"status": "success", "task_id": task_id, "message": "Created"}
        except Exception as e:
            return {"status": "error", "message": f"Create failed: {str(e)}"}

    def _schedule_push_task(self, task_id, user_prompt, push_time):
        """Schedules a push task."""
        try:
            hour, minute = map(int, push_time.split(':'))
            push_datetime = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            early_time = push_datetime - timedelta(minutes=10)
            if early_time < datetime.now():
                early_time += timedelta(days=1)

            scheduler.add_job(
                self._execute_push_task,
                'cron',
                hour=early_time.hour,
                minute=early_time.minute,
                args=[task_id, user_prompt],
                id=task_id,
                replace_existing=True
            )
        except Exception as e:
            print(f"Scheduling failed: {str(e)}")

    def _execute_push_task(self, task_id, user_prompt):
        """Executes the push task."""
        try:
            print(f"Starting task: {task_id}")
            system = get_system_instance()
            if not system:
                print("System not initialized")
                return

            from hotsearch_analysis_agent.core.tools import SemanticSearchTool, TopicClusteringTool
            search_tool = SemanticSearchTool()
            search_results = search_tool._run(f"{user_prompt}|all|30")

            clustering_tool = TopicClusteringTool()
            clustering_results = clustering_tool._run("2|all")

            structured_data = self._extract_titles_urls_from_clusters(user_prompt, clustering_results, search_results, system)
            if not structured_data:
                print("Failed to extract data from clusters")
                return

            content_data = self._extract_content_for_structured_data(structured_data)
            if not content_data:
                print("Failed to extract content")
                return

            report = self._generate_hotspot_report(user_prompt, content_data, system)
            if not report:
                print("Report generation failed")
                return

            self._send_report(report, user_prompt)
        except Exception as e:
            print(f"Execution failed: {str(e)}")

    def _extract_titles_urls_from_clusters(self, user_prompt, clustering_results, search_results, system):
        """Extracts titles and URLs from clusters."""
        try:
            relevant_cluster = self._identify_relevant_cluster(user_prompt, clustering_results, system)
            if not relevant_cluster:
                print("No relevant cluster found")
                return []

            structured_data = self._parse_cluster_for_titles_urls(relevant_cluster, clustering_results, search_results)
            return structured_data
        except Exception as e:
            print(f"Extraction failed: {str(e)}")
            return []

    def _identify_relevant_cluster(self, user_prompt, clustering_results, system):
        """Identifies the relevant cluster using LLM."""
        try:
            prompt = f"""
Based on user prompt: "{user_prompt}"
and clustering results:
{clustering_results}
Return the most relevant cluster name.
"""
            response = system.agent.llm.predict(prompt)
            return response.strip()
        except Exception as e:
            print(f"Cluster identification failed: {str(e)}")
            return None

    def _parse_cluster_for_titles_urls(self, cluster_name, clustering_results, search_results):
        """Parses cluster for titles and URLs."""
        try:
            structured_data = []
            import re
            cluster_pattern = rf"📂\s*{re.escape(cluster_name)}.*?(?=📂|📊|$)"
            cluster_match = re.search(cluster_pattern, clustering_results, re.DOTALL)

            if cluster_match:
                cluster_content = cluster_match.group(0)
                article_pattern = r'\[文章(\d+)\]\s*([^:]+):\s*(.*?)(?:\s*排名(\d+))?\s*\n\s*链接:\s*(https?://[^\s]+)'
                articles = re.findall(article_pattern, cluster_content)

                for article_num, platform, title, rank, url in articles:
                    structured_data.append({
                        "title": title.strip(),
                        "url": url,
                        "cluster": cluster_name,
                        "platform": platform.strip(),
                        "rank": rank if rank else "N/A"
                    })

                if not articles:
                    structured_data.extend(self._extract_articles_alternative(cluster_content, cluster_name))

            if len(structured_data) < 3:
                structured_data.extend(self._extract_from_search_results(search_results, cluster_name))

            return structured_data
        except Exception as e:
            print(f"Parsing cluster failed: {str(e)}")
            return []

    def _extract_articles_alternative(self, cluster_content, cluster_name):
        """Alternative extraction method."""
        structured_data = []
        import re
        try:
            title_url_patterns = [
                r'([^-]+?)\s*-\s*(https?://[^\s]+)',  # Title - URL
                r'([^-:]+?):\s*(https?://[^\s]+)',    # Title: URL
                r'([^\n]+?)\s+(https?://[^\s]+)'      # Title URL
            ]
            for pattern in title_url_patterns:
                items = re.findall(pattern, cluster_content)
                for title, url in items[:10]:
                    title = title.strip()
                    if len(title) > 5 and not any(keyword in title for keyword in ['关键词', '代表性文章', '主题']):
                        structured_data.append({
                            "title": title,
                            "url": url,
                            "cluster": cluster_name,
                            "platform": "Unknown",
                            "rank": "N/A"
                        })
            return structured_data
        except Exception as e:
            print(f"Alternative extraction failed: {str(e)}")
            return []

    def _extract_from_search_results(self, search_results, cluster_name):
        """Extracts from search results."""
        try:
            structured_data = []
            import re
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, search_results)

            for i, url in enumerate(urls[:10]):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                path_parts = parsed.path.split('/')
                title_keyword = path_parts[-1] if path_parts[-1] else path_parts[-2] if len(path_parts) > 1 else domain
                title = f"{cluster_name} related {i + 1}: {title_keyword}"
                structured_data.append({
                    "title": title,
                    "url": url,
                    "cluster": cluster_name
                })
            return structured_data
        except Exception as e:
            print(f"Extract from search results failed: {str(e)}")
            return []

    def _extract_content_for_structured_data(self, structured_data):
        """Extracts content for structured data."""
        try:
            content_extractor = ContentExtractor()
            content_data = []
            for item in structured_data[:15]:
                try:
                    url = item["url"]
                    title = item["title"]
                    content, is_video, video_url = content_extractor.extract_text_content(url)
                    if content and len(content.strip()) > 50:
                        clean_content = content[:2000] + "..." if len(content) > 2000 else content
                        content_data.append({
                            "title": title,
                            "url": url,
                            "content": clean_content,
                            "cluster": item["cluster"],
                            "platform": item.get("platform", "Unknown"),
                            "rank": item.get("rank", "N/A"),
                            "timestamp": datetime.now().isoformat()
                        })
                    time.sleep(2)
                except Exception as e:
                    print(f"Process URL failed {item['url']}: {str(e)}")
                    continue
            return content_data
        except Exception as e:
            print(f"Extract URL content failed: {str(e)}")
            return None

    def _generate_hotspot_report(self, user_prompt, content_data, system):
        """Generates a hotspot report."""
        try:
            analysis_prompt = f"""
User interest: {user_prompt}
Generate a concise report based on the following structured data:

Format:
1. Length 800-1000 words
2. Highlight key info and data
3. List news as "Title: URL: Summary"

Data:
{json.dumps(content_data, ensure_ascii=False, indent=2)[:6000]}

Generate the report:
"""
            response = system.agent.llm.predict(analysis_prompt)

            report_file = f"hotspot_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"# Report - {user_prompt}\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Cluster: {content_data[0]['cluster'] if content_data else 'Unknown'}\n")
                f.write(response)

            return report_file
        except Exception as e:
            print(f"Report generation failed: {str(e)}")
            return None

    def _push_to_wechat(self, content, title):
        """Pushes to WeChat group."""
        try:
            from hotsearch_analysis_agent.config.settings import PUSH_CONFIG
            if not PUSH_CONFIG.get('wecom_webhook'):
                print("Webhook not configured")
                return

            clean_content = self._clean_content(content)
            markdown_template = """## 🔥 Push: {title}
    **Time**: {time}
    **Summary**:
    {content}
    > Auto-generated by system
    """
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            draft_content = markdown_template.format(title=title, time=current_time, content=clean_content)
            content_bytes = draft_content.encode('utf-8')
            max_bytes = 4096

            if len(content_bytes) > max_bytes:
                excess_bytes = len(content_bytes) - max_bytes
                excess_chars = excess_bytes // 3 + 100
                if len(clean_content) > excess_chars:
                    clean_content = clean_content[:len(clean_content) - excess_chars] + "... [Long, see system]"
                else:
                    clean_content = "[Too long, see system]"

            markdown_content = markdown_template.format(title=title, time=current_time, content=clean_content)
            final_bytes = len(markdown_content.encode('utf-8'))

            if final_bytes > max_bytes:
                truncated_bytes = markdown_content.encode('utf-8')[:max_bytes - 100]
                try:
                    markdown_content = truncated_bytes.decode('utf-8', errors='ignore') + "..."
                except:
                    markdown_content = "Content too long, see system."

            message = {"msgtype": "markdown", "markdown": {"content": markdown_content}}

            response = requests.post(PUSH_CONFIG['wecom_webhook'], json=message, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                print("Pushed to WeChat group")
            else:
                print(f"WeChat group push failed: {result}")
        except Exception as e:
            print(f"WeChat push failed: {str(e)}")

    def _push_to_personal_wechat(self, content, title):
        """Pushes to personal WeChat."""
        try:
            from hotsearch_analysis_agent.config.settings import PUSH_CONFIG
            corp_id = PUSH_CONFIG.get('wecom_corp_id', '').strip()
            agent_id = PUSH_CONFIG.get('wecom_agent_id', '').strip()
            secret = PUSH_CONFIG.get('wecom_secret', '').strip()
            user_id = PUSH_CONFIG.get('wecom_user_id', '').strip()

            if not all([corp_id, agent_id, secret, user_id]):
                print("Personal WeChat config incomplete")
                return

            token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={secret}"
            token_response = requests.get(token_url, timeout=10)
            token_data = token_response.json()
            if token_data.get('errcode') != 0:
                print(f"Get access_token failed: {token_data}")
                return
            access_token = token_data.get('access_token')

            clean_content = self._clean_content(content, remove_markdown=True)
            if len(clean_content) > 1500:
                clean_content = clean_content[:1500] + "... [Long, see system]"

            message_content = f"""🔥 Push: {title}
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
📋 Content:
{clean_content}
💡 Auto-generated
"""

            message = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": int(agent_id),
                "text": {"content": message_content}
            }

            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
            send_response = requests.post(send_url, json=message, timeout=10)
            send_data = send_response.json()
            if send_data.get('errcode') == 0:
                print("Pushed to personal WeChat")
            else:
                print(f"Personal WeChat push failed: {send_data}")
                if send_data.get('errcode') == 60020:
                    print("Hint: Add server IP to whitelist.")
        except Exception as e:
            print(f"Personal WeChat push failed: {str(e)}")

    def _push_to_email(self, content, title):
        """Pushes to email."""
        try:
            from hotsearch_analysis_agent.config.settings import PUSH_CONFIG
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.header import Header

            email_host = PUSH_CONFIG.get('email_host')
            email_port = PUSH_CONFIG.get('email_port')
            email_user = PUSH_CONFIG.get('email_user')
            email_password = PUSH_CONFIG.get('email_password')
            email_to = PUSH_CONFIG.get('email_to')

            if not all([email_host, email_port, email_user, email_password, email_to]):
                print("Email config incomplete")
                return

            msg = MIMEMultipart()
            msg['From'] = email_user
            msg['To'] = email_to
            msg['Subject'] = Header(f'🔥 Push: {title}', 'utf-8')

            html_content = self._content_to_html(content)
            full_html = f"""
            <!DOCTYPE html>
            <html><head><meta charset="utf-8"><style>
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ padding: 25px; background: #f8f9fa; border-left: 1px solid #e9ecef; border-right: 1px solid #e9ecef; }}
                .footer {{ text-align: center; color: #6c757d; font-size: 14px; margin-top: 20px; padding: 15px; background: #e9ecef; border-radius: 0 0 10px 10px; }}
                .info-section {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #007bff; }}
                h1 {{ margin: 0; font-size: 24px; }} h2 {{ margin: 0; font-size: 18px; opacity: 0.9; }}
            </style></head><body>
                <div class="header"><h1>🔥 Report</h1><h2>{title}</h2></div>
                <div class="info-section"><strong>📅 Time</strong>: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                <div class="content">{html_content}</div>
                <div class="footer"><p>Auto-sent by system</p><p>Contact admin.</p></div>
            </body></html>
            """

            msg.attach(MIMEText(full_html, 'html', 'utf-8'))

            with smtplib.SMTP(email_host, email_port) as server:
                server.set_debuglevel(1)
                server.starttls()
                server.login(email_user, email_password)
                server.send_message(msg)
            print("Pushed to email")
        except Exception as e:
            print(f"Email push failed: {str(e)}")

    def _clean_content(self, content, remove_markdown=False):
        """Cleans content."""
        if remove_markdown:
            content = re.sub(r'[#*`\[\]]', '', content)
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', content)
        content = re.sub(r'\n\s*\n', '\n', content).strip()
        return content

    def _content_to_html(self, content):
        """Converts content to HTML."""
        content = re.sub(r'^# (.*?)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^## (.*?)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'^\* (.*?)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        content = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', content, flags=re.DOTALL)
        content = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" style="color: #007bff;">\1</a>', content)

        paragraphs = content.split('\n')
        html_paragraphs = []
        for para in paragraphs:
            if not para.strip(): continue
            if not para.startswith('<'): para = f'<p>{para}</p>'
            html_paragraphs.append(para)
        return '\n'.join(html_paragraphs)

    def _send_report(self, report_file, user_prompt):
        """Sends the report."""
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()

            content_lines = report_content.split('\n')
            actual_content = '\n'.join(content_lines[4:]) if len(content_lines) > 4 else report_content

            self._push_to_telegram(actual_content, user_prompt)
            self._push_to_wechat(actual_content, user_prompt)
            self._push_to_personal_wechat(actual_content, user_prompt)
            self._push_to_email(actual_content, user_prompt)
        except Exception as e:
            print(f"Send report failed: {str(e)}")

    def _push_to_telegram(self, content, title):
        """Pushes to Telegram."""
        try:
            from hotsearch_analysis_agent.config.settings import PUSH_CONFIG
            if not PUSH_CONFIG.get('telegram_bot_token') or not PUSH_CONFIG.get('telegram_chat_id'):
                print("Telegram config incomplete")
                return

            clean_content = self._clean_content(content)
            message_template = """
    *🔥 Push: {title}*
    *Time*: {time}
    {content}
    _Auto-generated_
            """.strip()

            fixed_content = message_template.format(title=title, time=datetime.now().strftime('%Y-%m-%d %H:%M'), content="")
            fixed_length = len(fixed_content)
            available_length = 4096 - fixed_length - 100

            if len(clean_content) > available_length:
                clean_content = clean_content[:available_length] + "... [Long, see system]"

            message = message_template.format(title=title, time=datetime.now().strftime('%Y-%m-%d %H:%M'), content=clean_content)

            if len(message) > 4096:
                emergency_length = 4096 - 200
                clean_content = clean_content[:emergency_length] + "... [Truncated]"
                message = message_template.format(title=title, time=datetime.now().strftime('%Y-%m-%d %H:%M'), content=clean_content)

            url = f"https://api.telegram.org/bot{PUSH_CONFIG['telegram_bot_token']}/sendMessage"
            payload = {
                'chat_id': PUSH_CONFIG['telegram_chat_id'],
                'text': message,
                'parse_mode': 'Markdown'
            }

            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            if result.get('ok'):
                print("Pushed to Telegram")
            else:
                print(f"Telegram push failed: {result}")
        except Exception as e:
            print(f"Telegram push failed: {str(e)}")

    def get_all_tasks(self):
        """Gets all push tasks."""
        try:
            from hotsearch_analysis_agent.config.settings import MYSQL_CONFIG
            query = "SELECT task_id, user_prompt, push_time, created_at FROM push_tasks WHERE status = 'active'"
            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute(query)
            tasks = cursor.fetchall()
            conn.close()
            return tasks
        except Exception as e:
            print(f"Get tasks failed: {str(e)}")
            return []

    def delete_task(self, task_id):
        """Deletes a push task."""
        try:
            from hotsearch_analysis_agent.config.settings import MYSQL_CONFIG
            query = "UPDATE push_tasks SET status = 'deleted' WHERE task_id = %s"
            conn = pymysql.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()
            cursor.execute(query, (task_id,))
            conn.commit()
            conn.close()

            try:
                scheduler.remove_job(task_id)
            except:
                pass
            return {"status": "success", "message": "Deleted"}
        except Exception as e:
            return {"status": "error", "message": f"Delete failed: {str(e)}"}


crawler_manager = CrawlerManager()
push_task_manager = PushTaskManager()


def get_system_instance():
    """Gets system instance (singleton)."""
    global system_instance
    if system_instance is None:
        try:
            system_instance = HotSearchAnalysisSystem()
            system_instance.startup()
        except Exception as e:
            print(f"System init failed: {e}")
            return None
    return system_instance


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_input = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')

        if not user_input:
            return jsonify({"status": "error", "message": "Input empty"})

        system = get_system_instance()
        if not system:
            return jsonify({"status": "error", "message": "System init failed"})

        response = system.agent.process_query(user_input)

        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
        saved_id = history_manager.save_conversation(user_input, response, conversation_id)

        return jsonify({"status": "success", "response": response, "conversation_id": saved_id})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Processing error: {str(e)}"})


@app.route('/api/crawler/logs', methods=['GET'])
def get_crawler_logs():
    try:
        lines = request.args.get('lines', default=100, type=int)
        logs = crawler_manager.get_recent_logs(lines)
        return jsonify({"status": "success", "logs": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Get logs failed: {str(e)}"})


@app.route('/api/crawler/full_status', methods=['GET'])
def get_crawler_full_status():
    try:
        status = crawler_manager.get_crawler_status()
        import psutil
        system_info = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }

        process_info = None
        if status.get("pid"):
            try:
                p = psutil.Process(status["pid"])
                process_info = {
                    "cpu_percent": p.cpu_percent(interval=0.1),
                    "memory_mb": p.memory_info().rss / 1024 / 1024,
                    "create_time": datetime.fromtimestamp(p.create_time()).isoformat(),
                    "status": p.status()
                }
            except psutil.NoSuchProcess:
                process_info = {"error": "Process not found"}

        return jsonify({
            "status": "success",
            "crawler_status": status,
            "system_info": system_info,
            "process_info": process_info
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Get status failed: {str(e)}"})


@app.route('/api/crawler/start', methods=['POST'])
def start_crawler():
    try:
        result = crawler_manager.start_crawlers()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Start failed: {str(e)}"})


@app.route('/api/crawler/stop', methods=['POST'])
def stop_crawler():
    try:
        result = crawler_manager.stop_crawlers()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Stop failed: {str(e)}"})


@app.route('/api/crawler/status', methods=['GET'])
def get_crawler_status():
    return jsonify({"status": "success", "running": crawler_manager.running})


@app.route('/api/push_tasks', methods=['POST'])
def create_push_task():
    try:
        data = request.json
        user_prompt = data.get('user_prompt', '').strip()
        push_time = data.get('push_time', '09:00')

        if not user_prompt:
            return jsonify({"status": "error", "message": "Prompt required"})

        if not crawler_manager.running:
            return jsonify({"status": "error", "message": "Start crawler first"})

        result = push_task_manager.create_push_task(user_prompt, push_time)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Create task failed: {str(e)}"})


@app.route('/api/push_tasks', methods=['GET'])
def get_push_tasks():
    try:
        tasks = push_task_manager.get_all_tasks()
        return jsonify({"status": "success", "tasks": tasks})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Get tasks failed: {str(e)}"})


@app.route('/api/push_tasks/<task_id>', methods=['DELETE'])
def delete_push_task(task_id):
    try:
        result = push_task_manager.delete_task(task_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Delete task failed: {str(e)}"})


@app.route('/api/direct_platform_query', methods=['POST'])
def direct_platform_query():
    try:
        data = request.json
        platform_name = data.get('platform_name', '').strip()
        user_message = data.get('message', '').strip()

        if not platform_name:
            return jsonify({"status": "error", "message": "Platform name required"})

        query = f"Query {platform_name} hot searches"

        from hotsearch_analysis_agent.core.tools import PlatformQueryTool
        try:
            tool = PlatformQueryTool()
            response = tool._run(query)

            system = get_system_instance()
            if system and system.agent and system.agent.memory:
                system.agent.memory.save_context(
                    {"input": user_message if user_message else query},
                    {"output": response}
                )

            conversation_id = str(uuid.uuid4())
            saved_id = history_manager.save_conversation(
                user_message if user_message else query,
                response,
                conversation_id
            )

            return jsonify({
                "status": "success",
                "response": response,
                "conversation_id": saved_id
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Query failed: {str(e)}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Request failed: {str(e)}"})


def cleanup():
    """Cleans up resources on exit."""
    print("Cleaning up...")
    if crawler_manager.running:
        print("Stopping crawler...")
        crawler_manager.stop_crawlers()
    if system_instance:
        try:
            system_instance.cleanup()
        except:
            pass
    try:
        scheduler.shutdown()
    except:
        pass
    print("Cleanup done")


atexit.register(cleanup)

if __name__ == '__main__':
    print("Initializing system...")
    get_system_instance()
    app.run(host='::', port=5000, debug=False)
