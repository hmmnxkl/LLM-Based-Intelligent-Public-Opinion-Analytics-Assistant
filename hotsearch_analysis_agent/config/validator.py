import os
from typing import Dict, Any


class ConfigValidator:
    @staticmethod
    def validate_required_config() -> Dict[str, Any]:
        errors = []
        warnings = []

        # 检查OpenAI API密钥
        if not os.getenv('OPENAI_API_KEY'):
            errors.append("OPENAI_API_KEY未设置，请在.env文件中配置")

        # 检查数据库配置
        db_required = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_DATABASE']
        for key in db_required:
            if not os.getenv(key):
                warnings.append(f"{key}未设置，使用默认值")

        # 检查爬虫路径
        from hotsearch_analysis_agent.config.settings import SPIDER_CONFIG
        if not os.path.exists(SPIDER_CONFIG['project_path']):
            warnings.append(f"爬虫项目路径不存在: {SPIDER_CONFIG['project_path']}")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @staticmethod
    def print_config_status():
        from hotsearch_analysis_agent.config.settings import LLM_CONFIG, MYSQL_CONFIG

        print("🔧 配置状态检查:")
        print(f"  OpenAI API密钥: {'✅ 已设置' if LLM_CONFIG['api_key'] else '❌ 未设置'}")
        print(f"  数据库连接: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG.get('port', 3306)}")
        print(f"  数据库名称: {MYSQL_CONFIG['database']}")
        print(f"  LLM模型: {LLM_CONFIG['model_name']}")

        result = ConfigValidator.validate_required_config()
        if result['errors']:
            print("\n❌ 配置错误:")
            for error in result['errors']:
                print(f"  - {error}")

        if result['warnings']:
            print("\n⚠️ 配置警告:")
            for warning in result['warnings']:
                print(f"  - {warning}")

        return result['is_valid']