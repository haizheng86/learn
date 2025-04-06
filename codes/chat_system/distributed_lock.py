import asyncio
import uuid
import time
import logging
import random
import socket
import os
from typing import Optional, Dict, Any, Callable, Awaitable

# 导入Redis客户端
try:
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
except ImportError:
    # 如果导入失败，main.py中已提供了AsyncRedisWrapper的实现
    from main import AsyncRedisWrapper
    redis_async = AsyncRedisWrapper
    REDIS_AVAILABLE = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DistributedLock")

class DummyLock:
    """
    本地锁实现，用于Redis不可用时，提供兼容的API但仅在单机模式下工作
    """
    # 保存所有锁及其状态
    _locks = {}
    
    def __init__(self, 
                lock_name: str, 
                expire_seconds: int = 10, 
                owner_id: Optional[str] = None):
        """
        初始化本地锁
        
        参数:
            lock_name: 锁名称
            expire_seconds: 锁过期时间（秒）
            owner_id: 锁所有者ID，如未提供则自动生成
        """
        self.lock_name = f"lock:{lock_name}"
        self.expire_seconds = expire_seconds
        
        # 生成所有者ID
        hostname = socket.gethostname()
        pid = os.getpid()
        rand_suffix = str(uuid.uuid4())[:8]
        self.owner_id = owner_id or f"{hostname}:{pid}:{rand_suffix}"
        
        # 锁状态
        self.locked = False
        self.acquired_time = None
        self.expire_at = None
        
    async def acquire(self) -> bool:
        """获取锁，支持重入"""
        # 检查锁是否存在且未过期
        current_time = time.time()
        
        if self.lock_name in self._locks:
            lock_info = self._locks[self.lock_name]
            
            # 检查是否已过期
            if lock_info["expire_at"] < current_time:
                # 锁已过期，可以获取
                pass
            elif lock_info["owner"] == self.owner_id:
                # 支持重入
                lock_info["reentry_count"] = lock_info.get("reentry_count", 0) + 1
                self.locked = True
                return True
            else:
                # 锁被其他所有者持有且未过期
                return False
        
        # 获取锁
        self._locks[self.lock_name] = {
            "owner": self.owner_id,
            "created_at": current_time,
            "expire_at": current_time + self.expire_seconds,
            "reentry_count": 0
        }
        
        self.locked = True
        self.acquired_time = current_time
        self.expire_at = current_time + self.expire_seconds
        
        return True
    
    async def release(self) -> bool:
        """释放锁，支持重入锁的计数"""
        if not self.locked:
            return False
            
        # 检查锁是否存在
        if self.lock_name not in self._locks:
            self.locked = False
            return False
            
        lock_info = self._locks[self.lock_name]
        
        # 检查是否是锁的所有者
        if lock_info["owner"] != self.owner_id:
            return False
            
        # 如果是重入锁，递减计数
        if lock_info.get("reentry_count", 0) > 0:
            lock_info["reentry_count"] -= 1
            return True
            
        # 删除锁
        del self._locks[self.lock_name]
        self.locked = False
        
        return True
    
    async def get_lock_info(self) -> Dict[str, Any]:
        """获取锁的详细信息"""
        if self.lock_name not in self._locks:
            return {"exists": False}
            
        lock_info = self._locks[self.lock_name]
        current_time = time.time()
        
        return {
            "exists": True,
            "owner": lock_info["owner"],
            "created_at": lock_info["created_at"],
            "expire_at": lock_info["expire_at"],
            "is_expired": lock_info["expire_at"] < current_time,
            "is_owner": lock_info["owner"] == self.owner_id,
            "reentry_count": lock_info.get("reentry_count", 0)
        }
    
    @classmethod
    async def force_unlock(cls, lock_name: str) -> bool:
        """强制释放锁"""
        lock_key = f"lock:{lock_name}"
        
        if lock_key in cls._locks:
            del cls._locks[lock_key]
            return True
            
        return False
    
    async def __aenter__(self):
        """异步上下文管理器支持"""
        if not await self.acquire():
            raise TimeoutError(f"无法获取锁: {self.lock_name}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动释放锁"""
        await self.release()

class RedisDistributedLock:
    """
    基于Redis的分布式锁实现
    支持锁重入、自动续期、故障恢复和死锁预防
    适用于百万级并发系统的分布式协调
    
    使用方法：
    ```python
    async with RedisDistributedLock(redis, "my_lock"):
        # 这里的代码在获取锁的情况下执行
        # 退出上下文后自动释放锁
    ```
    """
    
    # 全局锁状态映射，用于跟踪同一进程内的锁获取情况
    # 键：锁名称, 值：{owner_id: 重入计数}
    _local_locks: Dict[str, Dict[str, int]] = {}
    
    def __init__(self, redis_client=None, default_timeout: int = 30):
        """初始化分布式锁"""
        self.redis_client = redis_client
        self.default_timeout = default_timeout
        self.locks: Dict[str, str] = {}  # 当前进程持有的锁，key为锁名，value为token
        
        # 如果Redis不可用，使用本地锁
        if self.redis_client is None:
            self.dummy_lock = DummyLock(lock_name, expire_seconds, owner_id)
            logger.info(f"Redis不可用，使用本地锁: {lock_name}")
    
    @staticmethod
    def _get_retry_interval(base_interval: float, retry_count: int, 
                           backoff_factor: float, jitter: float) -> float:
        """计算退避重试间隔，添加随机抖动以避免惊群效应"""
        interval = base_interval * (backoff_factor ** min(retry_count, 10))
        jitter_amount = interval * jitter
        return interval + random.uniform(-jitter_amount, jitter_amount)
    
    async def acquire(self) -> bool:
        """
        获取锁，支持重入
        
        返回:
            获取成功返回True，失败返回False
        """
        # 如果Redis不可用，使用本地锁
        if self.redis_client is None:
            return await self.dummy_lock.acquire()
            
        # 检查是否已经持有锁（支持重入）
        if self.lock_name in self._local_locks and self.owner_id in self._local_locks[self.lock_name]:
            # 已经持有锁，增加重入计数
            self._local_locks[self.lock_name][self.owner_id] += 1
            logger.debug(f"锁重入成功: {self.lock_name}, 重入计数: {self._local_locks[self.lock_name][self.owner_id]}")
            self.locked = True
            return True
        
        self.retry_count = 0
        retry_interval = self.retry_interval
        
        while self.retry_count < self.max_retry_times:
            # 尝试获取锁，使用setnx保证原子性
            # 同时设置过期时间和锁元数据
            lock_metadata = {
                "owner": self.owner_id,
                "created_at": time.time(),
                "expire_at": time.time() + self.expire_seconds
            }
            
            # 使用Lua脚本确保操作的原子性
            script = """
            if redis.call('exists', KEYS[1]) == 0 then
                redis.call('hset', KEYS[1], 'owner', ARGV[1], 'created_at', ARGV[2], 'expire_at', ARGV[3])
                redis.call('expire', KEYS[1], ARGV[4])
                return 1
            else
                -- 检查锁是否由当前所有者持有，支持重入
                if redis.call('hget', KEYS[1], 'owner') == ARGV[1] then
                    redis.call('hincrby', KEYS[1], 'reentry_count', 1)
                    redis.call('expire', KEYS[1], ARGV[4])
                    return 1
                end
                return 0
            end
            """
            
            result = await self.redis_client.eval(
                script,
                keys=[self.lock_name],
                args=[
                    self.owner_id,
                    str(lock_metadata["created_at"]),
                    str(lock_metadata["expire_at"]),
                    str(self.expire_seconds)
                ]
            )
            
            if result:
                # 锁获取成功
                self.locked = True
                self.acquired_time = time.time()
                self.lock_metadata = lock_metadata
                
                # 更新本地锁映射
                if self.lock_name not in self._local_locks:
                    self._local_locks[self.lock_name] = {}
                self._local_locks[self.lock_name][self.owner_id] = 1
                
                # 启动自动续期任务
                self.renew_task = asyncio.create_task(self._auto_renew())
                
                logger.debug(f"获取锁成功: {self.lock_name}")
                return True
            
            # 获取锁失败，检查锁状态
            await self._check_and_recover_dead_lock()
            
            # 计算下一次重试间隔
            retry_interval = self._get_retry_interval(
                self.retry_interval, 
                self.retry_count, 
                self.retry_backoff_factor,
                self.retry_jitter
            )
            
            # 等待后重试
            await asyncio.sleep(retry_interval)
            self.retry_count += 1
        
        logger.warning(f"获取锁失败（达到最大重试次数）: {self.lock_name}")
        return False
    
    async def _check_and_recover_dead_lock(self) -> bool:
        """
        检查并尝试恢复死锁或者过期但未自动释放的锁
        
        返回:
            如果发现并处理了死锁返回True，否则返回False
        """
        try:
            # 检查锁是否存在
            if not await self.redis_client.exists(self.lock_name):
                return False
                
            # 获取锁元数据
            lock_data = await self.redis_client.hgetall(self.lock_name)
            
            # 检查是否可以解析锁数据
            if not lock_data or b'owner' not in lock_data or b'expire_at' not in lock_data:
                return False
                
            owner = lock_data[b'owner'].decode('utf-8')
            expire_at = float(lock_data[b'expire_at'].decode('utf-8'))
            
            # 检查锁是否已过期但未自动释放
            current_time = time.time()
            if current_time > expire_at:
                # 使用Lua脚本原子性地检查并删除过期锁
                script = """
                if redis.call('hget', KEYS[1], 'expire_at') and tonumber(redis.call('hget', KEYS[1], 'expire_at')) < tonumber(ARGV[1]) then
                    return redis.call('del', KEYS[1])
                end
                return 0
                """
                
                result = await self.redis_client.eval(
                    script,
                    keys=[self.lock_name],
                    args=[str(current_time)]
                )
                
                if result:
                    logger.warning(f"清理了过期锁: {self.lock_name}, 原持有者: {owner}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"检查死锁时出错: {e}")
            return False
    
    async def release(self) -> bool:
        """
        释放锁，支持重入锁的递减计数
        
        返回:
            释放成功返回True，失败返回False
        """
        # 如果Redis不可用，使用本地锁
        if self.redis_client is None:
            return await self.dummy_lock.release()
            
        if not self.locked:
            return False
            
        try:
            # 检查是否是重入锁
            if (self.lock_name in self._local_locks and 
                self.owner_id in self._local_locks[self.lock_name] and 
                self._local_locks[self.lock_name][self.owner_id] > 1):
                # 重入锁，递减计数
                self._local_locks[self.lock_name][self.owner_id] -= 1
                logger.debug(f"递减锁重入计数: {self.lock_name}, 剩余计数: {self._local_locks[self.lock_name][self.owner_id]}")
                return True
                
            # 非重入或最后一次释放，取消自动续期任务
            if self.renew_task and not self.renew_task.done():
                self.renew_task.cancel()
                
            # 使用Lua脚本保证原子性，只有锁的持有者才能释放锁
            script = """
            if redis.call('hget', KEYS[1], 'owner') == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            
            result = await self.redis_client.eval(
                script,
                keys=[self.lock_name],
                args=[self.owner_id]
            )
            
            released = bool(result)
            if released:
                # 更新本地锁映射
                if self.lock_name in self._local_locks and self.owner_id in self._local_locks[self.lock_name]:
                    del self._local_locks[self.lock_name][self.owner_id]
                    if not self._local_locks[self.lock_name]:
                        del self._local_locks[self.lock_name]
                
                self.locked = False
                logger.debug(f"释放锁成功: {self.lock_name}")
            else:
                logger.warning(f"释放锁失败（锁可能已过期或被其他持有者获取）: {self.lock_name}")
            
            return released
            
        except Exception as e:
            logger.error(f"释放锁错误: {e}")
            return False
    
    async def _auto_renew(self):
        """
        自动续期任务
        
        在锁过期前自动续期，防止操作时间过长导致锁过期
        使用递增延长策略，避免出现网络分区时的问题
        """
        try:
            # 计算续期的时间间隔（锁过期时间的一半）
            renew_interval = self.expire_seconds / 2
            extension_seconds = self.expire_seconds
            
            while self.locked:
                # 等待一段时间
                await asyncio.sleep(renew_interval)
                
                # 检查是否仍然持有锁
                if not self.locked:
                    break
                
                # 使用Lua脚本续期，确保原子性
                script = """
                if redis.call('hget', KEYS[1], 'owner') == ARGV[1] then
                    redis.call('hset', KEYS[1], 'expire_at', ARGV[2])
                    return redis.call('expire', KEYS[1], ARGV[3])
                else
                    return 0
                end
                """
                
                new_expire_at = time.time() + extension_seconds
                
                result = await self.redis_client.eval(
                    script,
                    keys=[self.lock_name],
                    args=[
                        self.owner_id,
                        str(new_expire_at),
                        str(extension_seconds)
                    ]
                )
                
                if not result:
                    logger.warning(f"锁续期失败（锁可能已丢失）: {self.lock_name}")
                    self.locked = False
                    
                    # 清理本地锁映射
                    if self.lock_name in self._local_locks and self.owner_id in self._local_locks[self.lock_name]:
                        del self._local_locks[self.lock_name][self.owner_id]
                        if not self._local_locks[self.lock_name]:
                            del self._local_locks[self.lock_name]
                    
                    break
                
                # 更新锁元数据
                self.lock_metadata["expire_at"] = new_expire_at
                
                logger.debug(f"锁续期成功: {self.lock_name}, 新过期时间: {new_expire_at}")
                
                # 递增续期时间，防止长操作被中断
                extension_seconds = min(extension_seconds * 1.5, 60)  # 最长不超过60秒
        
        except asyncio.CancelledError:
            # 任务被取消，正常情况
            pass
        except Exception as e:
            logger.error(f"锁续期错误: {e}")
            self.locked = False
            
            # 清理本地锁映射
            if self.lock_name in self._local_locks and self.owner_id in self._local_locks[self.lock_name]:
                del self._local_locks[self.lock_name][self.owner_id]
                if not self._local_locks[self.lock_name]:
                    del self._local_locks[self.lock_name]
    
    async def get_lock_info(self) -> Dict[str, Any]:
        """
        获取锁的详细信息
        
        返回:
            锁的元数据信息
        """
        # 如果Redis不可用，使用本地锁
        if self.redis_client is None:
            return await self.dummy_lock.get_lock_info()
            
        try:
            if not await self.redis_client.exists(self.lock_name):
                return {"exists": False}
                
            lock_data = await self.redis_client.hgetall(self.lock_name)
            
            # 转换byte键值为字符串
            result = {"exists": True}
            for k, v in lock_data.items():
                try:
                    key = k.decode('utf-8')
                    # 尝试转换数值类型
                    if key in ['created_at', 'expire_at']:
                        value = float(v.decode('utf-8'))
                    elif key == 'reentry_count':
                        value = int(v.decode('utf-8'))
                    else:
                        value = v.decode('utf-8')
                    result[key] = value
                except (UnicodeDecodeError, ValueError):
                    result[k.decode('utf-8', errors='replace')] = str(v)
            
            # 添加过期状态
            if 'expire_at' in result:
                result['is_expired'] = result['expire_at'] < time.time()
                
            # 添加持有者状态
            if 'owner' in result:
                result['is_owner'] = result['owner'] == self.owner_id
                
            return result
            
        except Exception as e:
            logger.error(f"获取锁信息错误: {e}")
            return {"exists": False, "error": str(e)}
    
    @classmethod
    async def force_unlock(cls, redis_client, lock_name: str) -> bool:
        """
        强制释放锁（应谨慎使用）
        
        参数:
            redis_client: Redis客户端
            lock_name: 锁名称
            
        返回值:
            是否成功删除锁
        """
        if redis_client is None:
            # 处理本地锁
            lock_name = f"lock:{lock_name}"
            if lock_name in cls._local_locks:
                del cls._local_locks[lock_name]
                return True
            return False
            
        try:
            lock_key = f"lock:{lock_name}"
            deleted = await redis_client.delete(lock_key)
            return deleted > 0
        except Exception as e:
            logger.error(f"强制解锁失败: {str(e)}")
            return False
    
    async def __aenter__(self):
        """异步上下文管理器支持"""
        if not await self.acquire():
            raise TimeoutError(f"无法获取锁: {self.lock_name}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动释放锁"""
        await self.release() 