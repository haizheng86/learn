import asyncio
import logging
import os
import time
import threading
import json
import random
from typing import Dict, Optional, Callable, Awaitable, List, Tuple, Any
import multiprocessing
import psutil
import concurrent.futures
from functools import partial
import uuid

logger = logging.getLogger("ResourceScheduler")

class DynamicResourceScheduler:
    """
    动态资源调度器，根据系统负载动态调整资源分配
    支持百万级并发系统的资源管理
    包含服务降级策略和自适应资源分配
    """
    
    def __init__(self, 
                 min_processes: int = None, 
                 max_processes: int = None,
                 min_coroutines: int = 1000,
                 max_coroutines: int = 100000,
                 cpu_high_threshold: float = 75.0,
                 cpu_low_threshold: float = 25.0,
                 memory_high_threshold: float = 80.0,
                 memory_low_threshold: float = 40.0,
                 check_interval: int = 10,
                 cooldown_period: int = 60,
                 degradation_levels: List[Dict] = None):
        """
        初始化资源调度器
        
        Args:
            min_processes: 最小进程数
            max_processes: 最大进程数
            min_coroutines: 最小协程数
            max_coroutines: 最大协程数
            cpu_high_threshold: CPU使用率高阈值，超过此值考虑扩容
            cpu_low_threshold: CPU使用率低阈值，低于此值考虑缩容
            memory_high_threshold: 内存使用率高阈值
            memory_low_threshold: 内存使用率低阈值
            check_interval: 检查间隔时间(秒)
            cooldown_period: 扩缩容冷却期(秒)
            degradation_levels: 服务降级级别配置
        """
        # 进程池配置
        self.min_processes = min_processes or max(2, os.cpu_count() // 2)
        self.max_processes = max_processes or os.cpu_count() * 2
        self.current_processes = self.min_processes
        
        # 协程池配置
        self.min_coroutines = min_coroutines
        self.max_coroutines = max_coroutines
        self.current_coroutines = min_coroutines
        
        # 阈值设置
        self.cpu_high_threshold = cpu_high_threshold
        self.cpu_low_threshold = cpu_low_threshold
        self.memory_high_threshold = memory_high_threshold
        self.memory_low_threshold = memory_low_threshold
        
        # 时间配置
        self.check_interval = check_interval
        self.cooldown_period = cooldown_period
        self.last_scale_time = 0
        
        # 资源使用监控
        self.cpu_samples = []
        self.memory_samples = []
        self.sample_window = 300  # 5分钟样本窗口
        self.max_samples = self.sample_window // check_interval
        
        # 任务队列和管理
        self.task_queue = asyncio.Queue()
        self.priority_queue = asyncio.PriorityQueue()  # 优先级队列
        self.process_pool = None
        self.thread_pool = None
        self.process_semaphore = None  # 控制进程任务并发
        self.coroutine_semaphore = None  # 控制协程任务并发
        
        # 任务统计
        self.task_stats = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "in_queue": 0,
            "processing": 0,
            "avg_process_time": 0,
            "avg_queue_time": 0,
            "by_type": {}
        }
        
        # 服务降级设置
        self.degradation_level = 0  # 0表示正常，越高表示降级程度越严重
        self.is_degraded = False
        
        # 默认降级级别配置
        self.degradation_levels = degradation_levels or [
            {
                "level": 0,
                "name": "正常",
                "description": "系统正常运行，所有功能可用",
                "cpu_threshold": 75,
                "memory_threshold": 80,
                "task_queue_threshold": 1000,
                "actions": {}
            },
            {
                "level": 1,
                "name": "轻度降级",
                "description": "系统负载较高，部分非核心功能受限",
                "cpu_threshold": 85,
                "memory_threshold": 85,
                "task_queue_threshold": 5000,
                "actions": {
                    "reject_low_priority": True,
                    "increase_sampling": True,
                    "disable_history_features": False
                }
            },
            {
                "level": 2,
                "name": "中度降级",
                "description": "系统负载高，只保留核心功能",
                "cpu_threshold": 90,
                "memory_threshold": 90, 
                "task_queue_threshold": 10000,
                "actions": {
                    "reject_low_priority": True,
                    "increase_sampling": True,
                    "disable_history_features": True,
                    "limit_message_rate": True
                }
            },
            {
                "level": 3,
                "name": "重度降级",
                "description": "系统过载，只支持最基本功能",
                "cpu_threshold": 95,
                "memory_threshold": 95,
                "task_queue_threshold": 20000,
                "actions": {
                    "reject_low_priority": True,
                    "increase_sampling": True,
                    "disable_history_features": True,
                    "limit_message_rate": True,
                    "reject_new_connections": True,
                    "disable_persistence": True
                }
            }
        ]
        
        # 状态回调函数
        self.status_change_callback = None
        
        # 新增属性
        self.initialized = False
        self.workers = set()
        self.workers_to_close = set()
        self.scale_step = 100  # 新增属性
        self.default_workers = 10  # 新增属性
        
    async def initialize_scheduler(self):
        """初始化调度器"""
        # 设置事件循环策略（如果uvloop可用）
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("使用uvloop作为事件循环")
        except ImportError:
            logger.info("uvloop不可用，使用标准asyncio事件循环")
        
        # 创建工作线程池
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_processes,
            thread_name_prefix="resource_worker"
        )
        
        # 启动工作协程
        for i in range(self.default_workers):
            worker_id = f"worker-{i}"
            self.workers.add(worker_id)
            asyncio.create_task(self.worker(worker_id))
        
        # 启动优先级工作协程
        for i in range(3):  # 3个优先级工作器
            worker_id = f"priority-worker-{i}"
            self.workers.add(worker_id)
            asyncio.create_task(self.priority_worker(worker_id))
        
        # 启动资源监控
        self.monitoring_task = asyncio.create_task(self.monitor_resources())
        
        # 初始化完成标记
        self.initialized = True
        logger.info("资源调度器初始化完成")
        return self
    
    async def monitor_resources(self):
        """监控系统资源使用情况，并根据需要调整资源分配"""
        while True:
            try:
                # 收集系统指标
                metrics = await self.collect_metrics()
                
                # 检查是否需要调整资源
                decisions = await self.should_scale_resources()
                
                # 应用扩缩容决策
                if decisions["should_scale_processes"] or decisions["should_scale_coroutines"]:
                    await self._apply_scaling_decisions(decisions)
                    self.last_scale_time = time.time()
                
                # 检查并执行服务降级策略
                await self._check_degradation_level(metrics)
                
                # 等待下一个检查周期
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"资源监控错误: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def collect_metrics(self) -> Dict:
        """
        收集系统资源指标
        
        Returns:
            收集到的指标
        """
        process = psutil.Process(os.getpid())
        
        # 进程CPU使用率
        process_cpu = process.cpu_percent(interval=0.1)
        
        # 系统CPU使用率
        system_cpu = psutil.cpu_percent(interval=0.1)
        
        # 进程内存使用
        memory_info = process.memory_info()
        process_memory = memory_info.rss
        process_memory_percent = process.memory_percent()
        
        # 系统内存使用
        system_memory = psutil.virtual_memory()
        
        # 任务队列状态
        task_queue_size = self.task_queue.qsize()
        priority_queue_size = self.priority_queue.qsize()
        
        # 更新样本
        current_time = time.time()
        
        self.cpu_samples.append({
            "timestamp": current_time,
            "process_cpu": process_cpu,
            "system_cpu": system_cpu
        })
        
        self.memory_samples.append({
            "timestamp": current_time,
            "process_memory_percent": process_memory_percent,
            "system_memory_percent": system_memory.percent
        })
        
        # 保持样本窗口大小
        while len(self.cpu_samples) > self.max_samples:
            self.cpu_samples.pop(0)
            
        while len(self.memory_samples) > self.max_samples:
            self.memory_samples.pop(0)
        
        metrics = {
            "process_cpu": process_cpu,
            "system_cpu": system_cpu,
            "process_memory": process_memory,
            "process_memory_percent": process_memory_percent,
            "system_memory_percent": system_memory.percent,
            "current_processes": self.current_processes,
            "current_coroutines": self.current_coroutines,
            "task_queue_size": task_queue_size,
            "priority_queue_size": priority_queue_size,
            "degradation_level": self.degradation_level,
            "is_degraded": self.is_degraded
        }
        
        # 更新任务统计数据
        self.task_stats["in_queue"] = task_queue_size + priority_queue_size
        
        return metrics
    
    def _calculate_average_metrics(self) -> Dict:
        """
        计算平均指标值
        
        Returns:
            平均指标
        """
        if not self.cpu_samples or not self.memory_samples:
            return {
                "avg_process_cpu": 0,
                "avg_system_cpu": 0,
                "avg_process_memory_percent": 0,
                "avg_system_memory_percent": 0
            }
        
        # 计算CPU平均值
        avg_process_cpu = sum(sample["process_cpu"] for sample in self.cpu_samples) / len(self.cpu_samples)
        avg_system_cpu = sum(sample["system_cpu"] for sample in self.cpu_samples) / len(self.cpu_samples)
        
        # 计算内存平均值
        avg_process_memory_percent = sum(sample["process_memory_percent"] for sample in self.memory_samples) / len(self.memory_samples)
        avg_system_memory_percent = sum(sample["system_memory_percent"] for sample in self.memory_samples) / len(self.memory_samples)
        
        return {
            "avg_process_cpu": avg_process_cpu,
            "avg_system_cpu": avg_system_cpu,
            "avg_process_memory_percent": avg_process_memory_percent,
            "avg_system_memory_percent": avg_system_memory_percent
        }
    
    async def should_scale_resources(self) -> Dict:
        """
        判断是否需要调整资源分配
        
        Returns:
            资源调整决策
        """
        # 计算平均指标
        avg_metrics = self._calculate_average_metrics()
        
        # 资源调整决策
        decisions = {
            "should_scale_processes": False,
            "should_scale_coroutines": False,
            "new_processes": self.current_processes,
            "new_coroutines": self.current_coroutines,
            "reason": ""
        }
        
        # 检查是否在冷却期
        current_time = time.time()
        if current_time - self.last_scale_time < self.cooldown_period:
            decisions["reason"] = f"在冷却期内，还剩 {int(self.cooldown_period - (current_time - self.last_scale_time))} 秒"
            return decisions
        
        # 基于CPU使用率的进程扩缩容决策
        avg_cpu = max(avg_metrics["avg_process_cpu"], avg_metrics["avg_system_cpu"])
        
        if avg_cpu > self.cpu_high_threshold and self.current_processes < self.max_processes:
            # CPU使用率高，需要增加进程数
            new_processes = min(self.current_processes + 2, self.max_processes)
            decisions["should_scale_processes"] = True
            decisions["new_processes"] = new_processes
            decisions["reason"] = f"CPU使用率 ({avg_cpu:.1f}%) 超过阈值 ({self.cpu_high_threshold}%)，增加进程数"
            
        elif avg_cpu < self.cpu_low_threshold and self.current_processes > self.min_processes:
            # CPU使用率低，可以减少进程数
            new_processes = max(self.current_processes - 1, self.min_processes)
            decisions["should_scale_processes"] = True
            decisions["new_processes"] = new_processes
            decisions["reason"] = f"CPU使用率 ({avg_cpu:.1f}%) 低于阈值 ({self.cpu_low_threshold}%)，减少进程数"
        
        # 基于内存使用率和任务队列的协程扩缩容决策
        avg_memory = max(avg_metrics["avg_process_memory_percent"], avg_metrics["avg_system_memory_percent"])
        queue_size = self.task_queue.qsize() + self.priority_queue.qsize()
        
        # 根据队列大小动态调整协程数
        if queue_size > self.current_coroutines * 0.8 and self.current_coroutines < self.max_coroutines:
            # 队列较大，增加协程数
            new_coroutines = min(
                int(self.current_coroutines * 1.5),  # 增加50%
                self.max_coroutines
            )
            decisions["should_scale_coroutines"] = True
            decisions["new_coroutines"] = new_coroutines
            decisions["reason"] = f"任务队列较大 ({queue_size})，增加协程数"
            
        elif queue_size < self.current_coroutines * 0.2 and self.current_coroutines > self.min_coroutines:
            # 队列较小，减少协程数
            new_coroutines = max(
                int(self.current_coroutines * 0.8),  # 减少20%
                self.min_coroutines
            )
            decisions["should_scale_coroutines"] = True
            decisions["new_coroutines"] = new_coroutines
            decisions["reason"] = f"任务队列较小 ({queue_size})，减少协程数"
            
        # 根据内存使用率调整协程数
        if avg_memory > self.memory_high_threshold and not decisions["should_scale_coroutines"]:
            # 内存使用率高，减少协程数
            new_coroutines = max(
                int(self.current_coroutines * 0.7),  # 减少30%
                self.min_coroutines
            )
            decisions["should_scale_coroutines"] = True
            decisions["new_coroutines"] = new_coroutines
            decisions["reason"] = f"内存使用率高 ({avg_memory:.1f}%)，减少协程数"
        
        return decisions
    
    async def _apply_scaling_decisions(self, decisions: Dict) -> bool:
        """应用扩容/缩容决策"""
        try:
            changes_made = False
            
            # 扩容工作协程
            if decisions.get("scale_up_coroutines", False):
                target = min(self.max_coroutines, self.current_coroutines + self.scale_step)
                to_add = target - self.current_coroutines
                
                if to_add > 0:
                    logger.info(f"扩容协程数量: +{to_add} (当前: {self.current_coroutines}, 目标: {target})")
                    # 添加普通工作协程
                    for i in range(to_add):
                        worker_id = f"worker-{len(self.workers)}"
                        self.workers.add(worker_id)
                        asyncio.create_task(self.worker(worker_id))
                    
                    self.current_coroutines = target
                    changes_made = True
            
            # 缩容工作协程
            elif decisions.get("scale_down_coroutines", False):
                target = max(self.min_coroutines, self.current_coroutines - self.scale_step)
                to_remove = self.current_coroutines - target
                
                if to_remove > 0:
                    logger.info(f"缩容协程数量: -{to_remove} (当前: {self.current_coroutines}, 目标: {target})")
                    # 标记部分工作协程为待关闭
                    normal_workers = [w for w in self.workers if not w.startswith("priority")]
                    # 保留优先级工作器
                    to_remove = min(to_remove, len(normal_workers) - self.default_workers)
                    
                    if to_remove > 0:
                        for worker_id in normal_workers[-to_remove:]:
                            self.workers_to_close.add(worker_id)
                        
                        self.current_coroutines = target
                        changes_made = True
            
            # 扩容工作线程
            if decisions.get("scale_up_threads", False):
                # 使用已有的线程池，无法动态扩容
                # 在下一次初始化时会调整线程池大小
                pass
            
            # 缩容工作线程
            elif decisions.get("scale_down_threads", False):
                # 线程池无法动态缩容
                pass
            
            return changes_made
        except Exception as e:
            logger.error(f"应用扩缩容决策失败: {e}")
            return False
    
    async def _check_degradation_level(self, metrics: Dict):
        """
        检查是否需要调整服务降级级别
        
        Args:
            metrics: 系统指标
        """
        # 检查metrics是否包含必要的字段
        if not isinstance(metrics, dict):
            logger.warning(f"传入的metrics不是字典: {type(metrics)}")
            return

        # 获取当前指标，使用get方法避免KeyError
        cpu_usage = max(
            metrics.get("process_cpu", 0),
            metrics.get("system_cpu", 0)
        )
        memory_usage = max(
            metrics.get("process_memory_percent", 0),
            metrics.get("system_memory_percent", 0)
        )
        
        # 获取队列大小，如果不存在则默认为0
        queue_size = metrics.get("task_queue_size", 0)
        if "priority_queue_size" in metrics:
            queue_size += metrics.get("priority_queue_size", 0)
        
        # 当前降级级别
        current_level = self.degradation_level
        new_level = current_level
        
        # 检查是否需要提升降级级别
        for level in sorted(self.degradation_levels, key=lambda x: x["level"], reverse=True):
            if (cpu_usage >= level["cpu_threshold"] or 
                memory_usage >= level["memory_threshold"] or 
                queue_size >= level["task_queue_threshold"]):
                new_level = level["level"]
                break
        
        # 检查是否可以降低降级级别
        if new_level == current_level and current_level > 0:
            # 获取当前级别的上一级
            for level in sorted(self.degradation_levels, key=lambda x: x["level"]):
                if level["level"] < current_level:
                    potential_level = level["level"]
                    
                    # 只有当所有指标都低于阈值的80%时才降级
                    if (cpu_usage < level["cpu_threshold"] * 0.8 and
                        memory_usage < level["memory_threshold"] * 0.8 and
                        queue_size < level["task_queue_threshold"] * 0.8):
                        new_level = potential_level
        
        # 应用新的降级级别
        if new_level != current_level:
            old_level_name = next((l["name"] for l in self.degradation_levels if l["level"] == current_level), "未知")
            new_level_name = next((l["name"] for l in self.degradation_levels if l["level"] == new_level), "未知")
            
            logger.warning(f"服务降级级别变更: {old_level_name}({current_level}) -> {new_level_name}({new_level})")
            
            self.degradation_level = new_level
            self.is_degraded = new_level > 0
            
            # 调用状态变更回调
            if self.status_change_callback:
                await self.status_change_callback(
                    old_level=current_level,
                    new_level=new_level,
                    metrics=metrics
                )
    
    def register_status_change_callback(self, callback: Callable[[Dict], Awaitable[None]]):
        """
        注册状态变更回调函数
        
        Args:
            callback: 回调函数
        """
        self.status_change_callback = callback
    
    async def submit_task(self, task_type: str, func: Callable, priority: int = 5, **kwargs) -> Dict:
        """
        提交任务到调度队列
        
        参数:
            task_type: 任务类型（例如: 'io', 'cpu', 'mixed'）
            func: 要执行的异步函数
            priority: 优先级 (1-10，1最高)
            **kwargs: 传递给func的参数
            
        返回:
            任务结果信息
        """
        if not self.initialized:
            raise RuntimeError("调度器未初始化")
        
        # 根据当前降级级别检查是否允许提交非关键任务
        current_level = self.current_degradation_level
        
        # 检查降级级别下是否允许此类型任务
        if current_level > 0 and task_type not in self.degradation_levels[current_level].get("allowed_tasks", []):
            logger.warning(f"当前处于降级级别 {current_level}，拒绝 {task_type} 类型任务")
            return {
                "success": False, 
                "error": f"服务降级，拒绝 {task_type} 类型任务",
                "degradation_level": current_level
            }
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务对象
        task = {
            "id": task_id,
            "type": task_type,
            "func": func,
            "kwargs": kwargs,
            "priority": max(1, min(10, priority)),  # 确保优先级在1-10范围内
            "created_at": time.time(),
            "status": "pending",
            "result": None,
            "error": None
        }
        
        # 添加到任务统计
        self.task_stats["submitted"] += 1
        self.task_stats["by_type"][task_type] = self.task_stats["by_type"].get(task_type, 0) + 1
        
        try:
            # 高优先级任务使用优先级队列
            if task["priority"] <= 3:
                await self.priority_queue.put(task)
            else:
                # 根据任务类型选择队列
                if task_type == "io":
                    await self.io_task_queue.put(task)
                elif task_type == "cpu":
                    await self.cpu_task_queue.put(task)
                else:  # 默认或mixed类型
                    await self.default_task_queue.put(task)
            
            logger.debug(f"任务已提交: {task_id} (类型: {task_type}, 优先级: {priority})")
            return {"success": True, "task_id": task_id}
            
        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            self.task_stats["failed"] += 1
            return {"success": False, "error": str(e)}
    
    async def worker(self, worker_id: str):
        """
        任务工作器，处理普通队列中的任务
        
        Args:
            worker_id: 工作器ID
        """
        logger.info(f"启动工作器 {worker_id}")
        
        while True:
            try:
                # 从队列获取任务
                task = await self.task_queue.get()
                
                # 处理任务
                await self._process_task(task)
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info(f"工作器 {worker_id} 被取消")
                break
                
            except Exception as e:
                logger.error(f"工作器 {worker_id} 错误: {e}")
                await asyncio.sleep(1)  # 避免错误导致CPU过度使用
    
    async def priority_worker(self, worker_id: str):
        """
        优先级任务工作器，处理优先级队列中的任务
        
        Args:
            worker_id: 工作器ID
        """
        logger.info(f"启动优先级工作器 {worker_id}")
        
        while True:
            try:
                # 从优先级队列获取任务
                _, task = await self.priority_queue.get()
                
                # 处理任务
                await self._process_task(task)
                
                # 标记任务完成
                self.priority_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info(f"优先级工作器 {worker_id} 被取消")
                break
                
            except Exception as e:
                logger.error(f"优先级工作器 {worker_id} 错误: {e}")
                await asyncio.sleep(1)  # 避免错误导致CPU过度使用
    
    async def _process_task(self, task: Dict):
        """
        处理单个任务
        
        Args:
            task: 任务信息
        """
        task_id = task["id"]
        task_type = task["type"]
        func = task["func"]
        kwargs = task["kwargs"]
        
        # 更新任务状态
        task["status"] = "processing"
        task["start_time"] = time.time()
        
        self.task_stats["processing"] += 1
        
        try:
            # 根据任务类型选择执行方式
            if task_type == "cpu":
                # CPU密集型任务使用进程池
                async with self.process_semaphore:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        self.process_pool,
                        partial(func, **kwargs)
                    )
                    
            elif task_type == "io":
                # IO密集型任务使用协程
                async with self.coroutine_semaphore:
                    result = await func(**kwargs)
                    
            elif task_type == "mixed":
                # 混合型任务使用线程池
                async with self.coroutine_semaphore:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        self.thread_pool,
                        partial(func, **kwargs)
                    )
            else:
                # 默认使用协程
                async with self.coroutine_semaphore:
                    result = await func(**kwargs)
            
            # 更新任务状态
            task["status"] = "completed"
            task["result"] = result
            task["end_time"] = time.time()
            
            # 更新统计信息
            self.task_stats["completed"] += 1
            process_time = task["end_time"] - task["start_time"]
            queue_time = task["start_time"] - task["submit_time"]
            
            # 更新平均处理时间（使用移动平均）
            if self.task_stats["completed"] == 1:
                self.task_stats["avg_process_time"] = process_time
                self.task_stats["avg_queue_time"] = queue_time
            else:
                self.task_stats["avg_process_time"] = (
                    self.task_stats["avg_process_time"] * 0.9 + process_time * 0.1
                )
                self.task_stats["avg_queue_time"] = (
                    self.task_stats["avg_queue_time"] * 0.9 + queue_time * 0.1
                )
            
            logger.debug(f"任务完成: {task_id}, 处理时间: {process_time:.3f}秒")
            
        except Exception as e:
            # 更新任务状态
            task["status"] = "failed"
            task["error"] = str(e)
            task["end_time"] = time.time()
            
            # 更新统计信息
            self.task_stats["failed"] += 1
            
            logger.error(f"任务失败: {task_id}, 错误: {e}")
        
        finally:
            self.task_stats["processing"] -= 1
    
    async def get_task_stats(self) -> Dict:
        """
        获取任务统计信息
        
        Returns:
            任务统计
        """
        # 计算任务成功率
        total_finished = self.task_stats["completed"] + self.task_stats["failed"]
        success_rate = self.task_stats["completed"] / max(1, total_finished) * 100
        
        return {
            **self.task_stats,
            "success_rate": success_rate,
            "current_processes": self.current_processes,
            "current_coroutines": self.current_coroutines,
            "is_degraded": self.is_degraded,
            "degradation_level": self.degradation_level,
            "queue_sizes": {
                "task_queue": self.task_queue.qsize(),
                "priority_queue": self.priority_queue.qsize()
            }
        }
    
    def get_current_degradation_config(self) -> Dict:
        """
        获取当前降级配置
        
        Returns:
            降级配置
        """
        return next((l for l in self.degradation_levels if l["level"] == self.degradation_level), {})
    
    async def shutdown(self):
        """关闭资源调度器"""
        logger.info("关闭资源调度器...")
        
        # 关闭进程池
        if self.process_pool:
            self.process_pool.shutdown(wait=False)
            
        # 关闭线程池
        if self.thread_pool:
            self.thread_pool.shutdown(wait=False)
        
        logger.info("资源调度器已关闭") 