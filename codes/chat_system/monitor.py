import asyncio
import logging
import time
import os
import psutil
import json
import socket
import random
import traceback
from typing import Dict, Optional, List, Any, Callable, Awaitable
import platform
from datetime import datetime
from collections import deque, defaultdict

# 导入Redis客户端
try:
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
except ImportError:
    # 如果导入失败，main.py中已提供了AsyncRedisWrapper的实现
    from main import AsyncRedisWrapper
    redis_async = AsyncRedisWrapper
    REDIS_AVAILABLE = False

logger = logging.getLogger("SystemMonitor")

class ChatSystemMonitor:
    """
    聊天系统性能监控模块，负责收集和报告系统性能指标
    增强版本支持百万级并发，自动故障检测和恢复策略
    """
    
    def __init__(self, 
                 connection_manager=None, 
                 redis_client=None, 
                 node_id: str = None,
                 check_interval: int = 10,
                 alert_threshold: Dict[str, Dict] = None):
        """
        初始化系统监控器
        
        Args:
            connection_manager: 连接管理器实例
            redis_client: Redis客户端实例
            node_id: 节点ID，如果为None则自动生成
            check_interval: 监控检查间隔(秒)
            alert_threshold: 告警阈值配置
        """
        # 节点标识
        self.node_id = node_id or f"node-{socket.gethostname()}-{os.getpid()}"
        
        # 连接管理器
        self.connection_manager = connection_manager
        
        # Redis客户端
        self.redis_client = redis_client
        
        # 监控配置
        self.check_interval = check_interval
        
        # 默认告警阈值
        self.alert_threshold = {
            "cpu_usage": {
                "warning": 0.7,  # 70%
                "critical": 0.9   # 90%
            },
            "memory_usage": {
                "warning": 0.7,
                "critical": 0.9
            },
            "error_rate": {
                "warning": 0.1,   # 10% 错误率
                "critical": 0.3    # 30% 错误率
            },
            "redis_latency": {
                "warning": 100,    # 100毫秒
                "critical": 500     # 500毫秒
            }
        }
        
        # 更新自定义告警阈值
        if alert_threshold:
            for key, value in alert_threshold.items():
                if key in self.alert_threshold:
                    self.alert_threshold[key].update(value)
                else:
                    self.alert_threshold[key] = value
        
        # 指标数据
        self.metrics = {
            "start_time": time.time(),
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "connections": 0,
            "connections_opened": 0,
            "connections_closed": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "requests": 0,
            "redis_latency": 0.0,
            "node_id": self.node_id,
            "degradation_level": 0,
            "is_healthy": True,
            "last_update": time.time()
        }
        
        # 历史指标数据
        self.history = {
            "cpu_usage": deque(maxlen=60),
            "memory_usage": deque(maxlen=60),
            "connections": deque(maxlen=60),
            "message_rate": deque(maxlen=60)
        }
        
        # 计数器
        self.counters = defaultdict(int)
        self._counter_lock = asyncio.Lock()
        
        # 任务
        self.monitoring_task = None
        self.fault_detection_task = None
        self.cleanup_task = None
        
        # 状态回调
        self.status_callbacks = []
        
        # 当前状态
        self.current_status = {
            "is_healthy": True,
            "degradation_level": 0,
            "alerts": []
        }
        
        # 单机模式下的历史记录（Redis不可用时）
        self.local_history = {}

        # 初始化其他必要属性
        self.running = False
        self.start_time = time.time()
        self.alert_states = {}
        self.fault_counters = defaultdict(int)
        self.metrics_history = []
        self.max_history_size = 1000  # 最多保存1000条历史记录
        self.samples = []
        self.rate_window = 60  # 1分钟速率窗口
        self.last_net_io = None
        self.last_net_io_time = None
        
        # 初始化子指标
        self.metrics["process"] = {
            "cpu_usage": 0.0,
            "memory_usage": 0,
            "memory_percent": 0.0,
            "connections": 0,
            "threads": 0,
            "file_descriptors": 0
        }
        
        self.metrics["system"] = {
            "cpu_usage": 0.0,
            "memory_total": 0,
            "memory_available": 0,
            "memory_percent": 0.0,
            "disk_usage": 0.0,
            "network_io": {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_sent": 0,
                "packets_recv": 0
            }
        }
        
        self.metrics["application"] = {
            "active_connections": 0,
            "active_rooms": 0,
            "message_rate": 0,
            "connection_rate": 0,
            "messages_received": 0,
            "messages_sent": 0,
            "errors": 0,
            "is_degraded": False
        }
        
        self.metrics["status"] = {
            "is_healthy": True,
            "degradation_level": 0,
            "last_error": "",
            "last_error_time": 0
        }
        
        logger.info(f"初始化监控系统，节点ID: {self.node_id}, 模式: {'分布式' if self.redis_client else '单机'}")
        
    def _get_node_id(self) -> str:
        """获取当前节点ID"""
        # 尝试获取环境变量中的节点ID
        node_id = os.environ.get('NODE_ID')
        if node_id:
            return node_id
            
        # 尝试获取主机名
        try:
            hostname = socket.gethostname()
            return f"{hostname}-{os.getpid()}"
        except:
            pass
            
        # 生成随机ID
        import uuid
        return f"node-{uuid.uuid4().hex[:8]}"
    
    def increment_counter(self, counter_name: str, value: int = 1) -> None:
        """
        增加指定计数器的值
        
        Args:
            counter_name: 计数器名称
            value: 增加的值
        """
        if counter_name in self.counters:
            self.counters[counter_name] += value
    
    def register_status_callback(self, callback: Callable[[Dict], Awaitable[None]]) -> None:
        """
        注册状态变更回调函数
        
        Args:
            callback: 状态变更回调函数
        """
        self.status_callbacks.append(callback)
    
    async def _notify_status_change(self, old_status: Dict, new_status: Dict) -> None:
        """
        通知状态变更
        
        Args:
            old_status: 旧的状态
            new_status: 新的状态
        """
        try:
            # 记录状态变更
            change_type = "恢复" if new_status["is_healthy"] else "降级"
            old_level = old_status["degradation_level"]
            new_level = new_status["degradation_level"]
            
            logger.warning(f"系统状态变更: {change_type}, 降级级别: {old_level} -> {new_level}")
            
            # 添加CPU监控信息
            if "process" in self.metrics and "cpu_usage" in self.metrics["process"]:
                new_status["process_cpu"] = self.metrics["process"]["cpu_usage"]
            
            if "system" in self.metrics and "cpu_usage" in self.metrics["system"]:
                new_status["system_cpu"] = self.metrics["system"]["cpu_usage"]
            
            # 添加内存使用率信息
            if "process" in self.metrics and "memory_percent" in self.metrics["process"]:
                new_status["process_memory_percent"] = self.metrics["process"]["memory_percent"]
            
            if "system" in self.metrics and "memory_percent" in self.metrics["system"]:
                new_status["system_memory_percent"] = self.metrics["system"]["memory_percent"]
            
            # 执行状态变更回调
            if self.status_callbacks:
                for callback in self.status_callbacks:
                    try:
                        await callback(new_status)
                    except Exception as e:
                        logger.error(f"状态回调执行错误: {e.__class__.__name__}:{str(e)}")
                        logger.debug(f"回调错误详情: {traceback.format_exc()}")
            
            # 发布状态变更事件
            if self.redis_client:
                try:
                    # 创建异步任务，避免阻塞
                    async def publish_operation():
                        try:
                            await self.redis_client.publish(
                                "system:status_change",
                                json.dumps({
                                    "node_id": self.node_id,
                                    "timestamp": time.time(),
                                    "old_status": old_status,
                                    "new_status": new_status
                                })
                            )
                        except Exception as e:
                            logger.error(f"发布状态变更到Redis错误: {e}")
                    
                    # 设置超时
                    await asyncio.wait_for(publish_operation(), timeout=1.0)
                except asyncio.TimeoutError:
                    logger.warning("发布状态变更到Redis超时")
                except Exception as e:
                    logger.error(f"发布状态变更到Redis错误: {e}")
                
        except Exception as e:
            logger.error(f"状态变更通知失败: {e}")
    
    async def update_metrics(self, app_metrics: Dict = None) -> Dict:
        """
        更新系统指标
        
        Args:
            app_metrics: 应用层指标
            
        Returns:
            更新后的指标
        """
        try:
            process = psutil.Process(os.getpid())
            
            # 更新进程指标
            process_metrics = self.metrics["process"]
            process_metrics["cpu_usage"] = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            process_metrics["memory_usage"] = memory_info.rss
            process_metrics["memory_percent"] = process.memory_percent()
            process_metrics["connections"] = len(process.connections())
            process_metrics["threads"] = process.num_threads()
            
            # 获取文件描述符数量（仅在Unix系统上可用）
            if hasattr(process, 'num_fds'):
                process_metrics["file_descriptors"] = process.num_fds()
            
            # 更新系统指标
            system_metrics = self.metrics["system"]
            system_metrics["cpu_usage"] = psutil.cpu_percent(interval=0.1)
            virtual_memory = psutil.virtual_memory()
            system_metrics["memory_total"] = virtual_memory.total
            system_metrics["memory_available"] = virtual_memory.available
            system_metrics["memory_percent"] = virtual_memory.percent
            disk = psutil.disk_usage('/')
            system_metrics["disk_usage"] = disk.percent
            
            # 更新网络IO指标
            current_net_io = psutil.net_io_counters()
            current_time = time.time()
            
            if self.last_net_io and self.last_net_io_time:
                # 计算变化量
                time_diff = current_time - self.last_net_io_time
                bytes_sent_diff = current_net_io.bytes_sent - self.last_net_io.bytes_sent
                bytes_recv_diff = current_net_io.bytes_recv - self.last_net_io.bytes_recv
                packets_sent_diff = current_net_io.packets_sent - self.last_net_io.packets_sent
                packets_recv_diff = current_net_io.packets_recv - self.last_net_io.packets_recv
                
                # 计算速率
                system_metrics["network_io"] = {
                    "bytes_sent": bytes_sent_diff / time_diff,
                    "bytes_recv": bytes_recv_diff / time_diff,
                    "packets_sent": packets_sent_diff / time_diff,
                    "packets_recv": packets_recv_diff / time_diff
                }
            
            # 保存当前网络IO数据用于下次计算
            self.last_net_io = current_net_io
            self.last_net_io_time = current_time
            
            # 更新应用指标
            if app_metrics:
                self.metrics["application"].update(app_metrics)
            else:
                # 如果没有提供应用指标，获取连接管理器的指标
                if self.connection_manager:
                    try:
                        conn_stats = await self.connection_manager.get_connection_stats()
                        self.metrics["application"]["active_connections"] = conn_stats.get("total_connections", 0)
                        self.metrics["application"]["active_rooms"] = conn_stats.get("active_rooms", 0)
                        self.metrics["application"]["is_degraded"] = conn_stats.get("is_degraded", False)
                    except Exception as e:
                        logger.error(f"获取连接管理器统计信息错误: {e}")
                
                # 更新计数器
                app_metrics = self.metrics["application"]
                app_metrics["messages_received"] = self.counters["messages_received"]
                app_metrics["messages_sent"] = self.counters["messages_sent"]
                app_metrics["errors"] = self.counters["errors"]
            
            # 更新时间戳
            self.metrics["timestamp"] = time.time()
            
            # 保存历史指标
            if len(self.metrics_history) >= self.max_history_size:
                self.metrics_history.pop(0)
            self.metrics_history.append(self.metrics.copy())
            
            # 将数据保存到Redis
            await self._save_to_redis()
            
            # 每次更新指标后检查告警状态
            await self._check_alerts()
            
            return self.metrics
        
        except Exception as e:
            logger.error(f"更新指标错误: {traceback.format_exc()}")
            self.increment_counter("errors")
            self.metrics["status"]["last_error"] = str(e)
            self.metrics["status"]["last_error_time"] = time.time()
            return self.metrics
    
    async def _save_to_redis(self) -> None:
        """将指标保存到Redis"""
        # Redis不可用时跳过
        if not self.redis_client:
            return
        
        try:
            # 使用超时机制，避免阻塞太久
            async def save_operation():
                # 更新指标时间戳
                self.metrics["last_update"] = time.time()
                
                # 序列化指标数据
                metrics_json = json.dumps(self.metrics)
                
                # 将指标保存到Redis哈希表
                await self.redis_client.hset(
                    "monitor:nodes", 
                    self.node_id, 
                    metrics_json
                )
                
                # 设置过期时间（30分钟）
                await self.redis_client.expire("monitor:nodes", 1800)
                
                # 向活跃节点集合添加当前节点
                await self.redis_client.sadd("monitor:active_nodes", self.node_id)
                await self.redis_client.expire("monitor:active_nodes", 1800)
                
                # 保存历史数据
                for metric_name, values in self.history.items():
                    if values:
                        key = f"monitor:history:{self.node_id}:{metric_name}"
                        # 添加最新值到历史列表
                        await self.redis_client.lpush(key, values[-1])
                        # 限制列表长度
                        await self.redis_client.ltrim(key, 0, 599)  # 保留最近600个值（10小时，如果每分钟一个值）
                        # 设置过期时间
                        await self.redis_client.expire(key, 86400)  # 1天
            
            # 设置超时
            try:
                await asyncio.wait_for(save_operation(), timeout=2.0)
            except asyncio.TimeoutError:
                if random.random() < 0.1:  # 降低日志频率
                    logger.warning("保存指标到Redis超时")
                return
                
        except Exception as e:
            # 降低错误日志频率
            if random.random() < 0.1:  # 只有10%的错误会被记录
                logger.error(f"保存指标到Redis失败: {e}")
            return
    
    async def calculate_rates(self) -> Dict:
        """
        计算消息和连接的速率
        
        Returns:
            速率指标
        """
        try:
            current_time = time.time()
            current_sample = {
                "timestamp": current_time,
                "messages_received": self.counters["messages_received"],
                "messages_sent": self.counters["messages_sent"],
                "connections_opened": self.counters["connections_opened"],
                "connections_closed": self.counters["connections_closed"],
                "errors": self.counters["errors"],
                "requests": self.counters["requests"]
            }
            
            # 添加新样本
            self.samples.append(current_sample)
            
            # 移除过期样本
            while self.samples and current_time - self.samples[0]["timestamp"] > self.rate_window:
                self.samples.pop(0)
            
            if len(self.samples) < 2:
                return {
                    "messages_received_rate": 0,
                    "messages_sent_rate": 0,
                    "connections_rate": 0,
                    "error_rate": 0,
                    "request_rate": 0
                }
            
            # 计算速率
            oldest = self.samples[0]
            time_diff = current_time - oldest["timestamp"]
            
            if time_diff <= 0:
                return {
                    "messages_received_rate": 0,
                    "messages_sent_rate": 0,
                    "connections_rate": 0,
                    "error_rate": 0,
                    "request_rate": 0
                }
                
            messages_received_diff = current_sample["messages_received"] - oldest["messages_received"]
            messages_sent_diff = current_sample["messages_sent"] - oldest["messages_sent"]
            connections_opened_diff = current_sample["connections_opened"] - oldest["connections_opened"]
            connections_closed_diff = current_sample["connections_closed"] - oldest["connections_closed"]
            errors_diff = current_sample["errors"] - oldest["errors"]
            requests_diff = current_sample["requests"] - oldest["requests"]
            
            # 计算错误率
            error_rate = 0
            if requests_diff > 0:
                error_rate = errors_diff / requests_diff
            
            rates = {
                "messages_received_rate": messages_received_diff / time_diff,
                "messages_sent_rate": messages_sent_diff / time_diff,
                "connections_opened_rate": connections_opened_diff / time_diff,
                "connections_closed_rate": connections_closed_diff / time_diff,
                "net_connection_rate": (connections_opened_diff - connections_closed_diff) / time_diff,
                "error_rate": error_rate,
                "request_rate": requests_diff / time_diff
            }
            
            # 更新应用指标中的速率
            self.metrics["application"]["message_rate"] = rates["messages_received_rate"]
            self.metrics["application"]["connection_rate"] = rates["connections_opened_rate"]
            
            return rates
        except Exception as e:
            logger.error(f"计算速率错误: {e}")
            # 返回默认值，避免计算错误导致系统崩溃
            return {
                "messages_received_rate": 0,
                "messages_sent_rate": 0,
                "connections_rate": 0,
                "error_rate": 0,
                "request_rate": 0
            }
    
    async def _check_alerts(self) -> None:
        """检查系统指标是否超过告警阈值"""
        try:
            # 获取当前指标
            cpu_usage = max(self.metrics["process"]["cpu_usage"], self.metrics["system"]["cpu_usage"])
            memory_usage = max(self.metrics["process"]["memory_percent"], self.metrics["system"]["memory_percent"])
            
            # 计算错误率
            rates = await self.calculate_rates()
            error_rate = rates.get("error_rate", 0)  # 使用get方法避免KeyError
            
            # 确保所有必要的阈值键存在
            for key in ["cpu_usage", "memory_usage", "error_rate"]:
                if key not in self.alert_threshold:
                    self.alert_threshold[key] = {"warning": 0.7, "critical": 0.9}
                    if key == "error_rate":
                        self.alert_threshold[key] = {"warning": 0.1, "critical": 0.3}
                    logger.warning(f"添加缺失的告警阈值: {key}")
            
            # 检查CPU告警
            await self._check_alert_threshold("cpu_usage", cpu_usage)
            
            # 检查内存告警
            await self._check_alert_threshold("memory_usage", memory_usage)
            
            # 检查错误率告警
            await self._check_alert_threshold("error_rate", error_rate)
            
            # 检查Redis延迟
            if self.redis_client:
                try:
                    redis_latency = await self._check_redis_latency()
                    await self._check_alert_threshold("redis_latency", redis_latency)
                except Exception as e:
                    logger.error(f"Redis延迟检查失败: {e}")
            
            # 更新健康状态
            old_health_status = self.metrics["status"]["is_healthy"]
            old_degradation = self.metrics["status"]["degradation_level"]
            
            # 判断健康状态
            is_healthy = True
            degradation_level = 0
            
            # 检查CPU和内存是否处于危急状态
            if (cpu_usage >= self.alert_threshold["cpu_usage"]["critical"] or 
                memory_usage >= self.alert_threshold["memory_usage"]["critical"] or
                error_rate >= self.alert_threshold.get("error_rate", {}).get("critical", 0.3)):
                is_healthy = False
                degradation_level = 3  # 严重降级
            # 检查是否处于警告状态
            elif (cpu_usage >= self.alert_threshold["cpu_usage"]["warning"] or 
                  memory_usage >= self.alert_threshold["memory_usage"]["warning"] or
                  error_rate >= self.alert_threshold.get("error_rate", {}).get("warning", 0.1)):
                is_healthy = True  # 仍然健康，但处于警告状态
                degradation_level = 1  # 轻度降级
            
            # 更新健康状态
            self.metrics["status"]["is_healthy"] = is_healthy
            self.metrics["status"]["degradation_level"] = degradation_level
            
            # 如果健康状态或降级级别发生变化，通知回调
            if old_health_status != is_healthy or old_degradation != degradation_level:
                try:
                    await self._notify_status_change(
                        {"is_healthy": old_health_status, "degradation_level": old_degradation},
                        {"is_healthy": is_healthy, "degradation_level": degradation_level}
                    )
                except Exception as e:
                    logger.error(f"状态变更通知失败: {e}")
        except Exception as e:
            logger.error(f"检查告警错误: {e}")
            # 不要让异常传播出去，以免影响监控循环
    
    async def _check_redis_latency(self) -> float:
        """
        检查Redis延迟
        
        Returns:
            Redis操作延迟（毫秒）
        """
        if not self.redis_client:
            return 0.0
            
        try:
            # 设置超时，避免长时间阻塞
            start_time = time.time()
            
            # 创建一个任务，设置超时
            ping_task = asyncio.create_task(self.redis_client.ping())
            try:
                await asyncio.wait_for(ping_task, timeout=2.0)  # 最多等待2秒
                end_time = time.time()
                
                # 计算延迟（毫秒）
                latency = (end_time - start_time) * 1000
                return latency
            except asyncio.TimeoutError:
                logger.warning("Redis操作超时")
                self.fault_counters["redis_errors"] += 1
                return 9999.0  # 返回一个大值表示错误
                
        except Exception as e:
            # 减少日志输出频率，避免日志爆炸
            if random.random() < 0.1:  # 只有10%的错误会被记录
                logger.error(f"Redis延迟检查错误: {e}")
            self.fault_counters["redis_errors"] += 1
            return 9999.0  # 返回一个大值表示错误
    
    async def _check_alert_threshold(self, metric_name: str, current_value: float) -> bool:
        """
        检查指标是否超过告警阈值
        
        Args:
            metric_name: 指标名称
            current_value: 当前值
            
        Returns:
            是否触发告警
        """
        # 确保告警阈值存在
        if metric_name not in self.alert_threshold:
            # 设置默认阈值
            if metric_name == "error_rate":
                self.alert_threshold[metric_name] = {"warning": 0.1, "critical": 0.3}
            else:
                self.alert_threshold[metric_name] = {"warning": 0.7, "critical": 0.9}
            
            logger.warning(f"为指标 {metric_name} 设置默认告警阈值")
        
        # 获取告警阈值
        thresholds = self.alert_threshold[metric_name]
        
        # 获取当前告警状态
        old_state = self.alert_states.get(metric_name, "normal")
        
        # 检查是否超过临界阈值
        if current_value >= thresholds.get("critical", 0.9):
            new_state = "critical"
        # 检查是否超过警告阈值
        elif current_value >= thresholds.get("warning", 0.7):
            new_state = "warning"
        else:
            new_state = "normal"
        
        # 如果告警状态变更，记录日志
        if old_state != new_state:
            if new_state == "critical":
                logger.warning(f"指标 {metric_name} 超过临界阈值: {current_value:.2f} >= {thresholds.get('critical', 0.9):.2f}")
            elif new_state == "warning":
                logger.warning(f"指标 {metric_name} 超过警告阈值: {current_value:.2f} >= {thresholds.get('warning', 0.7):.2f}")
            elif old_state != "normal":  # 从告警状态恢复到正常
                logger.info(f"指标 {metric_name} 恢复正常: {current_value:.2f}")
        
        # 更新告警状态
        self.alert_states[metric_name] = new_state
        
        # 返回是否触发告警
        return new_state != "normal"
    
    async def start_monitoring(self, interval: int = None) -> None:
        """
        启动定期监控任务
        
        Args:
            interval: 监控间隔(秒)，如果未提供则使用默认值
        """
        if self.running:
            logger.warning("监控任务已经在运行")
            return
            
        self.running = True
        if interval:
            self.check_interval = interval
            
        logger.info(f"启动系统监控，节点ID: {self.node_id}")
        
        # 启动监控任务
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
        # 启动故障检测任务
        self.fault_detector_task = asyncio.create_task(self._fault_detection_loop())
        
        # 启动清理任务
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _monitoring_loop(self) -> None:
        """主监控循环，定期更新指标"""
        try:
            while self.running:
                # 更新指标
                await self.update_metrics()
                
                # 计算速率
                rates = await self.calculate_rates()
                
                # 每分钟输出一次日志
                if int(time.time()) % 60 < self.check_interval:
                    system_cpu = self.metrics["system"]["cpu_usage"]
                    process_cpu = self.metrics["process"]["cpu_usage"]
                    memory_percent = self.metrics["process"]["memory_percent"]
                    connections = self.metrics["application"]["active_connections"]
                    msg_rate = rates["messages_received_rate"]
                    
                    logger.info(
                        f"系统状态 - CPU: {system_cpu:.1f}%, 进程CPU: {process_cpu:.1f}%, "
                        f"内存: {memory_percent:.1f}%, 连接数: {connections}, 消息速率: {msg_rate:.1f}/秒"
                    )
                
                # 等待下一个检查周期
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info("监控任务被取消")
        except Exception as e:
            logger.error(f"监控任务错误: {traceback.format_exc()}")
            self.metrics["status"]["is_healthy"] = False
            self.metrics["status"]["last_error"] = str(e)
            self.metrics["status"]["last_error_time"] = time.time()
    
    async def _fault_detection_loop(self) -> None:
        """故障检测循环，定期检查系统状态和外部依赖"""
        logger.info("启动故障检测循环")
        
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                # 检查Redis连接健康状态
                redis_healthy = True
                if self.redis_client:
                    try:
                        # 测量Redis响应时间
                        redis_latency = await self._check_redis_latency()
                        redis_healthy = redis_latency < self.alert_threshold["redis_latency"]["critical"]
                        
                        # 更新Redis延迟指标
                        self.metrics["redis_latency"] = redis_latency
                        
                        # 如果Redis健康状态变更，记录日志
                        if redis_healthy != self.metrics.get("redis_healthy", True):
                            if redis_healthy:
                                logger.info("Redis连接已恢复")
                            else:
                                logger.warning(f"Redis连接异常，延迟: {redis_latency:.6f}秒")
                        
                        self.metrics["redis_healthy"] = redis_healthy
                    except Exception as e:
                        logger.error(f"检查Redis健康状态失败: {e}")
                        self.metrics["redis_healthy"] = False
                        redis_healthy = False
                
                # 检查连接管理器状态
                if self.connection_manager:
                    try:
                        conn_stats = await self.connection_manager.get_connection_stats()
                        
                        # 更新连接数指标
                        self.metrics["connections"] = conn_stats["total_connections"]
                        
                        # 检测连接管理器是否处于降级模式
                        if conn_stats["is_degraded"] != self.metrics.get("cm_degraded", False):
                            if conn_stats["is_degraded"]:
                                logger.warning("连接管理器进入降级模式")
                            else:
                                logger.info("连接管理器退出降级模式")
                        
                        self.metrics["cm_degraded"] = conn_stats["is_degraded"]
                        self.metrics["cm_healthy"] = conn_stats["healthy"]
                        
                    except Exception as e:
                        logger.error(f"检查连接管理器状态失败: {e}")
                        self.metrics["cm_healthy"] = False
                
                # 更新系统整体健康状态
                old_status = self.current_status.copy()
                new_status = {
                    "is_healthy": all([
                        self.metrics.get("redis_healthy", True),
                        self.metrics.get("cm_healthy", True),
                        self.metrics["cpu_usage"] < self.alert_threshold["cpu_usage"]["critical"],
                        self.metrics["memory_usage"] < self.alert_threshold["memory_usage"]["critical"]
                    ]),
                    "degradation_level": self._calculate_degradation_level(),
                    "alerts": self.metrics.get("alerts", [])
                }
                
                # 如果状态变更，通知回调
                if (old_status["is_healthy"] != new_status["is_healthy"] or 
                    old_status["degradation_level"] != new_status["degradation_level"]):
                    
                    self.current_status = new_status
                    await self._notify_status_change(old_status, new_status)
                
            except Exception as e:
                logger.error(f"故障检测循环错误: {e}")
    
    async def _cleanup_loop(self) -> None:
        """清理循环，定期清理过期数据和无效节点"""
        try:
            while self.running:
                # 每小时执行一次清理
                await asyncio.sleep(3600)
                
                # 清理历史指标，避免内存泄漏
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history = self.metrics_history[-self.max_history_size:]
                
                # 检查并清理Redis中过期的节点
                if self.redis_client:
                    try:
                        # 获取所有活跃节点
                        active_nodes = await self.redis_client.smembers("monitor:active_nodes")
                        active_nodes = [node.decode('utf-8') for node in active_nodes]
                        
                        # 获取最后活跃时间
                        last_seen = await self.redis_client.hgetall("monitor:nodes:last_seen")
                        
                        # 清理超过1小时未活跃的节点
                        current_time = time.time()
                        for node in active_nodes:
                            if node.encode('utf-8') in last_seen:
                                node_last_seen = float(last_seen[node.encode('utf-8')])
                                if current_time - node_last_seen > 3600:  # 1小时
                                    logger.info(f"清理过期节点: {node}")
                                    await self.redis_client.srem("monitor:active_nodes", node)
                                    await self.redis_client.hdel("monitor:nodes:last_seen", node)
                                    
                    except Exception as e:
                        logger.error(f"清理过期节点错误: {e}")
                        
        except asyncio.CancelledError:
            logger.info("清理任务被取消")
        except Exception as e:
            logger.error(f"清理任务错误: {e}")
    
    async def get_system_status(self) -> Dict:
        """
        获取系统状态摘要
        
        Returns:
            系统状态摘要
        """
        # 计算正常运行时间
        uptime = time.time() - self.start_time
        uptime_str = self._format_uptime(uptime)
        
        # 获取最新指标
        cpu_usage = max(self.metrics["process"]["cpu_usage"], self.metrics["system"]["cpu_usage"])
        memory_percent = self.metrics["process"]["memory_percent"]
        active_connections = self.metrics["application"]["active_connections"]
        
        # 获取速率
        rates = await self.calculate_rates()
        
        status = {
            "node_id": self.node_id,
            "hostname": platform.node(),
            "uptime": uptime_str,
            "uptime_seconds": uptime,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "resources": {
                "cpu": cpu_usage,
                "memory": memory_percent,
                "memory_used": self._format_size(self.metrics["process"]["memory_usage"]),
                "memory_total": self._format_size(self.metrics["system"]["memory_total"]),
                "disk_usage": self.metrics["system"]["disk_usage"]
            },
            "application": {
                "connections": active_connections,
                "rooms": self.metrics["application"]["active_rooms"],
                "message_rate": rates["messages_received_rate"],
                "connection_rate": rates["connections_opened_rate"],
                "error_rate": rates["error_rate"] * 100  # 转为百分比
            },
            "health": {
                "is_healthy": self.metrics["status"]["is_healthy"],
                "degradation_level": self.metrics["status"]["degradation_level"],
                "redis_connected": self.redis_client is not None,
                "last_error": self.metrics["status"]["last_error"],
                "last_error_time": self.metrics["status"]["last_error_time"]
            },
            "timestamp": time.time()
        }
        
        return status
    
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """
        格式化正常运行时间
        
        Args:
            seconds: 正常运行时间（秒）
            
        Returns:
            格式化后的正常运行时间字符串
        """
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0 or parts:
            parts.append(f"{hours}小时")
        if minutes > 0 or parts:
            parts.append(f"{minutes}分钟")
        parts.append(f"{seconds}秒")
        
        return "".join(parts)
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 文件大小（字节）
            
        Returns:
            格式化后的文件大小字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    
    async def shutdown(self) -> None:
        """关闭监控模块"""
        logger.info("关闭系统监控...")
        
        # 停止监控
        self.running = False
        
        # 取消任务
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            
        if self.fault_detector_task and not self.fault_detector_task.done():
            self.fault_detector_task.cancel()
            
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            
        # 等待任务完成
        tasks = []
        for task in [self.monitor_task, self.fault_detector_task, self.cleanup_task]:
            if task and not task.done():
                tasks.append(task)
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        # 更新Redis中的节点状态为离线
        if self.redis_client:
            try:
                await self.redis_client.srem("monitor:active_nodes", self.node_id)
                await self.redis_client.hdel("monitor:nodes:last_seen", self.node_id)
                
                # 发布下线通知
                await self.redis_client.publish("system:node_offline", json.dumps({
                    "node_id": self.node_id,
                    "timestamp": time.time()
                }))
            except Exception as e:
                logger.error(f"更新Redis节点状态错误: {e}")
        
        logger.info("系统监控已关闭")
    
    def _calculate_degradation_level(self) -> int:
        """计算当前降级级别"""
        # 检查资源使用情况
        cpu_usage = max(self.metrics["process"]["cpu_usage"], self.metrics["system"]["cpu_usage"])
        memory_usage = max(self.metrics["process"]["memory_percent"], self.metrics["system"]["memory_percent"])
        
        # 根据资源使用情况确定降级级别
        if cpu_usage >= 95 or memory_usage >= 95:
            return 3  # 严重降级
        elif cpu_usage >= 85 or memory_usage >= 85:
            return 2  # 中度降级
        elif cpu_usage >= 75 or memory_usage >= 75:
            return 1  # 轻度降级
        else:
            return 0  # 正常
    
    async def stop_monitoring(self) -> None:
        """关闭监控模块"""
        logger.info("关闭系统监控...")
        
        # 停止监控
        self.running = False
        
        # 取消任务
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            
        if self.fault_detection_task and not self.fault_detection_task.done():
            self.fault_detection_task.cancel()
            
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            
        # 等待任务完成
        tasks = []
        for task in [self.monitoring_task, self.fault_detection_task, self.cleanup_task]:
            if task and not task.done():
                tasks.append(task)
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        # 更新Redis中的节点状态为离线
        if self.redis_client:
            try:
                await self.redis_client.srem("monitor:active_nodes", self.node_id)
                await self.redis_client.hdel("monitor:nodes:last_seen", self.node_id)
                
                # 发布下线通知
                await self.redis_client.publish("system:node_offline", json.dumps({
                    "node_id": self.node_id,
                    "timestamp": time.time()
                }))
            except Exception as e:
                logger.error(f"更新Redis节点状态错误: {e}")
        
        logger.info("系统监控已关闭")
        
    def get_monitoring_data(self) -> Dict[str, Any]:
        """获取监控数据"""
        return {
            "cpu_usage": max(self.metrics["process"]["cpu_usage"], self.metrics["system"]["cpu_usage"]),
            "memory_usage": self.metrics["process"]["memory_percent"],
            "connections": self.metrics["application"]["active_connections"],
            "degradation_level": self.metrics["status"]["degradation_level"],
            "is_healthy": self.metrics["status"]["is_healthy"],
            "redis_latency": self.metrics["redis_latency"],
            "timestamp": time.time()
        }
        
    def get_historical_data(self, hours: int = 1) -> Dict[str, List]:
        """获取历史监控数据"""
        result = {"timestamps": [], "cpu": [], "memory": [], "connections": []}
        
        # 限制小时数
        hours = min(hours, 24)
        
        # 如果没有历史数据，返回空结果
        if not self.metrics_history:
            return result
            
        # 计算时间范围
        start_time = time.time() - (hours * 3600)
        
        # 过滤数据
        for entry in self.metrics_history:
            if entry["timestamp"] >= start_time:
                result["timestamps"].append(entry["timestamp"])
                result["cpu"].append(max(entry["process"]["cpu_usage"], entry["system"]["cpu_usage"]))
                result["memory"].append(entry["process"]["memory_percent"])
                result["connections"].append(entry["application"]["active_connections"])
                
        return result 