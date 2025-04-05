#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统统计API
提供系统数据采集量、性能指标等统计信息
"""

from flask import Blueprint, request, jsonify, current_app
from services.monitor import MonitorService
import logging

# 配置日志
logger = logging.getLogger('api.stats')

# 创建蓝图
bp = Blueprint('stats', __name__, url_prefix='/api/stats')

# 创建监控服务实例
monitor_service = None

@bp.before_app_first_request
def setup_monitor_service():
    """在第一个请求之前初始化监控服务"""
    global monitor_service
    monitor_service = MonitorService(
        redis_url=current_app.config['REDIS_URL'],
        mongo_uri=current_app.config['MONGO_URI']
    )

@bp.route('/summary', methods=['GET'])
def get_summary_stats():
    """获取系统概要统计信息"""
    try:
        stats = monitor_service.get_summary_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取系统概要统计信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/daily', methods=['GET'])
def get_daily_stats():
    """获取每日统计数据"""
    try:
        days = int(request.args.get('days', 30))
        stats = monitor_service.get_daily_stats(days)
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取每日统计数据失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/performance', methods=['GET'])
def get_performance_stats():
    """获取系统性能统计"""
    try:
        hours = int(request.args.get('hours', 24))
        stats = monitor_service.get_performance_stats(hours)
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取系统性能统计失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/domains', methods=['GET'])
def get_domain_stats():
    """获取按域名统计的数据量"""
    try:
        days = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 10))
        stats = monitor_service.get_domain_stats(days, limit)
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取域名统计数据失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/errors', methods=['GET'])
def get_error_stats():
    """获取错误统计"""
    try:
        days = int(request.args.get('days', 7))
        limit = int(request.args.get('limit', 20))
        stats = monitor_service.get_error_stats(days, limit)
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取错误统计失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/prometheus', methods=['GET'])
def get_prometheus_metrics():
    """获取Prometheus监控指标信息"""
    try:
        metrics = monitor_service.get_prometheus_metrics()
        return jsonify({"status": "success", "data": metrics})
    except Exception as e:
        logger.error(f"获取Prometheus监控指标失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/queues', methods=['GET'])
def get_queue_stats():
    """获取队列统计信息"""
    try:
        stats = monitor_service.get_queue_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取队列统计信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/storage', methods=['GET'])
def get_storage_stats():
    """获取存储统计信息"""
    try:
        stats = monitor_service.get_storage_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取存储统计信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/export', methods=['GET'])
def export_stats():
    """导出统计数据"""
    try:
        format_type = request.args.get('format', 'json')
        days = int(request.args.get('days', 30))
        
        if format_type not in ['json', 'csv']:
            return jsonify({
                "status": "error", 
                "message": "不支持的导出格式，仅支持json和csv"
            }), 400
            
        data = monitor_service.export_stats(days, format_type)
        
        # 若为CSV格式，设置合适的响应头
        if format_type == 'csv':
            headers = {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=crawler_stats_{days}days.csv'
            }
            return data, 200, headers
            
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        logger.error(f"导出统计数据失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500 