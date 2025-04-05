#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API接口模块
提供RESTful API接口，管理爬虫任务、代理池、系统配置和监控数据
"""

from flask import Blueprint

def register_blueprints(app):
    """注册所有API蓝图"""
    from api.spiders import bp as spiders_bp
    from api.proxies import bp as proxies_bp
    from api.stats import bp as stats_bp
    from api.system import bp as system_bp
    from api.crawler import bp as crawler_bp
    from api.user import bp as user_bp
    from api.scheduler import bp as scheduler_bp
    
    # 注册蓝图
    app.register_blueprint(spiders_bp)
    app.register_blueprint(proxies_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(crawler_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(scheduler_bp)
    
    return app

__all__ = ['spiders_bp', 'proxies_bp', 'stats_bp', 'system_bp'] 