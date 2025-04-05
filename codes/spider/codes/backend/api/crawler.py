#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫管理API
提供爬虫任务的创建、配置、调度和监控
"""

import logging
from flask import Blueprint, request, jsonify, g
from services.crawler import CrawlerService
from utils.response import success_response, error_response, pagination_response
from utils.auth import login_required, admin_required
from config import REDIS_URL, MONGO_URI, KUBERNETES_ENABLED, KUBERNETES_NAMESPACE

# 创建蓝图
crawler_bp = Blueprint('crawler', __name__, url_prefix='/api/crawler')

# 配置日志
logger = logging.getLogger('api.crawler')

# 初始化爬虫服务
crawler_service = CrawlerService(
    redis_url=REDIS_URL,
    mongo_uri=MONGO_URI,
    kubernetes_enabled=KUBERNETES_ENABLED,
    kubernetes_namespace=KUBERNETES_NAMESPACE
)

@crawler_bp.route('/spiders', methods=['GET'])
@login_required
def get_spiders():
    """获取所有爬虫列表"""
    try:
        # 查询参数
        status = request.args.get('status')
        domain = request.args.get('domain')
        tags = request.args.getlist('tag')
        
        # 分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 排序参数
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # 获取爬虫列表
        spiders, total = crawler_service.get_all_spiders(
            status=status, 
            domain=domain,
            tags=tags,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return pagination_response(
            data=spiders,
            page=page,
            page_size=page_size,
            total=total,
            message="获取爬虫列表成功"
        )
    except Exception as e:
        logger.error(f"获取爬虫列表失败: {str(e)}")
        return error_response(message=f"获取爬虫列表失败: {str(e)}")

@crawler_bp.route('/spiders', methods=['POST'])
@admin_required
def create_spider():
    """创建新爬虫"""
    try:
        data = request.get_json()
        if not data:
            return error_response(message="无效的请求数据")
        
        # 验证必需字段
        required_fields = ['name', 'domain', 'start_urls']
        for field in required_fields:
            if field not in data:
                return error_response(message=f"缺少必需的字段: {field}")
        
        # 创建爬虫
        spider_id = crawler_service.create_spider(
            name=data['name'],
            domain=data['domain'],
            start_urls=data['start_urls'],
            settings=data.get('settings', {}),
            spider_type=data.get('spider_type', 'general'),
            custom_code=data.get('custom_code'),
            tags=data.get('tags', []),
            creator=g.user.get('username')
        )
        
        return success_response(
            data={"spider_id": spider_id},
            message="爬虫创建成功",
            code=201
        )
    except Exception as e:
        logger.error(f"创建爬虫失败: {str(e)}")
        return error_response(message=f"创建爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>', methods=['GET'])
@login_required
def get_spider(spider_id):
    """获取爬虫详细信息"""
    try:
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        return success_response(data=spider)
    except Exception as e:
        logger.error(f"获取爬虫详情失败: {str(e)}")
        return error_response(message=f"获取爬虫详情失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>', methods=['PUT'])
@admin_required
def update_spider(spider_id):
    """更新爬虫配置"""
    try:
        data = request.get_json()
        if not data:
            return error_response(message="无效的请求数据")
        
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 不允许更新的字段
        disallowed_fields = ['id', 'spider_id', 'created_at', 'creator']
        update_data = {k: v for k, v in data.items() if k not in disallowed_fields}
        
        # 更新爬虫
        updated = crawler_service.update_spider(spider_id, update_data)
        
        return success_response(data={"updated": updated})
    except Exception as e:
        logger.error(f"更新爬虫失败: {str(e)}")
        return error_response(message=f"更新爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>', methods=['DELETE'])
@admin_required
def delete_spider(spider_id):
    """删除爬虫"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 删除爬虫
        deleted = crawler_service.delete_spider(spider_id)
        
        return success_response(message="爬虫已删除")
    except Exception as e:
        logger.error(f"删除爬虫失败: {str(e)}")
        return error_response(message=f"删除爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/start', methods=['POST'])
@admin_required
def start_spider(spider_id):
    """启动爬虫"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 获取可选参数
        data = request.get_json() or {}
        instances = data.get('instances', 1)
        arguments = data.get('arguments', {})
        
        # 启动爬虫
        result = crawler_service.start_spider(spider_id, instances=instances, arguments=arguments)
        
        return success_response(data=result, message="爬虫已启动")
    except Exception as e:
        logger.error(f"启动爬虫失败: {str(e)}")
        return error_response(message=f"启动爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/stop', methods=['POST'])
@admin_required
def stop_spider(spider_id):
    """停止爬虫"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 停止爬虫
        result = crawler_service.stop_spider(spider_id)
        
        return success_response(data=result, message="爬虫已停止")
    except Exception as e:
        logger.error(f"停止爬虫失败: {str(e)}")
        return error_response(message=f"停止爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/pause', methods=['POST'])
@admin_required
def pause_spider(spider_id):
    """暂停爬虫"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 暂停爬虫
        result = crawler_service.pause_spider(spider_id)
        
        return success_response(data=result, message="爬虫已暂停")
    except Exception as e:
        logger.error(f"暂停爬虫失败: {str(e)}")
        return error_response(message=f"暂停爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/resume', methods=['POST'])
@admin_required
def resume_spider(spider_id):
    """恢复爬虫"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 恢复爬虫
        result = crawler_service.resume_spider(spider_id)
        
        return success_response(data=result, message="爬虫已恢复")
    except Exception as e:
        logger.error(f"恢复爬虫失败: {str(e)}")
        return error_response(message=f"恢复爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/scale', methods=['POST'])
@admin_required
def scale_spider(spider_id):
    """调整爬虫实例数量"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        data = request.get_json()
        if not data or 'instances' not in data:
            return error_response(message="请指定实例数量")
        
        instances = int(data['instances'])
        if instances < 1:
            return error_response(message="实例数量必须大于0")
        
        # 调整实例数量
        result = crawler_service.scale_spider(spider_id, instances)
        
        return success_response(data=result, message=f"爬虫实例数量已调整为 {instances}")
    except Exception as e:
        logger.error(f"调整爬虫实例数量失败: {str(e)}")
        return error_response(message=f"调整爬虫实例数量失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/stats', methods=['GET'])
@login_required
def get_spider_stats(spider_id):
    """获取爬虫统计信息"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 可选的时间范围
        hours = int(request.args.get('hours', 24))
        
        # 获取统计信息
        stats = crawler_service.get_spider_stats(spider_id, hours=hours)
        
        return success_response(data=stats)
    except Exception as e:
        logger.error(f"获取爬虫统计信息失败: {str(e)}")
        return error_response(message=f"获取爬虫统计信息失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/items', methods=['GET'])
@login_required
def get_spider_items(spider_id):
    """获取爬虫采集的数据"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        # 获取采集的数据
        items, total = crawler_service.get_spider_items(
            spider_id, 
            page=page, 
            page_size=page_size
        )
        
        return pagination_response(
            data=items,
            page=page,
            page_size=page_size,
            total=total,
            message="获取数据成功"
        )
    except Exception as e:
        logger.error(f"获取爬虫数据失败: {str(e)}")
        return error_response(message=f"获取爬虫数据失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/queue', methods=['DELETE'])
@admin_required
def clear_spider_queue(spider_id):
    """清空爬虫队列"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 清空队列
        result = crawler_service.clear_queue(spider_id)
        
        return success_response(data=result, message="爬虫队列已清空")
    except Exception as e:
        logger.error(f"清空爬虫队列失败: {str(e)}")
        return error_response(message=f"清空爬虫队列失败: {str(e)}")

@crawler_bp.route('/templates', methods=['GET'])
@login_required
def get_spider_templates():
    """获取爬虫模板列表"""
    try:
        templates = crawler_service.get_spider_templates()
        return success_response(data=templates)
    except Exception as e:
        logger.error(f"获取爬虫模板失败: {str(e)}")
        return error_response(message=f"获取爬虫模板失败: {str(e)}")

@crawler_bp.route('/domains', methods=['GET'])
@login_required
def get_domains():
    """获取已有的域名列表"""
    try:
        domains = crawler_service.get_domains()
        return success_response(data=domains)
    except Exception as e:
        logger.error(f"获取域名列表失败: {str(e)}")
        return error_response(message=f"获取域名列表失败: {str(e)}")

@crawler_bp.route('/tags', methods=['GET'])
@login_required
def get_tags():
    """获取已有的标签列表"""
    try:
        tags = crawler_service.get_tags()
        return success_response(data=tags)
    except Exception as e:
        logger.error(f"获取标签列表失败: {str(e)}")
        return error_response(message=f"获取标签列表失败: {str(e)}")

@crawler_bp.route('/schedule', methods=['POST'])
@admin_required
def schedule_spider():
    """定时调度爬虫任务"""
    try:
        data = request.get_json()
        if not data:
            return error_response(message="无效的请求数据")
        
        # 验证必需字段
        required_fields = ['spider_id', 'schedule_type', 'schedule_value']
        for field in required_fields:
            if field not in data:
                return error_response(message=f"缺少必需的字段: {field}")
        
        # 创建调度
        schedule_id = crawler_service.schedule_spider(
            spider_id=data['spider_id'],
            schedule_type=data['schedule_type'],
            schedule_value=data['schedule_value'],
            arguments=data.get('arguments', {}),
            instances=data.get('instances', 1),
            enabled=data.get('enabled', True),
            description=data.get('description', '')
        )
        
        return success_response(
            data={"schedule_id": schedule_id},
            message="爬虫调度创建成功",
            code=201
        )
    except Exception as e:
        logger.error(f"创建爬虫调度失败: {str(e)}")
        return error_response(message=f"创建爬虫调度失败: {str(e)}")

@crawler_bp.route('/schedule/<schedule_id>', methods=['DELETE'])
@admin_required
def delete_schedule(schedule_id):
    """删除爬虫调度"""
    try:
        # 删除调度
        deleted = crawler_service.delete_schedule(schedule_id)
        if not deleted:
            return error_response(message=f"调度不存在: {schedule_id}", code=404)
        
        return success_response(message="爬虫调度已删除")
    except Exception as e:
        logger.error(f"删除爬虫调度失败: {str(e)}")
        return error_response(message=f"删除爬虫调度失败: {str(e)}")

@crawler_bp.route('/schedule', methods=['GET'])
@login_required
def get_schedules():
    """获取爬虫调度列表"""
    try:
        # 查询参数
        spider_id = request.args.get('spider_id')
        enabled = request.args.get('enabled')
        if enabled is not None:
            enabled = enabled.lower() == 'true'
        
        # 分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 获取调度列表
        schedules, total = crawler_service.get_schedules(
            spider_id=spider_id,
            enabled=enabled,
            page=page,
            page_size=page_size
        )
        
        return pagination_response(
            data=schedules,
            page=page,
            page_size=page_size,
            total=total,
            message="获取爬虫调度列表成功"
        )
    except Exception as e:
        logger.error(f"获取爬虫调度列表失败: {str(e)}")
        return error_response(message=f"获取爬虫调度列表失败: {str(e)}")

@crawler_bp.route('/schedule/<schedule_id>/toggle', methods=['POST'])
@admin_required
def toggle_schedule(schedule_id):
    """启用/禁用爬虫调度"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', True)
        
        # 更新调度状态
        updated = crawler_service.toggle_schedule(schedule_id, enabled)
        if not updated:
            return error_response(message=f"调度不存在: {schedule_id}", code=404)
        
        status = "启用" if enabled else "禁用"
        return success_response(message=f"爬虫调度已{status}")
    except Exception as e:
        logger.error(f"更新爬虫调度状态失败: {str(e)}")
        return error_response(message=f"更新爬虫调度状态失败: {str(e)}")

@crawler_bp.route('/middleware', methods=['GET'])
@admin_required
def get_middleware():
    """获取可用的中间件列表"""
    try:
        middleware = crawler_service.get_middleware()
        return success_response(data=middleware)
    except Exception as e:
        logger.error(f"获取中间件列表失败: {str(e)}")
        return error_response(message=f"获取中间件列表失败: {str(e)}")

@crawler_bp.route('/pipelines', methods=['GET'])
@admin_required
def get_pipelines():
    """获取可用的数据处理管道列表"""
    try:
        pipelines = crawler_service.get_pipelines()
        return success_response(data=pipelines)
    except Exception as e:
        logger.error(f"获取数据处理管道列表失败: {str(e)}")
        return error_response(message=f"获取数据处理管道列表失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/clone', methods=['POST'])
@admin_required
def clone_spider(spider_id):
    """克隆爬虫"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        data = request.get_json() or {}
        new_name = data.get('name', f"{spider['name']}_clone")
        
        # 克隆爬虫
        new_spider_id = crawler_service.clone_spider(
            spider_id, 
            new_name=new_name,
            creator=g.user.get('username')
        )
        
        return success_response(
            data={"spider_id": new_spider_id},
            message="爬虫克隆成功",
            code=201
        )
    except Exception as e:
        logger.error(f"克隆爬虫失败: {str(e)}")
        return error_response(message=f"克隆爬虫失败: {str(e)}")

@crawler_bp.route('/spiders/<spider_id>/export', methods=['GET'])
@login_required
def export_spider(spider_id):
    """导出爬虫配置"""
    try:
        # 验证爬虫是否存在
        spider = crawler_service.get_spider(spider_id)
        if not spider:
            return error_response(message=f"爬虫不存在: {spider_id}", code=404)
        
        # 导出爬虫配置
        config = crawler_service.export_spider_config(spider_id)
        
        # 设置响应头，使浏览器下载文件
        response = jsonify(config)
        response.headers['Content-Disposition'] = f'attachment; filename={spider["name"]}_config.json'
        
        return response
    except Exception as e:
        logger.error(f"导出爬虫配置失败: {str(e)}")
        return error_response(message=f"导出爬虫配置失败: {str(e)}")

@crawler_bp.route('/import', methods=['POST'])
@admin_required
def import_spider():
    """导入爬虫配置"""
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return error_response(message="请上传爬虫配置文件")
        
        file = request.files['file']
        if file.filename == '':
            return error_response(message="未选择文件")
        
        # 读取文件内容
        import json
        try:
            config = json.loads(file.read().decode('utf-8'))
        except json.JSONDecodeError:
            return error_response(message="无效的JSON格式")
        
        # 导入爬虫配置
        spider_id = crawler_service.import_spider_config(
            config, 
            creator=g.user.get('username')
        )
        
        return success_response(
            data={"spider_id": spider_id},
            message="爬虫导入成功",
            code=201
        )
    except Exception as e:
        logger.error(f"导入爬虫配置失败: {str(e)}")
        return error_response(message=f"导入爬虫配置失败: {str(e)}")

@crawler_bp.route('/test-url', methods=['POST'])
@login_required
def test_url():
    """测试URL连通性"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return error_response(message="请提供要测试的URL")
        
        url = data['url']
        use_proxy = data.get('use_proxy', False)
        
        # 测试URL
        result = crawler_service.test_url(url, use_proxy=use_proxy)
        
        return success_response(data=result)
    except Exception as e:
        logger.error(f"测试URL失败: {str(e)}")
        return error_response(message=f"测试URL失败: {str(e)}")

@crawler_bp.route('/test-selector', methods=['POST'])
@login_required
def test_selector():
    """测试CSS/XPath选择器"""
    try:
        data = request.get_json()
        if not data:
            return error_response(message="无效的请求数据")
        
        # 验证必需字段
        required_fields = ['url', 'selector_type', 'selector']
        for field in required_fields:
            if field not in data:
                return error_response(message=f"缺少必需的字段: {field}")
        
        # 测试选择器
        result = crawler_service.test_selector(
            url=data['url'],
            selector_type=data['selector_type'],
            selector=data['selector'],
            use_proxy=data.get('use_proxy', False)
        )
        
        return success_response(data=result)
    except Exception as e:
        logger.error(f"测试选择器失败: {str(e)}")
        return error_response(message=f"测试选择器失败: {str(e)}")

@crawler_bp.route('/test-regex', methods=['POST'])
@login_required
def test_regex():
    """测试正则表达式"""
    try:
        data = request.get_json()
        if not data:
            return error_response(message="无效的请求数据")
        
        # 验证必需字段
        required_fields = ['text', 'regex']
        for field in required_fields:
            if field not in data:
                return error_response(message=f"缺少必需的字段: {field}")
        
        # 测试正则表达式
        result = crawler_service.test_regex(
            text=data['text'],
            regex=data['regex']
        )
        
        return success_response(data=result)
    except Exception as e:
        logger.error(f"测试正则表达式失败: {str(e)}")
        return error_response(message=f"测试正则表达式失败: {str(e)}") 