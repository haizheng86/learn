#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
分布式爬虫系统后端应用
基于Flask实现的RESTful API服务
"""

import os
import sys
import logging
import logging.config
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from api import register_blueprints
from prometheus_client import start_http_server

# 将项目根目录添加到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入配置
from config import LOGGING_CONFIG

# 配置日志
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Redis连接URL
def get_redis_url():
    """获取Redis连接URL"""
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = os.environ.get('REDIS_PORT', '6379')
    redis_db = os.environ.get('REDIS_DB', '0')
    redis_password = os.environ.get('REDIS_PASSWORD', '')
    
    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}"

# MongoDB连接URI
def get_mongo_uri():
    """获取MongoDB连接URI"""
    mongo_host = os.environ.get('MONGO_HOST', 'localhost')
    mongo_port = os.environ.get('MONGO_PORT', '27017')
    mongo_db = os.environ.get('MONGO_DB', 'crawler_db')
    mongo_user = os.environ.get('MONGO_USER', '')
    mongo_password = os.environ.get('MONGO_PASSWORD', '')
    
    if mongo_user and mongo_password:
        return f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}"
    else:
        return f"mongodb://{mongo_host}:{mongo_port}/{mongo_db}"

def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    
    # 启用CORS
    CORS(app)
    
    # 加载配置
    app.config.from_object('config.Config')
    
    # 从环境变量加载密钥
    secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SECRET_KEY'] = secret_key
    
    # 配置全局URL前缀
    url_prefix = app.config.get('URL_PREFIX', '/api')
    
    # 注册所有API蓝图
    register_blueprints(app)
    
    # 健康检查路由
    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok"})
    
    # 错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        logger.error(f"Server error: {error}")
        return jsonify({"error": "Internal server error"}), 500
    
    # 初始化Prometheus指标服务器
    prometheus_port = int(os.environ.get('PROMETHEUS_PORT', 9301))
    try:
        start_http_server(prometheus_port)
        logger.info(f"Prometheus exporter started at port {prometheus_port}")
    except Exception as e:
        logger.error(f"Failed to start Prometheus exporter: {str(e)}")
    
    return app

if __name__ == '__main__':
    # 从环境变量获取主机和端口
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    app = create_app()
    
    # 启动应用
    logger.info(f"Starting Flask app on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)

# 在gunicorn中使用的应用实例
app = create_app() 