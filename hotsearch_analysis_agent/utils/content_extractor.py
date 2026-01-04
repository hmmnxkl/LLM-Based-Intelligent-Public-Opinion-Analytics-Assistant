import requests
from bs4 import BeautifulSoup
import re
from typing import Optional, Tuple, List
import json
import logging
from urllib.parse import urljoin, urlparse
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
from hotsearch_analysis_agent.config.settings import COOKIES_CONFIG, PLATFORM_URL_PATTERNS
import json
from selenium.common.exceptions import (
    UnableToSetCookieException,
    InvalidCookieDomainException,
    WebDriverException,
    InvalidArgumentException,
    TimeoutException
)

logger = logging.getLogger(__name__)

class ContentExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = 10
        self.selenium_timeout = 30
        self.driver = None
        self.video_file_cache = {}
        self.video_keywords = [
            '视频', '播放', '短片', '影音', 'movie', 'video', '播放器', '观看', '收看',
            '点播', '直播', '短视频', '长视频', '影视', '影片', '剪辑', '录制', '放映',
            '剧场', '影院', '电影院', '腾讯视频', '爱奇艺', '优酷', 'bilibili', '抖音', '快手',
            '西瓜视频', '微视', 'AcFun', '梨视频', '秒拍', '美拍'
        ]
        self.video_domain_keywords = [
            'video', 'vod', 'tv', 'film', 'movie', 'play', 'player', 'bilibili', 'iqiyi',
            'youku', 'tudou', 'qq.com/v', 'youtube', 'netflix', 'hulu', 'v.qq', 'acfun',
            'douyin', 'kuaishou', 'ixigua', 'weishi'
        ]
        self.cookies_config = COOKIES_CONFIG
        self.platform_url_patterns = PLATFORM_URL_PATTERNS
        self.loaded_cookies = {}

    def _detect_platform_by_url(self, url: str) -> Optional[str]:
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            for platform, patterns in self.platform_url_patterns.items():
                for pattern in patterns:
                    if pattern in domain or pattern in url:
                        logger.info(f"检测到{platform}平台URL: {url}")
                        return platform
            return None
        except Exception as e:
            logger.error(f"检测平台失败: {e}")
            return None

    def _get_cookies_for_platform(self, platform: str) -> List[dict]:
        try:
            if platform in self.cookies_config:
                config = self.cookies_config[platform]
                if 'file' in config:
                    file_path = config['file']
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            cookies = json.load(f)
                            logger.info(f"从文件读取{platform}平台cookies，数量: {len(cookies)}")
                            return cookies
                    else:
                        logger.warning(f"{platform}平台cookies文件不存在: {file_path}")
                        return []
                elif 'cookies' in config:
                    cookies = config.get('cookies', [])
                    if cookies:
                        logger.info(f"从环境变量获取{platform}平台cookies，数量: {len(cookies)}")
                        return cookies
                    else:
                        logger.warning(f"{platform}平台cookies配置为空")
                else:
                    logger.warning(f"未找到{platform}平台的cookies配置")
            return []
        except Exception as e:
            logger.error(f"获取{platform}平台cookies失败: {e}")
            return []

    def _load_cookies_to_driver(self, platform: str):
        try:
            if platform in self.loaded_cookies:
                logger.info(f"{platform}平台cookies已加载，跳过重复加载")
                return True
            cookies = self._get_cookies_for_platform(platform)
            if not cookies:
                logger.warning(f"没有可用的{platform}平台cookies")
                return False
            if not self.driver:
                logger.error("Selenium驱动未初始化，无法加载cookies")
                return False
            self.driver.delete_all_cookies()
            allowed_fields = [
                'name', 'value', 'domain', 'path', 'secure', 'httpOnly', 'expirationDate', 'sameSite'
            ]
            valid_same_site_values = ['Lax', 'Strict', 'None', None]
            success_count = 0
            for idx, cookie in enumerate(cookies):
                try:
                    if not isinstance(cookie, dict) or 'name' not in cookie or 'value' not in cookie:
                        logger.warning(f"第{idx + 1}个cookie格式无效，缺少name或value字段: {cookie}")
                        continue
                    filtered_cookie = {
                        k: v
                        for k, v in cookie.items()
                        if k in allowed_fields
                    }
                    if 'expirationDate' in filtered_cookie:
                        try:
                            filtered_cookie['expirationDate'] = int(filtered_cookie['expirationDate'])
                        except (ValueError, TypeError):
                            logger.warning(f"第{idx + 1}个cookie（{cookie['name']}）的expirationDate格式无效，已移除该字段")
                            del filtered_cookie['expirationDate']
                    if 'sameSite' in filtered_cookie:
                        same_site = filtered_cookie['sameSite']
                        if same_site not in valid_same_site_values:
                            filtered_cookie['sameSite'] = None
                            logger.debug(f"第{idx + 1}个cookie（{cookie['name']}）的sameSite值{same_site}已转换为None")
                    if 'domain' not in filtered_cookie:
                        domain_map = {
                            'zhihu': '.zhihu.com',
                            'weibo': '.weibo.com',
                            'xiaohongshu': '.xiaohongshu.com'
                        }
                        if platform in domain_map:
                            filtered_cookie['domain'] = domain_map[platform]
                            logger.debug(f"第{idx + 1}个cookie（{cookie['name']}）补充默认domain: {filtered_cookie['domain']}")
                        else:
                            logger.warning(f"第{idx + 1}个cookie（{cookie['name']}）缺少domain且无默认配置，可能添加失败")
                    if filtered_cookie.get('sameSite') == 'None' and not filtered_cookie.get('secure'):
                        filtered_cookie['secure'] = True
                        logger.debug(f"第{idx + 1}个cookie（{cookie['name']}）因sameSite:None强制设置secure:True")
                    self.driver.add_cookie(filtered_cookie)
                    success_count += 1
                    logger.debug(f"第{idx + 1}个cookie（{cookie['name']}）添加成功")
                except InvalidCookieDomainException as e:
                    logger.error(
                        f"第{idx + 1}个cookie（{cookie.get('name', 'unknown')}）域名无效: {str(e)}，"
                        f"当前驱动域名: {self.driver.current_url}，"
                        f"cookie域名: {filtered_cookie.get('domain')}"
                    )
                except UnableToSetCookieException as e:
                    logger.error(
                        f"第{idx + 1}个cookie（{cookie.get('name', 'unknown')}）无法设置: {str(e)}，"
                        f"cookie内容: {filtered_cookie}"
                    )
                except InvalidArgumentException as e:
                    logger.error(
                        f"第{idx + 1}个cookie（{cookie.get('name', 'unknown')}）参数无效: {str(e)}，"
                        f"可能是字段格式错误: {filtered_cookie}"
                    )
                except WebDriverException as e:
                    logger.error(
                        f"第{idx + 1}个cookie（{cookie.get('name', 'unknown')}）WebDriver错误: {str(e)}，"
                        f"错误类型: {type(e).__name__}"
                    )
                except Exception as e:
                    logger.error(
                        f"第{idx + 1}个cookie（{cookie.get('name', 'unknown')}）未知错误: {str(e)}，"
                        f"错误类型: {type(e).__name__}，"
                        f"cookie内容: {filtered_cookie}"
                    )
            logger.info(f"成功加载{success_count}/{len(cookies)}个{platform}平台cookies")
            self.loaded_cookies[platform] = True
            return success_count > 0
        except Exception as e:
            logger.error(f"加载cookies到驱动失败: {str(e)}，错误类型: {type(e).__name__}")
            return False

    def _access_with_cookies(self, url: str, platform: str) -> bool:
        try:
            logger.info(f"使用cookies访问{platform}平台页面: {url}")
            parsed_url = urlparse(url)
            homepage = f"{parsed_url.scheme}://{parsed_url.netloc}"
            self.driver.get(homepage)
            time.sleep(2)
            if self._load_cookies_to_driver(platform):
                self.driver.refresh()
                time.sleep(2)
                self.driver.get(url)
                logger.info(f"使用cookies访问成功: {url}")
                return True
            else:
                logger.warning(f"无法加载{platform}平台cookies，尝试直接访问")
                self.driver.get(url)
                return True
        except Exception as e:
            logger.error(f"使用cookies访问失败: {e}")
            return False

    def _init_selenium_driver(self):
        try:
            if self.driver is not None:
                return True
            try:
                from selenium.webdriver.edge.options import Options as EdgeOptions
                edge_options = EdgeOptions()
                edge_options.add_argument('--headless')
                edge_options.add_argument('--disable-gpu')
                edge_options.add_argument('--disable-extensions')
                edge_options.add_argument('--no-sandbox')
                edge_options.add_argument('--disable-dev-shm-usage')
                edge_options.add_argument('--disable-blink-features=AutomationControlled')
                edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                edge_options.add_experimental_option('useAutomationExtension', False)
                edge_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0')
                edge_options.add_argument('--blink-settings=imagesEnabled=false')
                self.driver = webdriver.Edge(options=edge_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                logger.info("✅ Selenium Edge驱动初始化成功")
                return True
            except Exception as edge_error:
                logger.warning(f"❌ Edge驱动初始化失败: {edge_error}")
                logger.info("尝试使用Chrome/Chromium浏览器...")
                try:
                    from selenium.webdriver.chrome.options import Options as ChromeOptions
                    chrome_options = ChromeOptions()
                    chrome_options.add_argument('--headless')
                    chrome_options.add_argument('--disable-gpu')
                    chrome_options.add_argument('--disable-extensions')
                    chrome_options.add_argument('--no-sandbox')
                    chrome_options.add_argument('--disable-dev-shm-usage')
                    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    chrome_options.add_experimental_option('useAutomationExtension', False)
                    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                    chrome_options.add_argument('--blink-settings=imagesEnabled=false')
                    self.driver = webdriver.Chrome(options=chrome_options)
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    logger.info("✅ Selenium Chrome/Chromium驱动初始化成功")
                    return True
                except Exception as chrome_error:
                    logger.error(f"❌ Chrome/Chromium驱动初始化失败: {chrome_error}")
                    return False
        except Exception as e:
            logger.error(f"❌ Selenium初始化异常: {e}")
            return False

    def _close_selenium_driver(self):
        try:
            if self.driver is not None:
                self.driver.quit()
                self.driver = None
                logger.debug("Selenium驱动已关闭")
        except Exception as e:
            logger.error(f"关闭Selenium驱动时出错: {e}")

    def _is_video_page(self, soup, url: str, text: str) -> bool:
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            if self._is_non_content_page(soup, url, text):
                return False
            if self._has_strong_video_features(soup, url):
                return True
            video_score = self._calculate_video_score(soup, url, text)
            return video_score >= 3
        except Exception as e:
            logger.error(f"判断视频页面时出错: {e}")
            return False

    def _is_non_content_page(self, soup, url: str, text: str) -> bool:
        try:
            if self._is_captcha_page(soup, text):
                logger.info("检测到验证码页面特征")
                return True
            if self._is_login_page(soup, text):
                logger.info("检测到登录页面特征")
                return True
            if self._is_error_page(soup, text):
                logger.info("检测到错误页面特征")
                return True
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) < 100:
                logger.info("页面内容过少")
                return True
            return False
        except Exception as e:
            logger.warning(f"非内容页面检测失败: {e}")
            return False

    def _is_captcha_page(self, soup, text: str) -> bool:
        captcha_indicators = [
            '验证码', 'captcha', '人机验证', '安全验证', '请输入验证码', '验证码输入', 'slide captcha', '请完成验证', '点选', '拼图',
            'captcha-container', 'captcha-wrapper', 'geetest', 'tencent-captcha', 'slider-captcha', 'point-captcha'
        ]
        text_lower = text.lower()
        captcha_keyword_count = sum(1 for keyword in captcha_indicators if keyword.lower() in text_lower)
        if captcha_keyword_count >= 2:
            return True
        images = soup.find_all('img')
        for img in images:
            alt = img.get('alt', '').lower()
            src = img.get('src', '').lower()
            if any(keyword in alt or keyword in src for keyword in ['captcha', '验证码', 'geetest']):
                return True
        inputs = soup.find_all('input')
        captcha_inputs = [
            inp for inp in inputs
            if inp.get('type') in ['text', 'number']
               and any(
                    keyword in inp.get('placeholder', '').lower() or keyword in inp.get('name', '').lower()
                    for keyword in ['captcha', '验证码', 'code']
                )
        ]
        if len(captcha_inputs) > 0:
            return True
        return False

    def _is_login_page(self, soup, text: str) -> bool:
        login_indicators = [
            '登录', '登陆', 'sign in', 'login', '账号', '密码', '用户名', 'password', 'username', 'remember me', '忘记密码', '注册', 'register', 'sign up'
        ]
        text_lower = text.lower()
        login_keyword_count = sum(1 for keyword in login_indicators if keyword.lower() in text_lower)
        password_inputs = soup.find_all('input', type='password')
        if len(password_inputs) > 0 and login_keyword_count >= 2:
            return True
        return False

    def _is_error_page(self, soup, text: str) -> bool:
        error_indicators = [
            '404', 'not found', '页面不存在', '访问拒绝', 'access denied', 'error', '错误', '服务器异常', 'service unavailable', '500', '502', '503'
        ]
        text_lower = text.lower()
        error_keyword_count = sum(1 for keyword in error_indicators if keyword.lower() in text_lower)
        return error_keyword_count >= 2

    def _has_strong_video_features(self, soup, url: str) -> bool:
        try:
            strong_video_domains = [
                'youtube.com', 'youtu.be', 'v.qq.com', 'bilibili.com', 'iqiyi.com', 'youku.com', 'tv.sohu.com', 'mgtv.com', 'acfun.cn', 'douyin.com', 'ixigua.com', 'kuaishou.com', 'netflix.com', 'hulu.com', 'vimeo.com'
            ]
            domain = urlparse(url).netloc.lower()
            if any(video_domain in domain for video_domain in strong_video_domains):
                logger.info(f"强视频特征：知名视频平台域名: {domain}")
                return True
            video_tags = soup.find_all('video')
            for video in video_tags:
                if video.get('src') or video.find('source', src=True):
                    logger.info("强视频特征：存在有效的video标签")
                    return True
            iframes = soup.find_all('iframe')
            video_platforms = ['youtube', 'v.qq', 'youku', 'iqiyi', 'bilibili', 'tv.sohu', 'mgtv']
            for iframe in iframes:
                src = iframe.get('src', '').lower()
                if any(platform in src for platform in video_platforms):
                    logger.info(f"强视频特征：视频平台iframe: {src}")
                    return True
            video_meta_properties = ['og:video', 'og:video:url', 'video:url']
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                property_attr = meta.get('property', '').lower()
                if property_attr in video_meta_properties and meta.get('content'):
                    logger.info(f"强视频特征：视频meta标签: {property_attr}")
                    return True
            return False
        except Exception as e:
            logger.warning(f"强视频特征检测失败: {e}")
            return False

    def _calculate_video_score(self, soup, url: str, text: str) -> int:
        score = 0
        text_lower = text.lower()
        domain = urlparse(url).netloc.lower()
        weak_features = [
            (any(keyword in domain for keyword in ['video', 'vod', 'tv', 'film', 'movie']), 1),
            (sum(1 for keyword in self.video_keywords if keyword in text_lower) >= 3, 1),
            (self._has_video_class_or_id(soup), 1),
            (self._has_video_data_attributes(soup), 1),
            (self._has_player_elements(soup), 1),
            (any(keyword in urlparse(url).path.lower() for keyword in ['video', 'play', 'player']), 1),
        ]
        for condition, points in weak_features:
            if condition:
                score += points
                logger.debug(f"视频特征得分 +{points}, 当前总分: {score}")
        return score

    def _has_video_class_or_id(self, soup) -> bool:
        video_patterns = [r'video', r'player', r'play', r'vod', r'movie']
        for pattern in video_patterns:
            if soup.find_all(class_=re.compile(pattern, re.I)):
                return True
            if soup.find_all(id=re.compile(pattern, re.I)):
                return True
        return False

    def _has_video_data_attributes(self, soup) -> bool:
        video_elements = soup.find_all(attrs={"data-video": True, "data-video-url": True, "data-video-id": True})
        return len(video_elements) > 0

    def _has_player_elements(self, soup) -> bool:
        player_selectors = ['.video-player', '.player-container', '.play-btn', '.video-play', '.player-wrapper', '[data-player]']
        for selector in player_selectors:
            if soup.select(selector):
                return True
        return False

    def _is_supported_video_platform(self, video_url: str) -> bool:
        try:
            parsed = urlparse(video_url)
            if parsed.scheme and parsed.netloc:
                logger.info(f"✅ 支持视频平台: {parsed.netloc}")
                return True
            else:
                logger.warning(f"❌ 无效的视频URL: {video_url}")
                return False
        except Exception as e:
            logger.error(f"❌ 解析视频URL失败: {e}")
            return False

    def _get_cached_video_file(self, video_url: str) -> Optional[str]:
        try:
            if video_url in self.video_file_cache:
                cached_file = self.video_file_cache[video_url]
                if os.path.exists(cached_file):
                    logger.info(f"使用缓存的视频文件: {cached_file}")
                    return cached_file
                else:
                    del self.video_file_cache[video_url]
            temp_dir = tempfile.gettempdir()
            video_file = os.path.join(temp_dir, f"video_{hash(video_url)}.mp4")
            logger.info(f"开始下载视频: {video_url}")
            response = requests.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 100 * 1024 * 1024:
                logger.warning(f"视频文件过大({int(content_length) / 1024 / 1024:.1f}MB)，跳过下载")
                return None
            with open(video_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"视频下载完成: {video_file}")
            self.video_file_cache[video_url] = video_file
            return video_file
        except Exception as e:
            logger.error(f"视频下载失败: {e}")
            return None

    def _cleanup_video_cache(self):
        try:
            for video_url, video_file in list(self.video_file_cache.items()):
                if os.path.exists(video_file):
                    try:
                        os.remove(video_file)
                        logger.debug(f"清理视频缓存文件: {video_file}")
                    except Exception as e:
                        logger.warning(f"清理视频文件失败 {video_file}: {e}")
            self.video_file_cache.clear()
        except Exception as e:
            logger.error(f"清理视频缓存失败: {e}")

    def _extract_embedded_subtitles(self, video_file: str) -> Optional[str]:
        try:
            import subprocess
            logger.info(f"开始提取内封字幕: {video_file}")
            temp_dir = tempfile.gettempdir()
            subtitle_file = os.path.join(temp_dir, f"subtitle_{hash(video_file)}.srt")
            cmd = [
                'ffmpeg',
                '-i',
                video_file,
                '-map',
                '0:s:0',
                '-c:s', 'srt',
                '-y',
                subtitle_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(subtitle_file):
                with open(subtitle_file, 'r', encoding='utf-8') as f:
                    subtitle_content = f.read()
                os.remove(subtitle_file)
                parsed_subtitle = self._parse_srt_subtitle(subtitle_content)
                if parsed_subtitle and len(parsed_subtitle.strip()) > 0:
                    logger.info(f"成功提取内封字幕，长度: {len(parsed_subtitle)}字符")
                    return parsed_subtitle
                else:
                    logger.warning("提取的字幕内容为空")
                    return None
            else:
                cmd_info = [
                    'ffprobe',
                    '-v',
                    'quiet',
                    '-select_streams',
                    's',
                    '-show_entries',
                    'stream=index',
                    '-of',
                    'csv=p=0',
                    video_file
                ]
                result_info = subprocess.run(cmd_info, capture_output=True, text=True)
                if result_info.returncode == 0 and result_info.stdout.strip():
                    subtitle_streams = [
                        stream.strip()
                        for stream in result_info.stdout.strip().split('\n')
                        if stream.strip()
                    ]
                    logger.info(f"找到 {len(subtitle_streams)} 个字幕流: {subtitle_streams}")
                    for stream_index in subtitle_streams:
                        subtitle_file = os.path.join(temp_dir, f"subtitle_{hash(video_file)}_stream{stream_index}.srt")
                        cmd = [
                            'ffmpeg',
                            '-i',
                            video_file,
                            '-map',
                            f'0:s:{stream_index}',
                            '-c:s',
                            'srt',
                            '-y',
                            subtitle_file
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        if result.returncode == 0 and os.path.exists(subtitle_file):
                            with open(subtitle_file, 'r', encoding='utf-8') as f:
                                subtitle_content = f.read()
                            os.remove(subtitle_file)
                            parsed_subtitle = self._parse_srt_subtitle(subtitle_content)
                            if parsed_subtitle and len(parsed_subtitle.strip()) > 0:
                                logger.info(f"成功从流 {stream_index} 提取内封字幕")
                                return parsed_subtitle
                logger.warning("未找到可提取的内封字幕")
                return None
        except FileNotFoundError:
            logger.error("ffmpeg或ffprobe未安装，无法提取内封字幕")
            return None
        except subprocess.TimeoutExpired:
            logger.error("字幕提取超时")
            return None
        except Exception as e:
            logger.error(f"提取内封字幕失败: {e}")
            if 'subtitle_file' in locals() and os.path.exists(subtitle_file):
                try:
                    os.remove(subtitle_file)
                except:
                    pass
            return None

    def _extract_hardcoded_subtitles(self, video_file: str) -> Optional[str]:
        try:
            logger.info(f"开始使用EasyOCR提取新闻视频内嵌字幕: {video_file}")
            try:
                import easyocr
                import cv2
                import numpy as np
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
            except ImportError as e:
                logger.error(f"EasyOCR依赖库未安装: {e}")
                logger.info("请安装: pip install easyocr opencv-python scikit-learn")
                return None
            try:
                reader = easyocr.Reader(['ch_sim', 'en'])
            except Exception as e:
                logger.error(f"EasyOCR初始化失败: {e}")
                return None
            subtitle_texts = []
            frames_processed = 0
            try:
                cap = cv2.VideoCapture(video_file)
                if not cap.isOpened():
                    logger.error("无法打开视频文件")
                    return None
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = total_frames / fps if fps > 0 else 0
                logger.info(f"新闻视频信息: {total_frames}帧, {fps:.2f}fps, {duration:.2f}秒")
                window_interval = 3
                frames_per_window = int(fps * window_interval)
                total_windows = int(duration / window_interval) + 1
                logger.info(f"时间窗口设置: 每{window_interval}秒({frames_per_window}帧)一个窗口，共{total_windows}个窗口")
                window_texts = {}
                for window_idx in range(total_windows):
                    target_frame = min(window_idx * frames_per_window + frames_per_window // 2, total_frames - 1)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning(f"无法读取窗口 {window_idx} 的帧")
                        continue
                    frame_texts = self._extract_text_with_easyocr(frame, reader)
                    if frame_texts:
                        unique_texts = []
                        seen_in_window = set()
                        for text in frame_texts:
                            text_simple = self._simplify_text(text)
                            if text_simple not in seen_in_window:
                                seen_in_window.add(text_simple)
                                unique_texts.append(text)
                        window_texts[window_idx] = unique_texts
                        logger.debug(f"窗口 {window_idx} 提取到 {len(unique_texts)} 个独特文本")
                    frames_processed += 1
                    if frames_processed >= min(50, total_windows):
                        break
                cap.release()
                final_texts = self._deduplicate_texts_across_windows(window_texts)
                if final_texts:
                    merged_text = '\n'.join(final_texts)
                    logger.info(f"新闻视频EasyOCR提取完成，获得 {len(final_texts)} 条独特文本，总长度: {len(merged_text)}")
                    return merged_text
                else:
                    logger.warning("EasyOCR未提取到任何有效文字")
                    return None
            except Exception as e:
                logger.error(f"新闻视频EasyOCR处理过程中出错: {e}")
                return None
        except Exception as e:
            logger.error(f"新闻视频内嵌字幕EasyOCR提取失败: {e}")
            return None

    def _extract_text_with_easyocr(self, frame, reader):
        try:
            import cv2
            import numpy as np
            processed_frame = self._preprocess_frame_for_easyocr(frame)
            results = reader.readtext(processed_frame, detail=0, paragraph=True)
            filtered_texts = []
            for text in results:
                cleaned_text = self._clean_ocr_text(text)
                if cleaned_text and self._is_meaningful_video_subtitle(cleaned_text):
                    filtered_texts.append(cleaned_text)
            return filtered_texts
        except Exception as e:
            logger.warning(f"EasyOCR文本提取失败: {e}")
            return []

    def _preprocess_frame_for_easyocr(self, frame):
        try:
            import cv2
            import numpy as np
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            denoised = cv2.medianBlur(enhanced, 3)
            return denoised
        except Exception as e:
            logger.warning(f"帧预处理失败: {e}")
            return frame

    def _clean_ocr_text(self, text):
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text.strip())
        return text

    def _simplify_text(self, text):
        simplified = re.sub(r'[^\w]', '', text.lower())
        return simplified

    def _deduplicate_texts_across_windows(self, window_texts):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            all_texts = []
            window_indices = []
            for window_idx, texts in window_texts.items():
                for text in texts:
                    all_texts.append(text)
                    window_indices.append(window_idx)
            if not all_texts:
                return []
            vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 4))
            try:
                tfidf_matrix = vectorizer.fit_transform(all_texts)
            except:
                return self._simple_text_deduplication(all_texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            final_texts = []
            used_indices = set()
            for i in range(len(all_texts)):
                if i in used_indices:
                    continue
                current_text = all_texts[i]
                current_window = window_indices[i]
                similar_indices = set()
                for j in range(i + 1, len(all_texts)):
                    if similarity_matrix[i, j] > 0.7:
                        similar_indices.add(j)
                best_text = current_text
                best_window = current_window
                for j in similar_indices:
                    if window_indices[j] < best_window:
                        best_text = all_texts[j]
                        best_window = window_indices[j]
                    used_indices.add(j)
                if self._is_meaningful_video_subtitle(best_text):
                    final_texts.append((best_window, best_text))
                used_indices.add(i)
            final_texts.sort(key=lambda x: x[0])
            return [text for _, text in final_texts]
        except Exception as e:
            logger.warning(f"相似度去重失败，使用简单去重: {e}")
            return self._simple_text_deduplication([text for texts in window_texts.values() for text in texts])

    def _simple_text_deduplication(self, texts):
        seen_texts = set()
        unique_texts = []
        for text in texts:
            text_simple = self._simplify_text(text)
            if text_simple not in seen_texts and self._is_meaningful_video_subtitle(text):
                seen_texts.add(text_simple)
                unique_texts.append(text)
        return unique_texts

    def _is_meaningful_video_subtitle(self, text):
        if not text or len(text.strip()) < 3:
            return False
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        chinese_ratio = len(chinese_chars) / len(text) if text else 0
        if chinese_ratio < 0.8:
            return False
        clean_text = re.sub(r'[^\w]', '', text)
        if clean_text.isdigit():
            return False
        if len(text) > 100:
            return False
        return True

    def _download_video_and_extract_audio(self, video_url: str) -> Optional[str]:
        try:
            video_file = self._get_cached_video_file(video_url)
            if not video_file:
                return None
            temp_dir = tempfile.gettempdir()
            audio_file = os.path.join(temp_dir, f"audio_{hash(video_url)}.wav")
            try:
                import subprocess
                cmd = [
                    'ffmpeg',
                    '-i',
                    video_file,
                    '-vn',
                    '-acodec',
                    'pcm_s16le',
                    '-ar',
                    '16000',
                    '-ac',
                    '1',
                    '-y',
                    audio_file
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    logger.info(f"音频提取成功: {audio_file}")
                    return audio_file
                else:
                    logger.error(f"ffmpeg提取音频失败: {result.stderr}")
                    return None
            except FileNotFoundError:
                logger.error("ffmpeg未安装，无法提取音频")
                return None
            except subprocess.TimeoutExpired:
                logger.error("音频提取超时")
                return None
        except Exception as e:
            logger.error(f"视频下载和音频提取失败: {e}")
            if 'audio_file' in locals() and audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except:
                    pass
            return None

    def extract_text_content(self, url: str) -> Tuple[Optional[str], bool, Optional[str]]:
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"无效的URL格式: {url}")
                return f"无效的URL格式: {url}", False, None
            logger.info(f"开始使用Selenium提取URL内容: {url}")
            platform = self._detect_platform_by_url(url)
            requires_cookies = platform is not None
            if not self._init_selenium_driver():
                return "Selenium驱动初始化失败", False, None
            try:
                if requires_cookies:
                    logger.info(f"检测到{platform}平台URL，尝试使用cookies访问")
                    success = self._access_with_cookies(url, platform)
                    if not success:
                        logger.warning(f"cookies访问失败，尝试普通访问: {url}")
                        self.driver.get(url)
                else:
                    self.driver.get(url)
                try:
                    WebDriverWait(self.driver, self.selenium_timeout).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(3)
                    if requires_cookies:
                        page_source = self.driver.page_source.lower()
                        if any(keyword in page_source for keyword in ['登录', '登陆', 'sign in', 'login']):
                            logger.warning(f"{platform}页面可能需要登录，当前cookies可能已失效")
                except TimeoutException:
                    logger.warning(f"页面加载超时，但继续处理已有内容: {url}")
                page_source = self.driver.page_source
            except Exception as e:
                logger.error(f"Selenium访问页面失败: {e}")
                return f"Selenium访问页面失败: {e}", False, None
            soup = BeautifulSoup(page_source, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                element.decompose()
            if platform == 'zhihu':
                content = self._extract_zhihu_content(soup)
            elif platform == 'weibo':
                content = self._extract_weibo_content(soup)
            elif platform == 'xiaohongshu':
                content = self._extract_xiaohongshu_content(soup)
            else:
                content = self._extract_main_content(soup)
            if content:
                text = content.get_text()
            else:
                text = soup.get_text()
            cleaned_text = self._advanced_text_cleaning(text)
            is_video = self._is_video_page(soup, url, cleaned_text)
            video_url = None
            if is_video:
                logger.info(f"判断为视频页面，尝试提取视频URL")
                video_url = self._extract_video_url(soup, url)
                if video_url:
                    logger.info(f"找到视频URL: {video_url}")
                    video_content = self._extract_video_content_optimized(video_url, url)
                    if video_content and len(video_content.strip()) > 50:
                        cleaned_text = video_content
                        logger.info("成功使用视频内容作为文本源")
                    else:
                        logger.warning("无法提取有效视频内容，使用原始文本")
                else:
                    logger.warning("未找到视频URL，使用原始文本")
            else:
                logger.info(f"判断为文章页面，文本长度: {len(cleaned_text)}字符")
            if not cleaned_text or len(cleaned_text.strip()) < 10:
                return "内容过短或无法提取有效信息", is_video, video_url
            return cleaned_text, is_video, video_url
        except Exception as e:
            logger.error(f"提取内容失败: {e}")
            return f"提取内容失败: {e}", False, None

    def _extract_zhihu_content(self, soup):
        zhihu_selectors = [
            '.QuestionAnswer-content', '.QuestionHeader-title', '.RichContent-inner', '.ContentItem-answer', '.List-item', '.TopicList',
        ]
        for selector in zhihu_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 100:
                return content
        return self._extract_main_content(soup)

    def _extract_weibo_content(self, soup):
        weibo_selectors = [
            '.WB_text', '.WB_detail', '.feed_content', '.weibo-text', '.txt', '.content',
        ]
        for selector in weibo_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 50:
                return content
        return self._extract_main_content(soup)

    def _extract_xiaohongshu_content(self, soup):
        xiaohongshu_selectors = [
            '.note-content', '.content', '.desc', '.text', '.note-desc', '.user-desc',
        ]
        for selector in xiaohongshu_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 50:
                return content
        return self._extract_main_content(soup)

    def _extract_main_content(self, soup):
        content_selectors = [
            '.article-content', '.content', '.main-content', '.post-content', '.entry-content', '[role="main"]', 'article', '.news-content', '.detail-content', '.story-content', '.text-content', '.article-body', '.article-text', '.news-body', '.news-detail', '.content-body', '.post-body', '.story-body', '.detail-body'
        ]
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 200:
                return content
        paragraphs = soup.find_all(['p', 'div'])
        if paragraphs:
            paragraphs.sort(key=lambda x: len(x.get_text(strip=True)), reverse=True)
            return paragraphs[0]
        return None

    def _extract_video_url(self, soup, base_url: str) -> Optional[str]:
        try:
            video_sources = []
            video_tags = soup.find_all('video')
            for video in video_tags:
                src = video.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    video_sources.append(full_url)
                    logger.debug(f"从video标签找到视频URL: {full_url}")
                sources = video.find_all('source')
                for source in sources:
                    src = source.get('src')
                    if src:
                        full_url = urljoin(base_url, src)
                        video_sources.append(full_url)
                        logger.debug(f"从source标签找到视频URL: {full_url}")
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if src:
                    full_url = urljoin(base_url, src)
                    video_platforms = ['youtube', 'v.qq', 'youku', 'iqiyi', 'bilibili', 'douyin', 'kuaishou']
                    if any(platform in src.lower() for platform in video_platforms):
                        video_sources.append(full_url)
                        logger.debug(f"从iframe找到视频URL: {full_url}")
            video_elements = soup.find_all(attrs={"data-video-url": True})
            for element in video_elements:
                video_url = element.get('data-video-url')
                if video_url:
                    full_url = urljoin(base_url, video_url)
                    video_sources.append(full_url)
                    logger.debug(f"从data属性找到视频URL: {full_url}")
            meta_tags = soup.find_all('meta', attrs={'property': True})
            for meta in meta_tags:
                property_value = meta.get('property', '').lower()
                content_value = meta.get('content', '')
                if property_value in ['og:video', 'og:video:url', 'video:url'] and content_value:
                    full_url = urljoin(base_url, content_value)
                    video_sources.append(full_url)
                    logger.debug(f"从meta标签找到视频URL: {full_url}")
            if video_sources:
                logger.info(f"共找到 {len(video_sources)} 个视频URL，使用第一个")
                return video_sources[0]
            else:
                logger.info("未找到视频URL")
                return None
        except Exception as e:
            logger.error(f"提取视频URL失败: {e}")
            return None

    def _extract_video_content_optimized(self, video_url: str, page_url: str) -> Optional[str]:
        try:
            logger.info(f"开始处理视频内容: {video_url}")
            video_file = self._get_cached_video_file(video_url)
            if not video_file:
                logger.warning("视频文件下载失败")
                return None
            content_methods = [
                ("内封字幕", self._extract_embedded_subtitles_from_video_file),
                ("音频文字", self._extract_audio_text_from_video_file),
                ("外挂字幕", lambda vf: self._extract_subtitle_text(video_url, page_url)),
                ("内嵌字幕", self._extract_hardcoded_subtitles_from_video_file)
            ]
            for method_name, method_func in content_methods:
                try:
                    logger.info(f"尝试{method_name}提取")
                    content = method_func(video_file) if method_name != "外挂字幕" else method_func(video_url, page_url)
                    if content and self._is_valid_content(content):
                        logger.info(f"{method_name}提取成功")
                        prefix_map = {
                            "内封字幕": "视频内封字幕内容",
                            "音频文字": "视频音频内容",
                            "外挂字幕": "视频字幕内容",
                            "内嵌字幕": "视频内嵌字幕内容(OCR)"
                        }
                        return f"{prefix_map[method_name]}: {content}"
                except Exception as e:
                    logger.warning(f"{method_name}提取失败: {e}")
                    continue
            logger.warning("所有视频内容提取方法均失败")
            return None
        except Exception as e:
            logger.error(f"视频内容提取失败: {e}")
            return None

    def _extract_embedded_subtitles_from_video_file(self, video_file: str) -> Optional[str]:
        try:
            return self._extract_embedded_subtitles(video_file)
        except Exception as e:
            logger.error(f"从视频文件提取内封字幕失败: {e}")
            return None

    def _extract_hardcoded_subtitles_from_video_file(self, video_file: str) -> Optional[str]:
        try:
            return self._extract_hardcoded_subtitles(video_file)
        except Exception as e:
            logger.error(f"从视频文件提取内嵌字幕失败: {e}")
            return None

    def _extract_audio_text_from_video_file(self, video_file: str) -> Optional[str]:
        try:
            temp_dir = tempfile.gettempdir()
            audio_file = os.path.join(temp_dir, f"audio_{hash(video_file)}.wav")
            try:
                import subprocess
                cmd = [
                    'ffmpeg',
                    '-i',
                    video_file,
                    '-vn',
                    '-acodec',
                    'pcm_s16le',
                    '-ar',
                    '16000',
                    '-ac',
                    '1',
                    '-y',
                    audio_file
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    text = self._speech_to_text(audio_file)
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                    return text
                else:
                    logger.error(f"音频提取失败: {result.stderr}")
                    return None
            except Exception as e:
                logger.error(f"音频处理失败: {e}")
                return None
        except Exception as e:
            logger.error(f"从视频文件提取音频文字失败: {e}")
            return None

    def _is_valid_content(self, content: str) -> bool:
        if not content:
            return False
        clean_content = re.sub(r'[^\w]', '', content)
        return len(clean_content) > 30

    def _extract_audio_text(self, video_url: str) -> Optional[str]:
        try:
            audio_file = self._download_video_and_extract_audio(video_url)
            if not audio_file:
                return None
            text = self._speech_to_text(audio_file)
            if os.path.exists(audio_file):
                os.remove(audio_file)
            return text
        except Exception as e:
            logger.error(f"音频文字提取失败: {e}")
            return None

    def _speech_to_text(self, audio_file: str) -> Optional[str]:
        try:
            try:
                import speech_recognition as sr
            except ImportError:
                logger.error("speech_recognition未安装，无法进行语音识别")
                return None
            r = sr.Recognizer()
            with sr.AudioFile(audio_file) as source:
                audio_data = r.record(source)
                try:
                    text = r.recognize_google(audio_data, language='zh-CN')
                    logger.info(f"语音识别成功，文字长度: {len(text)}")
                    return text
                except sr.UnknownValueError:
                    logger.warning("Google语音识别无法理解音频内容")
                except sr.RequestError as e:
                    logger.error(f"Google语音识别服务错误: {e}")
            return None
        except Exception as e:
            logger.error(f"语音转文字失败: {e}")
            return None

    def _extract_subtitle_text(self, video_url: str, page_url: str) -> Optional[str]:
        try:
            if page_url and page_url != video_url:
                logger.info(f"尝试从原始页面提取字幕: {page_url}")
                subtitle_text = self._extract_subtitles_from_page(page_url)
                if subtitle_text:
                    return subtitle_text
            logger.info("直接视频文件通常没有外部字幕")
            return None
        except Exception as e:
            logger.error(f"字幕提取失败: {e}")
            return None

    def _extract_subtitles_from_page(self, page_url: str) -> Optional[str]:
        try:
            response = self.session.get(page_url, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            subtitle_patterns = [r'\.srt$', r'\.vtt$', r'\.ass$', r'subtitle', r'caption']
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(pattern in href.lower() for pattern in subtitle_patterns):
                    subtitle_url = urljoin(page_url, href)
                    return self._download_and_parse_subtitle(subtitle_url)
            for track in soup.find_all('track'):
                if track.get('kind') == 'subtitles':
                    subtitle_url = urljoin(page_url, track['src'])
                    return self._download_and_parse_subtitle(subtitle_url)
            return None
        except Exception as e:
            logger.error(f"从页面提取字幕失败: {e}")
            return None

    def _download_and_parse_subtitle(self, subtitle_url: str) -> Optional[str]:
        try:
            response = self.session.get(subtitle_url, timeout=self.timeout)
            subtitle_content = response.text
            if subtitle_url.endswith('.srt'):
                return self._parse_srt_subtitle(subtitle_content)
            elif subtitle_url.endswith('.vtt'):
                return self._parse_vtt_subtitle(subtitle_content)
            else:
                return subtitle_content
        except Exception as e:
            logger.error(f"下载解析字幕失败: {e}")
            return None

    def _parse_srt_subtitle(self, content: str) -> str:
        try:
            lines = content.split('\n')
            text_lines = []
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line or line.isdigit():
                    i += 1
                    continue
                elif '-->' in line:
                    i += 1
                    continue
                else:
                    text_lines.append(line)
                    i += 1
            return ' '.join(text_lines)
        except Exception as e:
            logger.error(f"解析SRT字幕失败: {e}")
            return content

    def _parse_vtt_subtitle(self, content: str) -> str:
        try:
            lines = content.split('\n')
            text_lines = []
            i = 0
            while i < len(lines) and not lines[i].strip().startswith('00:'):
                i += 1
            while i < len(lines):
                line = lines[i].strip()
                if '-->' in line:
                    i += 1
                    continue
                elif not line or line.startswith('NOTE') or line.startswith('STYLE'):
                    i += 1
                    continue
                else:
                    text_lines.append(line)
                    i += 1
            return ' '.join(text_lines)
        except Exception as e:
            logger.error(f"解析VTT字幕失败: {e}")
            return content

    def _advanced_text_cleaning(self, text: str) -> str:
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'版权所有|Copyright|©|@[\w]+', '', text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        lines = [line for line in lines if len(line) > 20]
        cleaned_text = '\n'.join(lines)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text

    def __del__(self):
        self._close_selenium_driver()
        self._cleanup_video_cache()
