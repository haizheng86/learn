#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
代理IP池管理API
提供代理的获取、验证、状态查询和管理功能
"""

from flask import Blueprint, request, jsonify, current_app
from services.proxy import ProxyPoolService
import logging

# 配置日志
logger = logging.getLogger('api.proxies')

# 创建蓝图
bp = Blueprint('proxies', __name__, url_prefix='/api/proxies')

# 创建代理池服务实例
proxy_pool_service = None

@bp.before_app_first_request
def setup_proxy_service():
    """在第一个请求之前初始化代理池服务"""
    global proxy_pool_service
    proxy_pool_service = ProxyPoolService(
        mongo_uri=current_app.config['PROXY_POOL_MONGO_URI'],
        db_name=current_app.config['PROXY_POOL_DB'],
        collection_name=current_app.config['PROXY_POOL_COLLECTION'],
        proxy_sources=current_app.config['PROXY_SOURCES']
    )

@bp.route('/', methods=['GET'])
def get_proxies():
    """获取代理列表"""
    try:
        # 解析查询参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        min_success_rate = float(request.args.get('min_success_rate', 0))
        
        # 获取代理列表
        proxies, total = proxy_pool_service.get_proxies(
            page=page,
            page_size=page_size,
            min_success_rate=min_success_rate
        )
        
        return jsonify({
            "status": "success", 
            "data": {
                "proxies": proxies,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size
            }
        })
    except Exception as e:
        logger.error(f"获取代理列表失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/stats', methods=['GET'])
def get_proxy_stats():
    """获取代理池统计信息"""
    try:
        stats = proxy_pool_service.get_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取代理池统计信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/validate', methods=['POST'])
def validate_proxies():
    """验证所有代理"""
    try:
        # 异步启动验证任务
        proxy_pool_service.validate_proxies_async()
        return jsonify({
            "status": "success", 
            "message": "代理验证任务已启动，请稍后查看结果"
        })
    except Exception as e:
        logger.error(f"启动代理验证任务失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/fetch', methods=['POST'])
def fetch_new_proxies():
    """从配置的来源获取新代理"""
    try:
        # 异步启动获取任务
        proxy_pool_service.fetch_proxies_async()
        return jsonify({
            "status": "success", 
            "message": "代理获取任务已启动，请稍后查看结果"
        })
    except Exception as e:
        logger.error(f"启动代理获取任务失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/clean', methods=['POST'])
def clean_proxies():
    """清理低质量代理"""
    try:
        data = request.json or {}
        min_success_rate = data.get('min_success_rate', 0.1)
        max_age_days = data.get('max_age_days', 7)
        
        # 执行清理
        result = proxy_pool_service.clean_proxies(
            min_success_rate=min_success_rate,
            max_age_days=max_age_days
        )
        
        return jsonify({
            "status": "success", 
            "message": f"已清理 {result['cleaned']} 个低质量代理",
            "data": result
        })
    except Exception as e:
        logger.error(f"清理低质量代理失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<proxy_id>', methods=['DELETE'])
def delete_proxy(proxy_id):
    """删除指定代理"""
    try:
        result = proxy_pool_service.delete_proxy(proxy_id)
        if not result:
            return jsonify({
                "status": "error", 
                "message": "代理不存在"
            }), 404
            
        return jsonify({
            "status": "success", 
            "message": "代理已成功删除"
        })
    except Exception as e:
        logger.error(f"删除代理失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/verify', methods=['POST'])
def verify_proxy():
    """手动验证指定代理"""
    try:
        data = request.json
        if not data or 'proxy' not in data:
            return jsonify({
                "status": "error", 
                "message": "请求缺少proxy参数"
            }), 400
            
        proxy = data['proxy']
        result = proxy_pool_service.verify_proxy(proxy)
        
        return jsonify({
            "status": "success", 
            "data": {
                "proxy": proxy,
                "valid": result,
                "message": "代理有效" if result else "代理无效"
            }
        })
    except Exception as e:
        logger.error(f"验证代理失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/export', methods=['GET'])
def export_proxies():
    """导出高质量代理"""
    try:
        min_success_rate = float(request.args.get('min_success_rate', 0.7))
        limit = int(request.args.get('limit', 100))
        
        proxies = proxy_pool_service.export_proxies(
            min_success_rate=min_success_rate,
            limit=limit
        )
        
        return jsonify({
            "status": "success", 
            "data": proxies
        })
    except Exception as e:
        logger.error(f"导出代理失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/add', methods=['POST'])
def add_proxy():
    """手动添加代理"""
    try:
        data = request.json
        if not data or 'proxy' not in data:
            return jsonify({
                "status": "error", 
                "message": "请求缺少proxy参数"
            }), 400
            
        proxy_data = data['proxy']
        if not isinstance(proxy_data, dict) or 'ip' not in proxy_data or 'port' not in proxy_data:
            return jsonify({
                "status": "error", 
                "message": "proxy参数格式错误，应包含ip和port字段"
            }), 400
            
        # 添加代理并验证
        result = proxy_pool_service.add_proxy(proxy_data, validate=True)
        
        return jsonify({
            "status": "success", 
            "message": "代理添加成功",
            "data": result
        })
    except Exception as e:
        logger.error(f"添加代理失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500 