from flask import Blueprint, request, jsonify, g
from services.scheduler import SchedulerService
from utils.auth import token_required, admin_required
from utils.response import success_response, error_response
import logging

logger = logging.getLogger(__name__)

# 初始化蓝图
bp = Blueprint('scheduler', __name__, url_prefix='/api/schedules')

# 获取调度服务实例
def get_scheduler_service():
    from app import get_mongo_uri, get_redis_url
    from services.crawler import CrawlerService
    
    if not hasattr(g, 'scheduler_service'):
        # 先获取爬虫服务
        if not hasattr(g, 'crawler_service'):
            g.crawler_service = CrawlerService(get_redis_url(), get_mongo_uri())
        
        # 使用爬虫服务初始化调度服务
        g.scheduler_service = SchedulerService(
            get_mongo_uri(),
            get_redis_url(),
            g.crawler_service
        )
    
    return g.scheduler_service

@bp.route('/', methods=['GET'])
@token_required
def get_schedules():
    """获取调度计划列表"""
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    spider_id = request.args.get('spider_id')
    
    scheduler_service = get_scheduler_service()
    schedules, total = scheduler_service.get_schedules(spider_id, page, page_size)
    
    return success_response({
        "schedules": schedules,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@bp.route('/<schedule_id>', methods=['GET'])
@token_required
def get_schedule(schedule_id):
    """获取指定调度计划"""
    scheduler_service = get_scheduler_service()
    schedule = scheduler_service.schedules.find_one({'schedule_id': schedule_id})
    
    if not schedule:
        return error_response("调度计划不存在", 404)
    
    # 移除MongoDB的_id字段
    if '_id' in schedule:
        del schedule['_id']
        
    return success_response(schedule)

@bp.route('/', methods=['POST'])
@token_required
def create_schedule():
    """创建新调度计划"""
    data = request.json
    
    # 验证请求数据
    if 'spider_id' not in data:
        return error_response("缺少必填字段: spider_id", 400)
    
    scheduler_service = get_scheduler_service()
    schedule, error = scheduler_service.create_schedule(data['spider_id'], data)
    
    if error:
        return error_response(error, 400)
    
    return success_response(schedule, "创建调度计划成功")

@bp.route('/<schedule_id>', methods=['PUT'])
@token_required
def update_schedule(schedule_id):
    """更新调度计划"""
    data = request.json
    
    scheduler_service = get_scheduler_service()
    result = scheduler_service.update_schedule(schedule_id, data)
    
    if result:
        return success_response({}, "更新调度计划成功")
    else:
        return error_response("更新失败，调度计划可能不存在", 400)

@bp.route('/<schedule_id>', methods=['DELETE'])
@token_required
def delete_schedule(schedule_id):
    """删除调度计划"""
    scheduler_service = get_scheduler_service()
    result = scheduler_service.delete_schedule(schedule_id)
    
    if result:
        return success_response({}, "删除调度计划成功")
    else:
        return error_response("删除失败，调度计划可能不存在", 400)

@bp.route('/<schedule_id>/enable', methods=['POST'])
@token_required
def enable_schedule(schedule_id):
    """启用调度计划"""
    scheduler_service = get_scheduler_service()
    result = scheduler_service.enable_schedule(schedule_id, True)
    
    if result:
        return success_response({}, "启用调度计划成功")
    else:
        return error_response("操作失败，调度计划可能不存在", 400)

@bp.route('/<schedule_id>/disable', methods=['POST'])
@token_required
def disable_schedule(schedule_id):
    """禁用调度计划"""
    scheduler_service = get_scheduler_service()
    result = scheduler_service.enable_schedule(schedule_id, False)
    
    if result:
        return success_response({}, "禁用调度计划成功")
    else:
        return error_response("操作失败，调度计划可能不存在", 400)

@bp.route('/types', methods=['GET'])
@token_required
def get_schedule_types():
    """获取可用的调度类型"""
    schedule_types = [
        {
            "value": "once",
            "label": "一次性",
            "description": "只执行一次的任务"
        },
        {
            "value": "interval",
            "label": "间隔执行",
            "description": "按固定时间间隔重复执行"
        }
    ]
    
    interval_units = [
        {"value": "minutes", "label": "分钟"},
        {"value": "hours", "label": "小时"},
        {"value": "days", "label": "天"},
        {"value": "weeks", "label": "周"}
    ]
    
    return success_response({
        "schedule_types": schedule_types,
        "interval_units": interval_units
    }) 