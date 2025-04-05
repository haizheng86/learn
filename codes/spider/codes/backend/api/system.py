#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统管理API
提供系统配置、资源管理和状态控制的接口
"""

import logging
from flask import Blueprint, request, jsonify
from services.system import SystemService
from utils.response import success_response, error_response
from utils.auth import login_required, admin_required
from config import REDIS_URL, MONGO_URI, KUBERNETES_ENABLED, KUBERNETES_NAMESPACE

# 创建蓝图
system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# 配置日志
logger = logging.getLogger('api.system')

# 初始化系统服务
system_service = SystemService(
    redis_url=REDIS_URL,
    mongo_uri=MONGO_URI,
    kubernetes_enabled=KUBERNETES_ENABLED,
    kubernetes_namespace=KUBERNETES_NAMESPACE
)

@system_bp.route('/info', methods=['GET'])
@login_required
def get_system_info():
    """获取系统基本信息"""
    try:
        info = system_service.get_system_info()
        return success_response(data=info)
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        return error_response(message=f"获取系统信息失败: {str(e)}")

@system_bp.route('/status', methods=['GET'])
@login_required
def get_system_status():
    """获取系统运行状态"""
    try:
        status = system_service.get_system_status()
        return success_response(data=status)
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}")
        return error_response(message=f"获取系统状态失败: {str(e)}")

@system_bp.route('/config', methods=['GET'])
@admin_required
def get_system_config():
    """获取系统配置"""
    try:
        # 从Redis获取配置
        config_data = system_service.redis.get('system:config')
        if not config_data:
            return success_response(data={})
        
        import json
        config = json.loads(config_data)
        
        # 过滤敏感信息
        sensitive_keys = ['password', 'secret', 'key', 'token']
        for key in list(config.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                config[key] = "******"
        
        return success_response(data=config)
    except Exception as e:
        logger.error(f"获取系统配置失败: {str(e)}")
        return error_response(message=f"获取系统配置失败: {str(e)}")

@system_bp.route('/config', methods=['POST'])
@admin_required
def update_system_config():
    """更新系统配置"""
    try:
        config_data = request.get_json()
        if not config_data:
            return error_response(message="无效的配置数据")
        
        # 过滤不允许修改的配置项
        disallowed_keys = ['version', 'installed_at', 'license']
        filtered_config = {k: v for k, v in config_data.items() if k not in disallowed_keys}
        
        if not filtered_config:
            return error_response(message="没有可更新的配置项")
        
        # 更新配置
        updated = system_service.update_config(filtered_config)
        
        return success_response(data={"updated_count": updated})
    except Exception as e:
        logger.error(f"更新系统配置失败: {str(e)}")
        return error_response(message=f"更新系统配置失败: {str(e)}")

@system_bp.route('/resources', methods=['GET'])
@login_required
def get_system_resources():
    """获取系统资源使用情况"""
    try:
        resources = system_service.get_system_resources()
        return success_response(data=resources)
    except Exception as e:
        logger.error(f"获取系统资源使用情况失败: {str(e)}")
        return error_response(message=f"获取系统资源使用情况失败: {str(e)}")

@system_bp.route('/logs', methods=['GET'])
@admin_required
def get_system_logs():
    """获取系统日志"""
    try:
        log_type = request.args.get('type', 'app')
        lines = int(request.args.get('lines', 100))
        
        logs = system_service.get_logs(log_type=log_type, lines=lines)
        return success_response(data=logs)
    except Exception as e:
        logger.error(f"获取系统日志失败: {str(e)}")
        return error_response(message=f"获取系统日志失败: {str(e)}")

@system_bp.route('/restart', methods=['POST'])
@admin_required
def restart_service():
    """重启系统服务"""
    try:
        data = request.get_json()
        service = data.get('service', 'all')
        
        result = system_service.restart_service(service=service)
        if result['success']:
            return success_response(message=result['message'])
        else:
            return error_response(message=result['message'])
    except Exception as e:
        logger.error(f"重启服务失败: {str(e)}")
        return error_response(message=f"重启服务失败: {str(e)}")

@system_bp.route('/nodes', methods=['GET'])
@admin_required
def get_nodes():
    """获取集群节点信息"""
    try:
        nodes = system_service.get_nodes()
        return success_response(data=nodes)
    except Exception as e:
        logger.error(f"获取节点信息失败: {str(e)}")
        return error_response(message=f"获取节点信息失败: {str(e)}")

@system_bp.route('/backup', methods=['POST'])
@admin_required
def create_backup():
    """创建系统备份"""
    try:
        data = request.get_json()
        backup_type = data.get('type', 'full')
        
        result = system_service.create_backup(backup_type=backup_type)
        return success_response(data=result)
    except Exception as e:
        logger.error(f"创建备份失败: {str(e)}")
        return error_response(message=f"创建备份失败: {str(e)}")

@system_bp.route('/backups', methods=['GET'])
@admin_required
def get_backups():
    """获取系统备份列表"""
    try:
        backups = system_service.get_backups()
        return success_response(data=backups)
    except Exception as e:
        logger.error(f"获取备份列表失败: {str(e)}")
        return error_response(message=f"获取备份列表失败: {str(e)}")

@system_bp.route('/restore', methods=['POST'])
@admin_required
def restore_backup():
    """恢复系统备份"""
    try:
        data = request.get_json()
        backup_id = data.get('backup_id')
        
        if not backup_id:
            return error_response(message="备份ID不能为空")
        
        result = system_service.restore_backup(backup_id=backup_id)
        
        if 'success' in result and not result['success']:
            return error_response(message=result['message'])
        
        return success_response(data=result)
    except Exception as e:
        logger.error(f"恢复备份失败: {str(e)}")
        return error_response(message=f"恢复备份失败: {str(e)}")

@system_bp.route('/version', methods=['GET'])
def get_version():
    """获取系统版本信息（公开接口）"""
    try:
        import os
        version = os.environ.get('APP_VERSION', '1.0.0')
        return success_response(data={"version": version})
    except Exception as e:
        logger.error(f"获取版本信息失败: {str(e)}")
        return error_response(message=f"获取版本信息失败: {str(e)}") 