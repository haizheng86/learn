#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统服务
提供系统配置、资源管理和状态控制
"""

import os
import psutil
import logging
import redis
import json
import subprocess
import threading
import shutil
from datetime import datetime, timedelta
from pymongo import MongoClient
from kubernetes import client, config

# 配置日志
logger = logging.getLogger('services.system')

class SystemService:
    """系统服务，管理系统配置和资源"""
    
    def __init__(self, redis_url, mongo_uri, kubernetes_enabled=False, kubernetes_namespace='default'):
        """
        初始化系统服务
        :param redis_url: Redis连接URL
        :param mongo_uri: MongoDB连接URI
        :param kubernetes_enabled: 是否启用Kubernetes
        :param kubernetes_namespace: Kubernetes命名空间
        """
        # 连接Redis
        self.redis = redis.from_url(redis_url)
        
        # 连接MongoDB
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client.crawler_db
        self.config_collection = self.db.system_config
        self.backup_collection = self.db.system_backups
        
        # Kubernetes配置
        self.kubernetes_enabled = kubernetes_enabled
        self.kubernetes_namespace = kubernetes_namespace
        
        # 如果启用了Kubernetes，初始化客户端
        if kubernetes_enabled:
            try:
                # 加载集群配置
                config.load_incluster_config()
                self.k8s_apps_api = client.AppsV1Api()
                self.k8s_core_api = client.CoreV1Api()
                logger.info("已成功初始化Kubernetes客户端")
            except Exception as e:
                logger.error(f"初始化Kubernetes客户端失败: {str(e)}")
                self.kubernetes_enabled = False
        
        # 配置文件路径
        self.config_file_path = os.environ.get('CONFIG_FILE_PATH', '/app/config.json')
        
        # 日志文件目录
        self.log_dir = os.environ.get('LOG_DIR', '/app/logs')
        
        # 备份目录
        self.backup_dir = os.environ.get('BACKUP_DIR', '/app/backups')
        
        # 确保目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        logger.info("系统服务初始化完成")
    
    def get_system_info(self):
        """
        获取系统基本信息
        :return: 系统信息字典
        """
        info = {
            "version": os.environ.get('APP_VERSION', '1.0.0'),
            "python_version": subprocess.check_output(["python", "--version"]).decode().strip(),
            "environment": os.environ.get('ENVIRONMENT', 'production'),
            "hostname": os.environ.get('HOSTNAME', 'localhost'),
            "start_time": self.get_start_time(),
            "components": self.get_component_versions()
        }
        
        return info
    
    def get_component_versions(self):
        """
        获取系统组件版本信息
        :return: 组件版本字典
        """
        components = {}
        
        # Redis版本
        try:
            redis_info = self.redis.info()
            components["redis"] = redis_info.get("redis_version", "未知")
        except:
            components["redis"] = "未连接"
        
        # MongoDB版本
        try:
            mongo_info = self.mongo_client.server_info()
            components["mongodb"] = mongo_info.get("version", "未知")
        except:
            components["mongodb"] = "未连接"
        
        # Kubernetes版本
        if self.kubernetes_enabled:
            try:
                version_info = self.k8s_core_api.get_api_versions()
                components["kubernetes"] = str(version_info)
            except:
                components["kubernetes"] = "未连接"
        else:
            components["kubernetes"] = "未启用"
        
        return components
    
    def get_start_time(self):
        """
        获取系统启动时间
        :return: 启动时间字符串
        """
        try:
            start_time_file = os.path.join(self.log_dir, 'start_time.txt')
            if os.path.exists(start_time_file):
                with open(start_time_file, 'r') as f:
                    return f.read().strip()
            else:
                # 如果文件不存在，获取当前进程的启动时间
                process = psutil.Process(os.getpid())
                start_time = datetime.fromtimestamp(process.create_time()).strftime("%Y-%m-%d %H:%M:%S")
                
                # 写入文件
                with open(start_time_file, 'w') as f:
                    f.write(start_time)
                    
                return start_time
        except:
            return "未知"
    
    def get_system_status(self):
        """
        获取系统运行状态
        :return: 状态信息字典
        """
        # 获取系统资源使用情况
        resources = self.get_system_resources()
        
        # 获取Redis连接状态
        redis_connected = False
        try:
            self.redis.ping()
            redis_connected = True
        except:
            pass
        
        # 获取MongoDB连接状态
        mongo_connected = False
        try:
            self.mongo_client.admin.command('ping')
            mongo_connected = True
        except:
            pass
        
        # 获取爬虫任务状态
        spider_stats = {
            "total": self.db.spiders.count_documents({}),
            "running": self.db.spiders.count_documents({"status": "running"}),
            "paused": self.db.spiders.count_documents({"status": "paused"}),
            "idle": self.db.spiders.count_documents({"status": "idle"}),
            "stopped": self.db.spiders.count_documents({"status": "stopped"})
        }
        
        # 获取最近错误数
        recent_errors_count = self.db.error_stats.count_documents({
            "timestamp": {"$gte": datetime.now() - timedelta(hours=24)}
        })
        
        return {
            "health": "healthy" if redis_connected and mongo_connected else "unhealthy",
            "redis_connected": redis_connected,
            "mongo_connected": mongo_connected,
            "resources": {
                "cpu_usage": resources["cpu_percent"],
                "memory_usage": resources["memory_percent"],
                "disk_usage": resources["disk_percent"]
            },
            "spiders": spider_stats,
            "recent_errors": recent_errors_count,
            "uptime": self.get_uptime()
        }
    
    def get_uptime(self):
        """
        获取系统运行时间
        :return: 运行时间（秒）
        """
        try:
            start_time_file = os.path.join(self.log_dir, 'start_time.txt')
            if os.path.exists(start_time_file):
                with open(start_time_file, 'r') as f:
                    start_time_str = f.read().strip()
                    start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    uptime = (datetime.now() - start_time).total_seconds()
                    return uptime
            else:
                # 如果文件不存在，获取当前进程的运行时间
                process = psutil.Process(os.getpid())
                uptime = (datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
                return uptime
        except:
            return 0
    
    def update_config(self, config_data):
        """
        更新系统配置
        :param config_data: 配置数据字典
        :return: 更新的配置项数量
        """
        updated = 0
        
        # 更新配置文件
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r') as f:
                    current_config = json.load(f)
            else:
                current_config = {}
                
            # 更新配置
            for key, value in config_data.items():
                current_config[key] = value
                updated += 1
            
            # 写入配置文件
            with open(self.config_file_path, 'w') as f:
                json.dump(current_config, f, indent=2)
                
            # 同时写入Redis，用于实时配置
            self.redis.set('system:config', json.dumps(current_config))
            
            # 同时写入MongoDB，用于持久化
            self.config_collection.update_one(
                {"type": "system_config"},
                {"$set": {"config": current_config, "updated_at": datetime.now()}},
                upsert=True
            )
            
            logger.info(f"已更新 {updated} 个配置项")
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            raise e
            
        return updated
    
    def get_system_resources(self):
        """
        获取系统资源使用情况
        :return: 资源使用情况字典
        """
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        
        # 网络IO
        net_io = psutil.net_io_counters()
        
        # 进程信息
        process = psutil.Process(os.getpid())
        process_info = {
            "cpu_percent": process.cpu_percent(interval=0.1),
            "memory_percent": process.memory_percent(),
            "threads": process.num_threads(),
            "open_files": len(process.open_files()),
            "connections": len(process.connections())
        }
        
        return {
            "cpu_percent": cpu_percent,
            "memory_total": memory.total,
            "memory_used": memory.used,
            "memory_percent": memory.percent,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "disk_percent": disk.percent,
            "net_io_sent": net_io.bytes_sent,
            "net_io_recv": net_io.bytes_recv,
            "process": process_info,
            "timestamp": datetime.now()
        }
    
    def get_logs(self, log_type='app', lines=100):
        """
        获取系统日志
        :param log_type: 日志类型 (app, error, access)
        :param lines: 返回的行数
        :return: 日志内容列表
        """
        log_file = os.path.join(self.log_dir, f'{log_type}.log')
        
        if not os.path.exists(log_file):
            logger.warning(f"日志文件不存在: {log_file}")
            return []
        
        try:
            # 使用tail命令获取最后N行
            output = subprocess.check_output(['tail', '-n', str(lines), log_file]).decode()
            log_lines = output.splitlines()
            
            # 解析日志行
            result = []
            for line in log_lines:
                try:
                    # 尝试解析JSON格式日志
                    log_entry = json.loads(line)
                    result.append(log_entry)
                except:
                    # 普通文本日志
                    result.append({"message": line, "timestamp": None, "level": None})
            
            return result
        except Exception as e:
            logger.error(f"获取日志失败: {str(e)}")
            return []
    
    def restart_service(self, service='all'):
        """
        重启系统服务
        :param service: 服务名称 (all, web, worker, scheduler)
        :return: 操作结果
        """
        if not self.kubernetes_enabled:
            logger.warning("未启用Kubernetes，无法重启服务")
            return {"success": False, "message": "未启用Kubernetes，无法重启服务"}
        
        try:
            if service == 'all':
                # 重启所有服务
                services = ['web', 'worker', 'scheduler']
                for svc in services:
                    self._restart_k8s_deployment(svc)
                return {"success": True, "message": "已重启所有服务"}
            else:
                # 重启指定服务
                self._restart_k8s_deployment(service)
                return {"success": True, "message": f"已重启服务 {service}"}
        except Exception as e:
            logger.error(f"重启服务失败: {str(e)}")
            return {"success": False, "message": f"重启服务失败: {str(e)}"}
    
    def _restart_k8s_deployment(self, service_name):
        """
        重启Kubernetes部署
        :param service_name: 服务名称
        """
        try:
            # 获取部署
            deployment = self.k8s_apps_api.read_namespaced_deployment(
                name=f"crawler-{service_name}",
                namespace=self.kubernetes_namespace
            )
            
            # 更新重启注解
            if deployment.spec.template.metadata.annotations is None:
                deployment.spec.template.metadata.annotations = {}
            
            deployment.spec.template.metadata.annotations['kubectl.kubernetes.io/restartedAt'] = datetime.now().isoformat()
            
            # 更新部署
            self.k8s_apps_api.patch_namespaced_deployment(
                name=f"crawler-{service_name}",
                namespace=self.kubernetes_namespace,
                body=deployment
            )
            
            logger.info(f"服务 {service_name} 正在重启")
        except Exception as e:
            logger.error(f"重启服务 {service_name} 失败: {str(e)}")
            raise e
    
    def get_nodes(self):
        """
        获取集群节点信息
        :return: 节点信息列表
        """
        if not self.kubernetes_enabled:
            logger.warning("未启用Kubernetes，无法获取节点信息")
            return []
        
        try:
            # 获取所有节点
            nodes = self.k8s_core_api.list_node()
            
            result = []
            for node in nodes.items:
                # 解析节点状态
                conditions = {cond.type: cond.status for cond in node.status.conditions}
                
                # 解析资源信息
                allocatable = node.status.allocatable
                capacity = node.status.capacity
                
                node_info = {
                    "name": node.metadata.name,
                    "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
                    "cpu_allocatable": allocatable.get("cpu", "未知"),
                    "memory_allocatable": allocatable.get("memory", "未知"),
                    "cpu_capacity": capacity.get("cpu", "未知"),
                    "memory_capacity": capacity.get("memory", "未知"),
                    "kernel_version": node.status.node_info.kernel_version,
                    "os_image": node.status.node_info.os_image,
                    "container_runtime": node.status.node_info.container_runtime_version,
                    "kubelet_version": node.status.node_info.kubelet_version
                }
                
                result.append(node_info)
            
            return result
        except Exception as e:
            logger.error(f"获取节点信息失败: {str(e)}")
            return []
    
    def create_backup(self, backup_type='full'):
        """
        创建系统备份
        :param backup_type: 备份类型 (full, config, data)
        :return: 备份结果
        """
        backup_id = f"{backup_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        backup_path = os.path.join(self.backup_dir, backup_id)
        
        def backup_task():
            try:
                # 创建备份目录
                os.makedirs(backup_path, exist_ok=True)
                
                # 记录备份开始
                self.backup_collection.insert_one({
                    "backup_id": backup_id,
                    "type": backup_type,
                    "started_at": datetime.now(),
                    "status": "in_progress",
                    "path": backup_path
                })
                
                if backup_type in ['full', 'config']:
                    # 备份配置文件
                    if os.path.exists(self.config_file_path):
                        shutil.copy2(self.config_file_path, os.path.join(backup_path, 'config.json'))
                    
                    # 备份系统配置集合
                    self._backup_mongodb_collection('system_config', backup_path)
                
                if backup_type in ['full', 'data']:
                    # 备份爬虫配置
                    self._backup_mongodb_collection('spiders', backup_path)
                    
                    # 备份每日统计数据
                    self._backup_mongodb_collection('daily_stats', backup_path)
                    
                    # 备份错误统计
                    self._backup_mongodb_collection('error_stats', backup_path)
                
                # 记录备份完成
                self.backup_collection.update_one(
                    {"backup_id": backup_id},
                    {
                        "$set": {
                            "completed_at": datetime.now(),
                            "status": "completed",
                            "size": self._get_directory_size(backup_path)
                        }
                    }
                )
                
                logger.info(f"备份 {backup_id} 完成")
                
            except Exception as e:
                logger.error(f"备份失败: {str(e)}")
                
                # 记录备份失败
                self.backup_collection.update_one(
                    {"backup_id": backup_id},
                    {
                        "$set": {
                            "completed_at": datetime.now(),
                            "status": "failed",
                            "error": str(e)
                        }
                    }
                )
        
        # 启动异步备份任务
        threading.Thread(target=backup_task).start()
        
        return {
            "backup_id": backup_id,
            "type": backup_type,
            "started_at": datetime.now(),
            "status": "in_progress",
            "message": "备份任务已启动，请稍后查看结果"
        }
    
    def _backup_mongodb_collection(self, collection_name, backup_path):
        """
        备份MongoDB集合
        :param collection_name: 集合名称
        :param backup_path: 备份路径
        """
        collection = self.db[collection_name]
        documents = list(collection.find({}))
        
        # 将ObjectId转换为字符串
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        # 写入JSON文件
        with open(os.path.join(backup_path, f'{collection_name}.json'), 'w') as f:
            json.dump(documents, f, indent=2, default=str)
    
    def _get_directory_size(self, path):
        """
        获取目录大小
        :param path: 目录路径
        :return: 目录大小（字节）
        """
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size
    
    def get_backups(self):
        """
        获取备份列表
        :return: 备份列表
        """
        backups = list(self.backup_collection.find(
            {},
            {"_id": 0, "backup_id": 1, "type": 1, "started_at": 1, "completed_at": 1, 
             "status": 1, "size": 1, "error": 1}
        ).sort("started_at", -1))
        
        return backups
    
    def restore_backup(self, backup_id):
        """
        恢复备份
        :param backup_id: 备份ID
        :return: 恢复结果
        """
        # 获取备份信息
        backup = self.backup_collection.find_one({"backup_id": backup_id})
        if not backup:
            logger.warning(f"备份 {backup_id} 不存在")
            return {"success": False, "message": f"备份 {backup_id} 不存在"}
        
        backup_path = backup.get("path")
        if not backup_path or not os.path.exists(backup_path):
            logger.warning(f"备份路径 {backup_path} 不存在")
            return {"success": False, "message": f"备份路径不存在"}
        
        def restore_task():
            try:
                # 记录恢复开始
                restore_id = f"restore_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                self.backup_collection.insert_one({
                    "restore_id": restore_id,
                    "backup_id": backup_id,
                    "started_at": datetime.now(),
                    "status": "in_progress"
                })
                
                backup_type = backup.get("type", "full")
                
                if backup_type in ['full', 'config']:
                    # 恢复配置文件
                    config_file = os.path.join(backup_path, 'config.json')
                    if os.path.exists(config_file):
                        shutil.copy2(config_file, self.config_file_path)
                    
                    # 恢复系统配置集合
                    self._restore_mongodb_collection('system_config', backup_path)
                
                if backup_type in ['full', 'data']:
                    # 恢复爬虫配置
                    self._restore_mongodb_collection('spiders', backup_path)
                    
                    # 恢复每日统计数据
                    self._restore_mongodb_collection('daily_stats', backup_path)
                    
                    # 恢复错误统计
                    self._restore_mongodb_collection('error_stats', backup_path)
                
                # 记录恢复完成
                self.backup_collection.update_one(
                    {"restore_id": restore_id},
                    {
                        "$set": {
                            "completed_at": datetime.now(),
                            "status": "completed"
                        }
                    }
                )
                
                logger.info(f"恢复 {restore_id} 完成")
                
            except Exception as e:
                logger.error(f"恢复失败: {str(e)}")
                
                # 记录恢复失败
                self.backup_collection.update_one(
                    {"restore_id": restore_id},
                    {
                        "$set": {
                            "completed_at": datetime.now(),
                            "status": "failed",
                            "error": str(e)
                        }
                    }
                )
        
        # 启动异步恢复任务
        threading.Thread(target=restore_task).start()
        
        return {
            "backup_id": backup_id,
            "started_at": datetime.now(),
            "status": "in_progress",
            "message": "恢复任务已启动，请稍后查看结果"
        }
    
    def _restore_mongodb_collection(self, collection_name, backup_path):
        """
        恢复MongoDB集合
        :param collection_name: 集合名称
        :param backup_path: 备份路径
        """
        json_file = os.path.join(backup_path, f'{collection_name}.json')
        if not os.path.exists(json_file):
            logger.warning(f"备份文件 {json_file} 不存在，跳过恢复 {collection_name}")
            return
        
        try:
            # 读取JSON文件
            with open(json_file, 'r') as f:
                documents = json.load(f)
            
            if not documents:
                logger.warning(f"备份文件 {json_file} 为空，跳过恢复 {collection_name}")
                return
            
            # 清空集合
            self.db[collection_name].delete_many({})
            
            # 恢复数据
            for doc in documents:
                # 处理ObjectId
                if '_id' in doc and isinstance(doc['_id'], str):
                    try:
                        from bson.objectid import ObjectId
                        doc['_id'] = ObjectId(doc['_id'])
                    except:
                        # 如果无法转换为ObjectId，则删除_id字段
                        del doc['_id']
            
            # 批量插入
            self.db[collection_name].insert_many(documents)
            
            logger.info(f"恢复集合 {collection_name} 完成，共 {len(documents)} 条记录")
            
        except Exception as e:
            logger.error(f"恢复集合 {collection_name} 失败: {str(e)}")
            raise e 