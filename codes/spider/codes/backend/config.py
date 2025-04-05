#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统配置文件
包含系统运行需要的各种配置项
"""

import os
import logging
from datetime import timedelta

# 环境配置
ENV = os.environ.get('FLASK_ENV', 'production')
DEBUG = ENV == 'development'
TESTING = ENV == 'testing'

# 密钥配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)

# 数据库配置
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/crawler_db')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# 日志配置
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_DIR = os.environ.get('LOG_DIR', '/app/logs')

# API配置
API_PREFIX = '/api'
API_VERSION = 'v1'

# JWT配置
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# 爬虫配置
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_DOWNLOAD_DELAY = 1
DEFAULT_CONCURRENT_REQUESTS = 16
DEFAULT_RETRY_TIMES = 3
DEFAULT_RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# 代理IP池配置
PROXY_POOL_CHECK_INTERVAL = 300  # 秒
PROXY_VALIDITY_THRESHOLD = 0.7  # 代理可用性阈值
PROXY_SOURCES = [
    {
        'name': 'provider1',
        'url': os.environ.get('PROXY_SOURCE1_URL', ''),
        'api_key': os.environ.get('PROXY_SOURCE1_KEY', ''),
        'type': 'json'
    },
    {
        'name': 'provider2',
        'url': os.environ.get('PROXY_SOURCE2_URL', ''),
        'api_key': os.environ.get('PROXY_SOURCE2_KEY', ''),
        'type': 'text'
    }
]

# Kubernetes配置
KUBERNETES_ENABLED = os.environ.get('KUBERNETES_ENABLED', 'false').lower() == 'true'
KUBERNETES_NAMESPACE = os.environ.get('KUBERNETES_NAMESPACE', 'default')
KUBERNETES_SPIDER_IMAGE = os.environ.get('KUBERNETES_SPIDER_IMAGE', 'crawler-spider:latest')

# 监控配置
PROMETHEUS_ENABLED = os.environ.get('PROMETHEUS_ENABLED', 'false').lower() == 'true'
STATS_COLLECTION_INTERVAL = 60  # 秒

# 存储配置
DATA_STORAGE_TYPE = os.environ.get('DATA_STORAGE_TYPE', 'mongodb')  # mongodb, elasticsearch, mysql
ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL', '')
MYSQL_URI = os.environ.get('MYSQL_URI', '')

# 配置日志格式
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'json': {
            'format': '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': LOG_LEVEL,
            'formatter': 'json',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'encoding': 'utf8'
        },
        'error_file': {
            'level': 'ERROR',
            'formatter': 'json',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'error.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'encoding': 'utf8'
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file', 'error_file'],
            'level': LOG_LEVEL,
            'propagate': True
        },
        'api': {
            'handlers': ['console', 'file', 'error_file'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'services': {
            'handlers': ['console', 'file', 'error_file'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'utils': {
            'handlers': ['console', 'file', 'error_file'],
            'level': LOG_LEVEL,
            'propagate': False
        },
    }
}

# 初始化日志目录
os.makedirs(LOG_DIR, exist_ok=True)

# 配置应用版本信息
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
APP_BUILD_DATE = os.environ.get('APP_BUILD_DATE', '2023-01-01') 