#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫管理API
提供爬虫任务的创建、启动、停止和状态查询
"""

from flask import Blueprint, request, jsonify, current_app
from services.crawler import CrawlerService
import logging

# 配置日志
logger = logging.getLogger('api.spiders')

# 创建蓝图
bp = Blueprint('spiders', __name__, url_prefix='/api/spiders')

# 创建爬虫服务实例
crawler_service = None

@bp.before_app_first_request
def setup_crawler_service():
    """在第一个请求之前初始化爬虫服务"""
    global crawler_service
    crawler_service = CrawlerService(
        redis_url=current_app.config['REDIS_URL'],
        mongo_uri=current_app.config['MONGO_URI'],
        kubernetes_enabled=current_app.config['KUBERNETES_ENABLED'],
        kubernetes_namespace=current_app.config['KUBERNETES_NAMESPACE'],
        crawler_image=current_app.config['CRAWLER_IMAGE']
    )

@bp.route('/', methods=['GET'])
def get_spiders():
    """获取所有爬虫信息"""
    try:
        spiders = crawler_service.get_all_spiders()
        return jsonify({"status": "success", "data": spiders})
    except Exception as e:
        logger.error(f"获取所有爬虫信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>', methods=['GET'])
def get_spider(spider_id):
    """获取指定爬虫信息"""
    try:
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return jsonify({"status": "error", "message": "爬虫不存在"}), 404
        return jsonify({"status": "success", "data": spider})
    except Exception as e:
        logger.error(f"获取爬虫 {spider_id} 信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/', methods=['POST'])
def create_spider():
    """创建新爬虫任务"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "请求缺少JSON数据"}), 400
            
        # 必须字段验证
        required_fields = ['name', 'start_urls', 'domain']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "status": "error", 
                "message": f"缺少必要字段: {', '.join(missing_fields)}"
            }), 400
            
        # 创建爬虫
        result = crawler_service.create_spider(data)
        return jsonify({"status": "success", "data": result}), 201
    except Exception as e:
        logger.error(f"创建爬虫失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/start', methods=['POST'])
def start_spider(spider_id):
    """启动爬虫"""
    try:
        # 获取配置参数
        data = request.json or {}
        concurrent_requests = data.get('concurrent_requests', 
                                      current_app.config['DEFAULT_CONCURRENT_REQUESTS'])
        use_proxy = data.get('use_proxy', True)
        
        # 启动爬虫
        result = crawler_service.start_spider(
            spider_id, 
            concurrent_requests=concurrent_requests,
            use_proxy=use_proxy
        )
        
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在或已启动"
            }), 400
            
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"启动爬虫 {spider_id} 失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/stop', methods=['POST'])
def stop_spider(spider_id):
    """停止爬虫"""
    try:
        result = crawler_service.stop_spider(spider_id)
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在或未运行"
            }), 400
            
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"停止爬虫 {spider_id} 失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/pause', methods=['POST'])
def pause_spider(spider_id):
    """暂停爬虫"""
    try:
        result = crawler_service.pause_spider(spider_id)
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在或未运行"
            }), 400
            
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"暂停爬虫 {spider_id} 失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/resume', methods=['POST'])
def resume_spider(spider_id):
    """恢复爬虫"""
    try:
        result = crawler_service.resume_spider(spider_id)
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在或未暂停"
            }), 400
            
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"恢复爬虫 {spider_id} 失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/stats', methods=['GET'])
def get_spider_stats(spider_id):
    """获取爬虫统计信息"""
    try:
        stats = crawler_service.get_spider_stats(spider_id)
        if not stats:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在或未运行"
            }), 404
            
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取爬虫 {spider_id} 统计信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/items', methods=['GET'])
def get_spider_items(spider_id):
    """获取爬虫采集的数据项"""
    try:
        # 分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        # 获取数据
        items, total = crawler_service.get_spider_items(spider_id, page, page_size)
        
        return jsonify({
            "status": "success", 
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size
            }
        })
    except Exception as e:
        logger.error(f"获取爬虫 {spider_id} 数据项失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>', methods=['DELETE'])
def delete_spider(spider_id):
    """删除爬虫"""
    try:
        # 首先尝试停止爬虫
        crawler_service.stop_spider(spider_id)
        
        # 删除爬虫
        result = crawler_service.delete_spider(spider_id)
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在"
            }), 404
            
        return jsonify({
            "status": "success", 
            "message": f"爬虫 {spider_id} 已成功删除"
        })
    except Exception as e:
        logger.error(f"删除爬虫 {spider_id} 失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/clear-queue', methods=['POST'])
def clear_spider_queue(spider_id):
    """清空爬虫队列"""
    try:
        result = crawler_service.clear_queue(spider_id)
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在"
            }), 404
            
        return jsonify({
            "status": "success", 
            "message": f"爬虫 {spider_id} 队列已清空"
        })
    except Exception as e:
        logger.error(f"清空爬虫 {spider_id} 队列失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/<spider_id>/scale', methods=['POST'])
def scale_spider(spider_id):
    """扩缩容爬虫实例"""
    try:
        data = request.json
        if not data or 'replicas' not in data:
            return jsonify({
                "status": "error", 
                "message": "请求缺少replicas参数"
            }), 400
            
        replicas = int(data['replicas'])
        if replicas < 0 or replicas > 50:
            return jsonify({
                "status": "error", 
                "message": "replicas参数值无效，应在0-50之间"
            }), 400
            
        # 扩缩容爬虫
        result = crawler_service.scale_spider(spider_id, replicas)
        if not result:
            return jsonify({
                "status": "error", 
                "message": f"爬虫 {spider_id} 不存在或未部署在Kubernetes中"
            }), 400
            
        return jsonify({
            "status": "success", 
            "message": f"爬虫 {spider_id} 已扩缩为 {replicas} 个实例",
            "data": result
        })
    except Exception as e:
        logger.error(f"扩缩容爬虫 {spider_id} 失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500 