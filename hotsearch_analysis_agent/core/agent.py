from langchain.agents import AgentType, initialize_agent
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from typing import List, Dict, Any
import re
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hotsearch_analysis_agent.config.settings import LLM_CONFIG, MEMORY_CONFIG
from hotsearch_analysis_agent.config.prompts import SYSTEM_PROMPT, TOOL_SELECTION_PROMPT
from hotsearch_analysis_agent.core.tools import *
from hotsearch_analysis_agent.utils.platform_mapper import platform_mapper
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate

class HotSearchAgent:
    def __init__(self):
        logger.info("🚀 开始初始化 HotSearchAgent...")
        logger.info(f"📋 当前配置:")
        logger.info(f"  - API Base: {LLM_CONFIG.get('api_base')}")
        logger.info(f"  - Model: {LLM_CONFIG.get('model_name')}")
        logger.info(f"  - API Key: {LLM_CONFIG.get('api_key')}")

        if not LLM_CONFIG.get('api_base'):
            raise ValueError("请配置 OPENAI_API_BASE 指向模型服务器")

        if not LLM_CONFIG['api_key']:
            raise ValueError("OpenAI API密钥未设置，请在.env文件中配置OPENAI_API_KEY")

        llm_kwargs = {
            'model_name': LLM_CONFIG['model_name'],
            'temperature': LLM_CONFIG['temperature'],
            'max_tokens': LLM_CONFIG['max_tokens'],
            'openai_api_key': LLM_CONFIG['api_key']
        }

        if LLM_CONFIG['api_base']:
            llm_kwargs['openai_api_base'] = LLM_CONFIG['api_base']
        if LLM_CONFIG['organization']:
            llm_kwargs['openai_organization'] = LLM_CONFIG['organization']

        logger.info(f"🤖 初始化LLM，模型: {LLM_CONFIG['model_name']}")
        self.llm = ChatOpenAI(**llm_kwargs)

        logger.info("🛠️ 创建工具...")
        self.tools = self._create_tools()
        logger.info(f"✅ 成功创建 {len(self.tools)} 个工具")

        logger.info("🧠 初始化LangChain记忆系统...")
        self.memory = ConversationBufferWindowMemory(
            k=MEMORY_CONFIG['max_history'],
            memory_key=MEMORY_CONFIG['memory_key'],
            return_messages=True,
            output_key="output"
        )
        logger.info("🔧 初始化智能体...")
        try:
            self.agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,

                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                memory=self.memory,
                verbose=True,
                handle_parsing_errors=True,
                return_intermediate_steps=False
            )
            #若模型能力较弱，请使用以下代码
            # self.agent = initialize_agent(
            #     tools=self.tools,
            #     llm=self.llm,
            #     agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            #     memory=self.memory,
            #     verbose=True,
            #     handle_parsing_errors=True,
            #     return_intermediate_steps=False,
            #     max_iterations=1,
            #     early_stopping_method="generate",
            #     agent_kwargs={
            #         'prefix': SYSTEM_PROMPT + "\n\n" + '请直接调用合适的工具来处理用户请求。工具执行后会直接返回结果。',
            #         'format_instructions': '请以JSON格式输出，包含action和action_input两个字段。',
            #         'suffix': """请直接返回JSON格式，不要添加额外解释。格式如下：
            #                             {{
            #                                 "action": "工具名称",
            #                                 "action_input": "工具输入参数"
            #                             }}
            #
            #                             工具名称必须是以下之一: {tool_names}
            #
            #                             用户输入: {input}
            #                             {agent_scratchpad}"""
            #     }
            # )

            logger.info("✅ 智能体初始化成功")
        except Exception as e:
            logger.error(f"❌ 智能体初始化失败: {e}")
            raise

        logger.info("📋 设置系统提示...")
        self.agent.agent.llm_chain.prompt.messages[0].prompt.template = SYSTEM_PROMPT + "\n\n" + \
                                 self.agent.agent.llm_chain.prompt.messages[0].prompt.template

        self.platform_mapper = platform_mapper
        logger.info("🎉 HotSearchAgent 初始化完成")

    def process_query(self,
                      query: str) -> str:
        """处理用户查询 - 统一使用LangChain记忆系统"""
        try:
            detected_platforms = self.platform_mapper.extract_platforms_from_text(
                query)
            if detected_platforms:
                platform_names = self.platform_mapper.format_platform_list(
                    detected_platforms)
                logger.info(
                    f"🔍 检测到平台: {platform_names}")

            try:
                response = self.agent.run(
                    query)
                logger.info(
                    f"📝 原始响应 (前500字符): {response[:500]}")
                logger.info(
                    f"📝 响应长度: {len(response)}")
                logger.info(
                    f"📝 是否包含Observation: {'Observation:' in response}")
                logger.info(
                    f"📝 是否包含unused17: {'unused17:' in response}")
                filtered_response = self.filter_response(
                response)

            except Exception as e:
                logger.error(
                    f"Agent执行失败: {e}")
                filtered_response = f"处理查询时出错2: {str(e)}"

            return filtered_response

        except Exception as e:
            error_msg = f"处理查询时出错: {str(e)}"
            logger.error(
                error_msg)
            return error_msg


#若模型能力较弱，请使用以下代码
    # def process_query(self, query: str) -> str:
    #     try:
    #         detected_platforms = self.platform_mapper.extract_platforms_from_text(query)
    #         if detected_platforms:
    #             platform_names = self.platform_mapper.format_platform_list(detected_platforms)
    #             logger.info(f"🔍 检测到平台: {platform_names}")
    #
    #         try:
    #             response = self.agent.run(query)
    #             filtered_response = self.filter_response(response)
    #             logger.info(f"✅ Agent执行成功，过滤后响应长度: {len(filtered_response)}")
    #             logger.info(f"✅ 过滤后响应前500字符: {filtered_response[:500]}")
    #         except Exception as e:
    #             logger.error(f"Agent执行失败: {e}")
    #
    #             error_str = str(e)
    #             logger.info(f"🔍 错误信息内容: {error_str[:1000]}")
    #
    #             extracted_response = self._extract_response_from_error(error_str)
    #             if extracted_response:
    #                 logger.info(f"✅ 成功从错误信息中提取工具响应")
    #                 filtered_response = extracted_response
    #             else:
    #                 filtered_response = f"处理查询时出错2: {str(e)}"
    #
    #         return filtered_response
    #
    #     except Exception as e:
    #         error_msg = f"处理查询时出错: {str(e)}"
    #         logger.error(error_msg)
    #         return error_msg

    def _extract_response_from_error(self, error_str: str) -> str:
        try:
            obs_patterns = [
                r'Observation:\s*(.*?)(?=\n\nThought:|\n\nFinal Answer:|\n\n```|$)',
                r'Observation:\s*(.*)',
            ]

            for pattern in obs_patterns:
                match = re.search(pattern, error_str, re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    logger.info(f"✅ 从错误信息中提取到Observation内容，长度: {len(content)}")
                    return content

            tool_patterns = [
                r'📊.*热搜榜单.*',
                r'🎯.*话题聚类分析.*',
                r'📈.*情感分析报告.*',
                r'🔍.*搜索.*结果.*',
            ]

            for pattern in tool_patterns:
                match = re.search(pattern, error_str, re.DOTALL)
                if match:
                    content = match.group(0).strip()
                    logger.info(f"✅ 从错误信息中提取到工具返回内容，长度: {len(content)}")
                    return content

            if 'http://' in error_str or 'https://' in error_str:
                lines = error_str.split('\n')
                tool_lines = []
                for line in lines:
                    if any(keyword in line for keyword in ['链接:', '排名', '标题:', '作者:', '时间:', '📊', '🏆', '🔗']):
                        tool_lines.append(line)

                if tool_lines:
                    content = '\n'.join(tool_lines)
                    logger.info(f"✅ 从错误信息中提取到工具格式内容，长度: {len(content)}")
                    return content

            return ""
        except Exception as e:
            logger.error(f"提取错误信息中的响应失败: {e}")
            return ""

    def filter_response(self, response: str) -> str:
        try:
            logger.info(f"📝 filter_response 接收到的响应类型: {type(response)}")
            logger.info(f"📝 filter_response 响应前500字符: {str(response)[:500]}")

            if not isinstance(response, str):
                response_str = str(response)
            else:
                response_str = response

            obs_pattern = re.compile(r'Observation:\s*', re.IGNORECASE)
            obs_match = obs_pattern.search(response_str)

            if obs_match:
                content = response_str[obs_match.end():].strip()
                logger.info(f"✅ 找到Observation，提取内容长度: {len(content)}")
                return content

            unused_pattern = re.compile(r'unused17:\s*', re.IGNORECASE)
            unused_match = unused_pattern.search(response_str)

            if unused_match:
                content = response_str[unused_match.end():].strip()
                logger.info(f"✅ 找到unused17，提取内容长度: {len(content)}")
                return content

            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            json_match = json_pattern.search(response_str)

            if json_match:
                json_content = json_match.group(1).strip()
                logger.info(f"✅ 找到JSON格式响应，长度: {len(json_content)}")

                try:
                    import json
                    json_data = json.loads(json_content)
                    if 'action_input' in json_data:
                        return json_data['action_input']
                except:
                    pass

            tool_indicators = ['📊', '🏆', '🎯', '📈', '🔍', '排名', '链接:', '作者:', '时间:']
            if any(indicator in response_str for indicator in tool_indicators):
                logger.info(f"✅ 响应已包含工具格式内容，直接返回")
                return response_str

            logger.info(f"⚠️ 未匹配任何模式，返回原始响应")
            return response_str

        except Exception as e:
            logger.error(f"filter_response处理失败: {e}")
            return response if isinstance(response, str) else str(response)

    def _create_tools(self):
        logger.info("🔨 开始创建工具...")

        tools = [
            PlatformQueryTool(),
            SemanticSearchTool(),
            IntelligentSentimentAnalysisTool(),
            TopicClusteringTool(),
            VectorSearchTool(),
            IntelligentContentAnalysisTool(),
            TitleSemanticSearchTool(),
            PlatformListTool()
        ]

        logger.info(f"✅ 成功创建 {len(tools)} 个工具")
        return tools
