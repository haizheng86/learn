import asyncio
import json
import logging
import os
import time
import signal
import traceback
from typing import Dict, Optional, List, Any, Set

# 配置日志
logging.basicConfig(
    level=logging.getLevelName(os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ChatApp")

# 默认标记组件可用性
REDIS_AVAILABLE = False
UVLOOP_AVAILABLE = False
AIOHTTP_AVAILABLE = False
PANDAS_AVAILABLE = False
MATPLOTLIB_AVAILABLE = False

# 基础组件
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# Redis支持 - 可选
try:
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
    logger.info("使用redis.asyncio模块")
except ImportError:
    try:
        # 简单的Redis兼容层，保持代码一致性
        import redis
        
        # 创建Redis兼容模块
        class AsyncRedisPipelineWrapper:
            """Redis Pipeline的异步包装器"""
            
            def __init__(self, pipeline, loop=None):
                self._pipeline = pipeline
                self._loop = loop or asyncio.get_event_loop()
                
            async def execute(self):
                """执行管道中的所有命令"""
                def _execute():
                    return self._pipeline.execute()
                return await self._run_in_executor(_execute)
                
            async def _run_in_executor(self, func):
                return await self._loop.run_in_executor(None, func)
                
            # 支持管道操作
            def __getattr__(self, name):
                # 获取原始pipeline的方法
                attr = getattr(self._pipeline, name)
                
                # 如果是方法，返回一个包装器，让管道可以链式调用
                if callable(attr):
                    def wrapper(*args, **kwargs):
                        # 调用原始方法
                        result = attr(*args, **kwargs)
                        # 如果返回的是pipeline本身（链式调用），返回self
                        if result == self._pipeline:
                            return self
                        return result
                    return wrapper
                return attr
        
        class AsyncPubSubWrapper:
            """Redis PubSub对象的异步包装器"""
            
            def __init__(self, pubsub, loop=None):
                self._pubsub = pubsub
                self._loop = loop or asyncio.get_event_loop()
            
            async def subscribe(self, *channels):
                """订阅频道"""
                def _subscribe():
                    return self._pubsub.subscribe(*channels)
                return await self._run_in_executor(_subscribe)
            
            async def get_message(self, ignore_subscribe_messages=True, timeout=0):
                """获取消息"""
                def _get_message():
                    return self._pubsub.get_message(
                        ignore_subscribe_messages=ignore_subscribe_messages,
                        timeout=timeout
                    )
                return await self._run_in_executor(_get_message)
            
            async def unsubscribe(self, *channels):
                """取消订阅频道"""
                def _unsubscribe():
                    return self._pubsub.unsubscribe(*channels)
                return await self._run_in_executor(_unsubscribe)
            
            async def close(self):
                """关闭PubSub连接"""
                def _close():
                    return self._pubsub.close()
                return await self._run_in_executor(_close)
                
            async def _run_in_executor(self, func):
                return await self._loop.run_in_executor(None, func)
        
        class AsyncRedisWrapper:
            """Redis异步API的兼容包装器，将同步Redis API包装成异步接口"""
            
            def __init__(self, url=None, host='localhost', port=6379, username=None, password=None, **kwargs):
                """初始化Redis包装器
                
                参数:
                    url: Redis连接URL
                    host: Redis主机名
                    port: Redis端口
                    username: Redis用户名
                    password: Redis密码
                    **kwargs: 其他Redis连接参数
                """
                try:
                    import redis as sync_redis_lib
                    if url:
                        self._redis = sync_redis_lib.from_url(url, **kwargs)
                    else:
                        self._redis = sync_redis_lib.Redis(
                            host=host, 
                            port=port,
                            username=username,
                            password=password,
                            **kwargs
                        )
                    self._loop = None
                except Exception as e:
                    logger = logging.getLogger("AsyncRedisWrapper")
                    logger.error(f"Redis客户端创建失败: {str(e)}")
                    raise
            
            @classmethod
            def from_url(cls, url, **kwargs):
                """从URL创建Redis连接
                
                这是一个类方法，兼容redis.asyncio.Redis.from_url的接口
                """
                return cls(url, **kwargs)
            
            async def ping(self):
                """测试Redis连接"""
                def _ping():
                    return self._redis.ping()
                return await self._run_in_executor(_ping)
            
            async def get(self, key):
                """获取键值"""
                def _get():
                    return self._redis.get(key)
                return await self._run_in_executor(_get)
            
            async def set(self, key, value, **kwargs):
                """设置键值"""
                def _set():
                    return self._redis.set(key, value, **kwargs)
                return await self._run_in_executor(_set)
            
            async def delete(self, *keys):
                """删除键"""
                def _delete():
                    return self._redis.delete(*keys)
                return await self._run_in_executor(_delete)
            
            async def exists(self, *keys):
                """检查键是否存在"""
                def _exists():
                    return self._redis.exists(*keys)
                return await self._run_in_executor(_exists)
            
            async def expire(self, key, seconds):
                """设置键过期时间"""
                def _expire():
                    return self._redis.expire(key, seconds)
                return await self._run_in_executor(_expire)
            
            async def ttl(self, key):
                """获取键剩余生存时间"""
                def _ttl():
                    return self._redis.ttl(key)
                return await self._run_in_executor(_ttl)
            
            async def hset(self, name, key=None, value=None, mapping=None):
                """设置哈希表中的字段值"""
                def _hset():
                    if mapping is not None:
                        return self._redis.hset(name, mapping=mapping)
                    else:
                        return self._redis.hset(name, key, value)
                return await self._run_in_executor(_hset)
            
            async def hget(self, name, key):
                """获取哈希表字段值"""
                def _hget():
                    return self._redis.hget(name, key)
                return await self._run_in_executor(_hget)
            
            async def hgetall(self, name):
                """获取哈希表所有字段和值"""
                def _hgetall():
                    return self._redis.hgetall(name)
                return await self._run_in_executor(_hgetall)
            
            async def publish(self, channel, message):
                """发布消息到频道"""
                def _publish():
                    return self._redis.publish(channel, message)
                return await self._run_in_executor(_publish)
            
            async def _run_in_executor(self, func):
                """在执行器中运行同步函数"""
                if self._loop is None:
                    self._loop = asyncio.get_event_loop()
                return await self._loop.run_in_executor(None, func)
            
            # 添加额外需要的方法
            async def keys(self, pattern):
                """查找所有符合给定模式的键"""
                def _keys():
                    return self._redis.keys(pattern)
                return await self._run_in_executor(_keys)
                
            async def hincrby(self, name, key, amount=1):
                """为哈希表指定字段的整数值加上增量"""
                def _hincrby():
                    return self._redis.hincrby(name, key, amount)
                return await self._run_in_executor(_hincrby)
                
            async def sadd(self, name, *values):
                """向集合添加一个或多个成员"""
                def _sadd():
                    return self._redis.sadd(name, *values)
                return await self._run_in_executor(_sadd)
                
            async def smembers(self, name):
                """返回集合中的所有成员"""
                def _smembers():
                    return self._redis.smembers(name)
                return await self._run_in_executor(_smembers)
                
            async def srem(self, name, *values):
                """移除集合中一个或多个成员"""
                def _srem():
                    return self._redis.srem(name, *values)
                return await self._run_in_executor(_srem)
                
            async def hdel(self, name, *keys):
                """删除一个或多个哈希表字段"""
                def _hdel():
                    return self._redis.hdel(name, *keys)
                return await self._run_in_executor(_hdel)
                
            async def lpush(self, name, *values):
                """将一个或多个值插入到列表头部"""
                def _lpush():
                    return self._redis.lpush(name, *values)
                return await self._run_in_executor(_lpush)
                
            async def ltrim(self, name, start, end):
                """对一个列表进行修剪(trim)"""
                def _ltrim():
                    return self._redis.ltrim(name, start, end)
                return await self._run_in_executor(_ltrim)
                
            async def lrange(self, name, start, end):
                """获取列表指定范围内的元素"""
                def _lrange():
                    return self._redis.lrange(name, start, end)
                return await self._run_in_executor(_lrange)
                
            async def scard(self, name):
                """获取集合的成员数"""
                def _scard():
                    return self._redis.scard(name)
                return await self._run_in_executor(_scard)
            
            async def zrevrange(self, name, start, end, withscores=False):
                """返回有序集合中指定区间内的成员，分数从高到低排序"""
                def _zrevrange():
                    return self._redis.zrevrange(name, start, end, withscores=withscores)
                return await self._run_in_executor(_zrevrange)
            
            async def eval(self, script, keys=None, args=None):
                """执行Lua脚本"""
                def _eval():
                    return self._redis.eval(script, len(keys) if keys else 0, *(keys or []) + (args or []))
                return await self._run_in_executor(_eval)
            
            def pipeline(self):
                """创建一个管道"""
                # 创建一个简单的异步管道实现
                pipe = self._redis.pipeline()
                wrapper = AsyncRedisPipelineWrapper(pipe, self._loop)
                return wrapper

            async def close(self):
                """关闭Redis连接"""
                return self._redis.close()
            
            async def wait_closed(self):
                """等待Redis连接关闭完成"""
                # 同步客户端没有wait_closed方法，返回None即可
                return None
            
            # 添加pubsub方法
            def pubsub(self):
                """获取PubSub对象"""
                pubsub = self._redis.pubsub()
                return AsyncPubSubWrapper(pubsub, self._loop)
                
            async def zadd(self, name, mapping):
                """添加到有序集合"""
                def _zadd():
                    return self._redis.zadd(name, mapping)
                return await self._run_in_executor(_zadd)
            
            async def zremrangebyrank(self, name, start, end):
                """删除有序集合中指定排名范围内的所有成员"""
                def _zremrangebyrank():
                    return self._redis.zremrangebyrank(name, start, end)
                return await self._run_in_executor(_zremrangebyrank)
            
            async def type(self, key):
                """获取键的类型"""
                def _type():
                    return self._redis.type(key)
                return await self._run_in_executor(_type)
        
        # 设置redis_async为我们的兼容包装器
        redis_async = AsyncRedisWrapper
        REDIS_AVAILABLE = True
        logger.info("使用AsyncRedisWrapper兼容层")
    except ImportError:
        redis_async = None
        REDIS_AVAILABLE = False
        logger.warning("Redis不可用")

# 确保redis_async正确初始化
if redis_async is None:
    logger.error("redis_async初始化失败，尝试重新导入")
    try:
        import redis
        # 创建一个简单的模拟类
        class DummyRedisAsync:
            @classmethod
            def from_url(cls, *args, **kwargs):
                logger.warning("使用无操作的Redis客户端")
                return cls()
                
            async def ping(self):
                return False
                
            async def close(self):
                pass
                
            async def wait_closed(self):
                pass
                
        redis_async = DummyRedisAsync
    except ImportError:
        logger.error("无法创建Redis兼容层")

# uvloop支持 - 可选
try:
    if os.environ.get("DISABLE_UVLOOP") != "1":
        import uvloop
        # 验证uvloop与当前Python版本的兼容性
        try:
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            UVLOOP_AVAILABLE = True
            logger.info("成功加载uvloop高性能事件循环")
        except Exception as e:
            logger.warning(f"uvloop不兼容当前Python版本，将使用标准事件循环: {e}")
    else:
        logger.info("通过环境变量禁用uvloop，将使用标准事件循环")
except ImportError:
    logger.warning("uvloop不可用，将使用标准事件循环")

# aiohttp支持 - 可选
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    logger.warning("aiohttp不可用，一些HTTP请求功能将受限")

# 数据分析支持 - 可选
"""
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    logger.warning("pandas不可用，数据分析功能将受限")

try:
    import matplotlib.pyplot as plt
    import matplotlib
    # 设置非交互式后端，避免GUI依赖
    matplotlib.use('Agg')
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    logger.warning("matplotlib不可用，可视化功能将受限")
"""
# 暂时禁用pandas和matplotlib导入，避免numpy兼容性问题
PANDAS_AVAILABLE = True
MATPLOTLIB_AVAILABLE = False
logger.warning("数据分析和可视化功能已禁用，以避免numpy兼容性问题")

from dotenv import load_dotenv

from connection_manager import ConnectionManager
from resource_scheduler import DynamicResourceScheduler
from monitor import ChatSystemMonitor
from distributed_lock import RedisDistributedLock

# 加载环境变量
load_dotenv()

# 使用uvloop替换默认事件循环（如果可用）
if UVLOOP_AVAILABLE and os.environ.get("DISABLE_UVLOOP") != "1":
    try:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.info("已启用uvloop高性能事件循环")
    except Exception as e:
        logger.warning(f"无法设置uvloop事件循环策略: {e}")
        logger.info("将使用标准事件循环")
else:
    logger.info("使用标准asyncio事件循环")

# 创建FastAPI应用
app = FastAPI(
    title="百万级WebSocket聊天系统",
    description="一个支持百万并发连接的分布式WebSocket聊天系统，具备服务降级和故障恢复能力",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板
templates_path = os.path.join(os.path.dirname(__file__), "templates")
static_path = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates = Jinja2Templates(directory=templates_path)

# 获取环境变量
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
NODE_ID = os.getenv("NODE_ID", f"node-{os.getpid()}")
MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", "100000"))
API_KEY = os.getenv("API_KEY", "test123")  # 设置默认API密钥为test123

# 全局变量
connection_manager = ConnectionManager()
resource_scheduler = None
system_monitor = None
redis = None
shutdown_event = asyncio.Event()

# API密钥验证（可选）
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# 系统状态
system_status = {
    "start_time": time.time(),
    "node_id": NODE_ID,
    "is_healthy": True,
    "degradation_level": 0,
    "connections": 0,
    "messages": 0,
    "errors": 0,
    "redis_connected": False, 
    "process_cpu": 0.0,
    "system_cpu": 0.0,
    "process_memory_percent": 0.0,
    "system_memory_percent": 0.0,
    "task_queue_size": 0,
    "version": "2.0.0"  # 添加系统版本
}

# 单机模式下用于存储消息的内存字典
in_memory_messages = {}
in_memory_rooms = {
    "general": {"name": "公共聊天室", "description": "所有用户的一般性讨论", "users": set()},
    "tech": {"name": "技术讨论", "description": "讨论编程和技术话题", "users": set()},
    "random": {"name": "随机话题", "description": "自由讨论各种话题", "users": set()}
}

# 模型定义
class Message(BaseModel):
    room: str
    content: str
    sender: Optional[str] = None
    private_to: Optional[str] = None
    type: str = "text"  # text, image, file, system

class RoomCreate(BaseModel):
    name: str
    description: str = ""

class SystemConfig(BaseModel):
    max_connections: int = Field(MAX_CONNECTIONS, ge=1000, le=10000000)
    degradation_level: int = Field(0, ge=0, le=3)

# 依赖项
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if not API_KEY:
        return True
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="无效的API密钥")
    return True

async def get_current_user(request: Request):
    # 简单的用户身份获取，实际应用中应实现更完善的身份验证
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    return user_id

# 状态变更回调函数
async def status_change_handler(new_status: Dict[str, Any]):
    """处理系统状态变更事件"""
    # 更新全局状态
    for key, value in new_status.items():
        if key in system_status:
            system_status[key] = value
    
    # 确保特定CPU指标字段存在，避免KeyError
    if "process_cpu" not in system_status and "process_cpu" in new_status:
        system_status["process_cpu"] = new_status["process_cpu"]
    
    # 处理system_cpu字段
    if "system_cpu" not in system_status and "system_cpu" in new_status:
        system_status["system_cpu"] = new_status["system_cpu"]
    
    # 处理process_memory_percent字段
    if "process_memory_percent" not in system_status and "process_memory_percent" in new_status:
        system_status["process_memory_percent"] = new_status["process_memory_percent"]
    
    # 处理system_memory_percent字段
    if "system_memory_percent" not in system_status and "system_memory_percent" in new_status:
        system_status["system_memory_percent"] = new_status["system_memory_percent"]
    
    # 处理task_queue_size字段
    if "task_queue_size" not in system_status and "task_queue_size" in new_status:
        system_status["task_queue_size"] = new_status["task_queue_size"]
    
    # 如果系统降级级别改变，向所有客户端发送通知
    if "degradation_level" in new_status:
        message = "系统正常运行" if new_status["degradation_level"] == 0 else f"系统当前处于性能降级状态 (级别 {new_status['degradation_level']})"
        await connection_manager.broadcast_system_message(message)
    
    # 更新资源调度器的降级级别
    if resource_scheduler:
        await resource_scheduler._check_degradation_level(new_status)

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    global resource_scheduler, system_monitor, redis, system_status
    
    try:
        # 连接Redis（如果可用）
        if REDIS_AVAILABLE:
            try:
                # 获取环境变量中的Redis URL
                redis_url = os.getenv("REDIS_URL", "redis://localhost")
                logger.info(f"配置的Redis URL: {redis_url}")
                
                # 解析Redis URL获取连接参数
                host = "localhost"
                port = 6379
                username = None
                password = None
                
                # 提取主机和端口
                if "@" in redis_url:
                    auth_part, conn_part = redis_url.replace("redis://", "").split("@")
                    if ":" in conn_part:
                        host, port = conn_part.split(":")
                        port = int(port)
                    else:
                        host = conn_part
                    
                    # 提取密码（和可能的用户名）
                    if auth_part.startswith(":"):  # 只有密码的格式 :password
                        password = auth_part[1:]
                    elif ":" in auth_part:         # 用户名:密码格式
                        username, password = auth_part.split(":")
                    else:                          # 只有密码，无冒号格式（兼容）
                        password = auth_part
                else:
                    # 无认证的URL
                    url_part = redis_url.replace("redis://", "")
                    if ":" in url_part:
                        host, port = url_part.split(":")
                        port = int(port)
                    else:
                        host = url_part
                
                logger.info(f"Redis连接参数 - 主机: {host}, 端口: {port}, 用户名: {username}, 密码: {'已设置' if password else '未设置'}")
                
                try:
                    # 先用同步客户端测试连接
                    import redis as sync_redis_lib
                    
                    sync_client = sync_redis_lib.Redis(
                        host=host,
                        port=port,
                        username=username,
                        password=password,
                        socket_timeout=3.0,
                        decode_responses=True
                    )
                    
                    # 测试连接
                    sync_ping = sync_client.ping()
                    logger.info(f"Redis同步连接成功，ping结果: {sync_ping}")
                    
                    # 创建异步Redis客户端 - 使用直接参数方式
                    # 使用导入重命名避免冲突
                    redis = AsyncRedisWrapper(
                        host=host, 
                        port=port,
                        username=username,
                        password=password,
                        decode_responses=True
                    )
                    
                    # 测试异步连接
                    ping_result = await redis.ping()
                    logger.info(f"Redis异步连接成功，ping结果: {ping_result}")
                    
                    # 设置连接状态
                    system_status["redis_connected"] = True
                    logger.info("Redis连接成功，使用分布式模式")
                    
                    # 彻底清理Redis数据
                    try:
                        # 获取房间相关的所有模式
                        patterns = [
                            "room:*:messages",
                            "chat:room:*:messages",
                            "message:*"
                        ]
                        
                        logger.warning("开始清理Redis键，删除所有消息相关数据")
                        for pattern in patterns:
                            try:
                                # 查找所有匹配键
                                keys = await redis.keys(pattern)
                                if keys:
                                    logger.warning(f"找到 {len(keys)} 个匹配模式 {pattern} 的键，准备删除")
                                    
                                    # 分批删除，每批不超过100个
                                    for i in range(0, len(keys), 100):
                                        batch = keys[i:i+100]
                                        if batch:
                                            await redis.delete(*batch)
                                            logger.info(f"已删除 {len(batch)} 个键")
                            except Exception as e:
                                logger.error(f"删除 {pattern} 模式的键时出错: {e}")
                        
                        logger.warning("Redis键清理完成")
                    except Exception as e:
                        logger.error(f"清理Redis数据失败: {e}")
                    
                    # 重新创建基本房间
                    default_rooms = [
                        {"id": "general", "name": "公共聊天室", "description": "所有用户的一般性讨论"},
                        {"id": "tech", "name": "技术讨论", "description": "讨论编程和技术话题"},
                        {"id": "random", "name": "随机话题", "description": "自由讨论各种话题"}
                    ]
                    
                    for room in default_rooms:
                        try:
                            # 创建房间信息
                            room_data = {
                                "name": room["name"],
                                "description": room["description"],
                                "created_at": str(time.time())
                            }
                            await redis.hset(f"room:{room['id']}", mapping=room_data)
                        except Exception as e:
                            logger.error(f"创建房间 {room['id']} 失败: {e}")
                except Exception as e:
                    logger.error(f"Redis连接失败: {str(e)}")
                    system_status["redis_connected"] = False
                    redis = None
                    logger.warning("将使用单机模式运行")
            except Exception as e:
                logger.warning(f"Redis连接过程出错: {e}")
                system_status["redis_connected"] = False
                redis = None
                logger.warning("将使用单机模式运行")
        else:
            logger.warning("Redis依赖不可用，将使用单机模式运行")
            system_status["redis_connected"] = False
            redis = None
        
        # 初始化连接管理器
        await connection_manager.initialize(redis)
        
        # 初始化资源调度器
        resource_scheduler = DynamicResourceScheduler()
        await resource_scheduler.initialize_scheduler()
        
        # 注册调度器状态变更回调
        resource_scheduler.register_status_change_callback(
            lambda old_level, new_level, metrics: status_change_handler(
                {
                    "degradation_level": new_level,
                    "is_degraded": new_level > 0,
                    "process_cpu": metrics.get("process_cpu", 0),
                    "system_cpu": metrics.get("system_cpu", 0),
                    "process_memory_percent": metrics.get("process_memory_percent", 0),
                    "system_memory_percent": metrics.get("system_memory_percent", 0),
                    "task_queue_size": metrics.get("task_queue_size", 0)
                }
            )
        )
        
        # 初始化系统监控
        system_monitor = ChatSystemMonitor(connection_manager, redis, NODE_ID)
        system_monitor.register_status_callback(status_change_handler)
        await system_monitor.start_monitoring()
        
        # 记录启动时间
        from datetime import datetime
        system_status["start_time"] = datetime.now().isoformat()
        
        # 改进的信号处理逻辑
        async def handle_exit_signal(sig_name):
            logger.warning(f"收到 {sig_name} 信号，正在关闭应用...")
            
            # 标记关闭事件
            shutdown_event.set()
            
            # 关闭所有连接和服务
            await shutdown_app()
            
            # 强制退出，确保进程不会悬挂
            import os, signal
            os.kill(os.getpid(), signal.SIGKILL)
        
        # 设置信号处理
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(
                sig, 
                lambda s=sig: asyncio.create_task(handle_exit_signal(s.name))
            )
        
        # 向Redis发布节点上线消息
        if system_status["redis_connected"]:
            try:
                await redis.publish("system:node_online", json.dumps({
                    "node_id": NODE_ID,
                    "timestamp": time.time(),
                    "max_connections": MAX_CONNECTIONS
                }))
            except Exception as e:
                logger.warning(f"发布节点上线消息失败: {e}")
        
        logger.info(f"聊天系统启动成功，节点ID: {NODE_ID}, 模式: {'分布式' if system_status['redis_connected'] else '单机'}")
        
    except Exception as e:
        logger.error(f"系统启动错误: {e}")
        logger.error(traceback.format_exc())
        
        # 设置错误状态
        system_status["is_healthy"] = False
        
        # 尝试以降级模式继续运行
        logger.info("尝试以降级模式启动...")

# 改进的应用关闭事件
@app.on_event("shutdown")
async def app_shutdown_event():
    logger.info("应用程序正在关闭...")
    
    # 确保shutdown_app被执行且完成
    try:
        await asyncio.wait_for(shutdown_app(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.error("应用关闭超时，将强制退出")
    except Exception as e:
        logger.error(f"应用关闭过程中出错: {e}")
        logger.error(traceback.format_exc())

# 改进的关闭函数
async def shutdown_app():
    """优雅关闭应用，并确保所有资源都被释放"""
    
    # 防止重复执行
    if hasattr(shutdown_app, "_is_shutting_down") and shutdown_app._is_shutting_down:
        return
    
    shutdown_app._is_shutting_down = True
    shutdown_event.set()
    
    # 第一步：向所有客户端发送关闭通知
    logger.info("正在向所有客户端发送关闭通知...")
    try:
        close_msg = json.dumps({
            "type": "system",
            "content": "系统正在关闭，连接将被断开",
            "sender": "system",
            "timestamp": time.time()
        })
        
        rooms = list(connection_manager.room_user_map.keys())
        for room_id in rooms:
            try:
                await connection_manager.broadcast_to_room(room_id, close_msg)
            except Exception as e:
                logger.error(f"向房间 {room_id} 发送关闭消息失败: {e}")
    except Exception as e:
        logger.error(f"发送关闭通知时出错: {e}")
    
    # 等待客户端接收到消息
    await asyncio.sleep(1)
    
    # 第二步：关闭连接管理器
    logger.info("正在关闭连接管理器...")
    try:
        if hasattr(connection_manager, 'shutdown'):
            await connection_manager.shutdown()
    except Exception as e:
        logger.error(f"关闭连接管理器时出错: {e}")
    
    # 第三步：关闭系统监控
    if system_monitor:
        logger.info("正在停止系统监控...")
        try:
            await system_monitor.stop_monitoring()
        except Exception as e:
            logger.error(f"停止系统监控时出错: {e}")
    
    # 第四步：关闭资源调度器
    if resource_scheduler:
        logger.info("正在停止资源调度器...")
        try:
            await resource_scheduler.shutdown()
        except Exception as e:
            logger.error(f"停止资源调度器时出错: {e}")
    
    # 第五步：关闭Redis连接
    if system_status["redis_connected"] and redis:
        try:
            # 发布节点下线消息
            await redis.publish("system:node_offline", json.dumps({
                "node_id": NODE_ID,
                "timestamp": time.time()
            }))
            
            # 关闭Redis连接
            await redis.close()
            logger.info("Redis连接已关闭")
        except Exception as e:
            logger.error(f"关闭Redis连接时出错: {e}")
    
    logger.info("应用程序已完全关闭")

# 健康检查接口
@app.get("/health")
async def health_check():
    """系统健康状态检查接口"""
    # 检查系统组件
    components_status = {
        "redis": system_status["redis_connected"],
        "connection_manager": connection_manager.healthy if hasattr(connection_manager, 'healthy') else True,
        "resource_scheduler": not shutdown_event.is_set(),
        "system_monitor": system_monitor is not None
    }
    
    # 计算服务器正常运行时间
    uptime = "N/A"
    if "start_time" in system_status and system_status["start_time"]:
        try:
            from datetime import datetime
            if isinstance(system_status["start_time"], str):
                start_time = datetime.fromisoformat(system_status["start_time"])
            else:
                start_time = datetime.fromtimestamp(system_status["start_time"])
            uptime_seconds = (datetime.now() - start_time).total_seconds()
            uptime = f"{int(uptime_seconds // 86400)}d {int((uptime_seconds % 86400) // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
        except Exception as e:
            logger.error(f"计算运行时间出错: {e}")
            uptime = "N/A"
    
    # 获取连接统计信息
    connection_stats = await connection_manager.get_connection_stats()
    
    # 构建响应
    response = {
        "status": "ok" if system_status["is_healthy"] else "degraded",
        "degradation_level": system_status["degradation_level"],
        "components": components_status,
        "version": system_status.get("version", "2.0.0"),  # 使用get方法避免KeyError
        "node_id": NODE_ID,
        "start_time": system_status.get("start_time"),
        "uptime": uptime,
        "connections": connection_stats
    }
    
    # 根据系统状态设置响应状态码
    status_code = 200 if system_status["is_healthy"] else 503
    
    return JSONResponse(content=response, status_code=status_code)

# 首页路由
@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    if not os.path.exists(templates_path):
        return JSONResponse({
            "message": "聊天系统API运行中，但未找到前端模板文件",
            "status": "running",
            "api_docs": "/docs"
        })
    
    # 获取房间列表
    rooms = []
    if system_status["redis_connected"]:
        try:
            room_keys = await redis.keys("room:*")
            for room_key in room_keys:
                room_data = await redis.hgetall(room_key)
                if room_data:
                    room_id = room_key.split(":", 1)[1]
                    rooms.append({
                        "id": room_id,
                        "name": room_data.get("name", room_id),
                        "description": room_data.get("description", ""),
                        "users": int(room_data.get("user_count", "0"))
                    })
        except Exception as e:
            logger.error(f"获取房间列表时出错: {e}")
    else:
        # 单机模式下从内存获取房间
        rooms = [
            {"id": room_id, "name": room_data["name"], "description": room_data["description"], "users": len(room_data["users"])}
            for room_id, room_data in in_memory_rooms.items()
        ]
    
    # 获取连接统计信息
    connection_stats = await connection_manager.get_connection_stats()
    total_connections = connection_stats["total_connections"]
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "rooms": rooms,
            "system_status": {
                "mode": "分布式" if system_status["redis_connected"] else "单机",
                "is_healthy": system_status["is_healthy"],
                "degradation_level": system_status["degradation_level"],
                "connections": total_connections
            }
        }
    )

# 聊天室页面路由
@app.get("/chat/{room_id}", response_class=HTMLResponse)
async def get_chat_room(
    request: Request, 
    room_id: str, 
    user=Depends(get_current_user)
):
    # 如果用户未登录，重定向到首页
    if not user:
        return RedirectResponse(url="/")
    
    # 检查房间是否存在
    if redis:
        room_exists = await redis.exists(f"room:{room_id}:info")
        if not room_exists:
            # 创建默认房间信息
            await redis.hset(
                f"room:{room_id}:info",
                mapping={
                    "name": f"聊天室 {room_id}",
                    "description": "自动创建的聊天室",
                    "created_at": time.time(),
                    "created_by": user
                }
            )
    
    return templates.TemplateResponse(
        "chat.html", 
        {
            "request": request, 
            "room_id": room_id, 
            "user_id": user,
            "ws_path": f"/ws/{room_id}/{user}"
        }
    )

# WebSocket连接端点
@app.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str):
    # 检查连接数是否达到上限
    connection_stats = await connection_manager.get_connection_stats()
    active_connections = connection_stats["total_connections"]
    
    if active_connections >= MAX_CONNECTIONS:
        # 根据降级策略决定是否拒绝连接
        if system_status["degradation_level"] >= 2:
            await websocket.accept()  # 必须先接受连接才能发送关闭消息
            await websocket.close(code=1013, reason="服务器连接数已达上限，请稍后重试")
            return
    
    # 记录连接时的WebSocket对象，确保即使发生异常也能正确断开连接
    websocket_obj = websocket
    
    # 接受WebSocket连接
    connected = await connection_manager.connect(websocket, user_id, room_id)
    if not connected:
        logger.warning(f"WebSocket连接失败: {user_id} -> {room_id}")
        return
    
    # 更新房间用户计数
    if system_status["redis_connected"] and redis:
        try:
            # 将用户添加到房间集合
            await redis.sadd(f"room:{room_id}:users", user_id)
            # 更新房间统计信息
            await redis.hincrby(f"room:{room_id}", "user_count", 1)
        except Exception as e:
            logger.error(f"更新房间用户数据时出错: {e}")
    else:
        # 单机模式
        if room_id in in_memory_rooms:
            if "users" not in in_memory_rooms[room_id]:
                in_memory_rooms[room_id]["users"] = set()
            in_memory_rooms[room_id]["users"].add(user_id)
        else:
            in_memory_rooms[room_id] = {"users": {user_id}, "name": room_id, "created_at": time.time()}
    
    # 准备欢迎消息
    welcome_msg = {
        "type": "system",
        "content": f"欢迎 {user_id} 加入聊天室",
        "sender": "system",
        "room": room_id,
        "timestamp": time.time()
    }
    
    # 发送欢迎消息
    welcome_msg_json = json.dumps(welcome_msg)
    await connection_manager.broadcast_to_room(room_id, welcome_msg_json)
    
    # 发送历史消息
    try:
        history_messages = []
        if system_status["redis_connected"] and redis:
            try:
                # 从Redis获取最近的消息，使用超时
                async def get_messages():
                    try:
                        # 从有序集合获取消息ID，按时间戳倒序
                        message_ids = await redis.zrevrange(f"room:{room_id}:messages", 0, 49)
                        if not message_ids:
                            return []
                            
                        messages = []
                        
                        # 获取每条消息的详细信息
                        for msg_id in message_ids:
                            try:
                                # 处理可能的字节类型
                                if isinstance(msg_id, bytes):
                                    msg_id_str = msg_id.decode('utf-8')
                                else:
                                    msg_id_str = str(msg_id)
                                    
                                msg_data = await redis.hgetall(f"message:{msg_id_str}")
                                if msg_data:
                                    # 转换所有字段为字符串，处理可能的bytes类型
                                    processed_data = {}
                                    for k, v in msg_data.items():
                                        if isinstance(k, bytes):
                                            k = k.decode('utf-8')
                                        if isinstance(v, bytes):
                                            v = v.decode('utf-8')
                                        processed_data[k] = v
                                    
                                    # 转换时间戳为浮点数
                                    try:
                                        timestamp = float(processed_data.get("timestamp", 0))
                                    except (ValueError, TypeError):
                                        timestamp = 0
                                    
                                    messages.append({
                                        "id": msg_id_str,
                                        "room": room_id,
                                        "content": processed_data.get("content", ""),
                                        "sender": processed_data.get("sender", "system"),
                                        "timestamp": timestamp,
                                        "type": processed_data.get("type", "text")
                                    })
                            except Exception as e:
                                logger.error(f"获取消息 {msg_id} 失败: {e}")
                                continue
                        
                        # 按时间戳排序
                        return sorted(messages, key=lambda x: x.get("timestamp", 0))
                    except Exception as e:
                        logger.error(f"获取历史消息失败: {e}")
                        return []
                
                try:
                    # 设置5秒超时
                    history_messages = await asyncio.wait_for(get_messages(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"获取历史消息超时: {room_id}")
                except Exception as e:
                    logger.error(f"从Redis获取历史消息时出错: {e}")
            except Exception as e:
                logger.error(f"从Redis获取历史消息时出错: {e}")
        else:
            # 单机模式 - 从内存获取消息
            if room_id in in_memory_messages:
                history_messages = sorted(in_memory_messages[room_id], key=lambda x: x.get("timestamp", 0))[-50:]
        
        # 发送历史消息
        if history_messages:
            history_msg = {
                "type": "history",
                "messages": history_messages
            }
            await connection_manager.send_personal_message(user_id, json.dumps(history_msg))
    except Exception as e:
        logger.error(f"发送历史消息时出错: {e}")
    
    try:
        # 主消息循环
        while True:
            if shutdown_event.is_set():
                break
                
            # 接收来自客户端的消息
            try:
                # 设置接收超时，防止长时间阻塞
                message_data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                if not message_data.strip():
                    continue
                    
                try:
                    # 处理消息频率限制（防止洪水攻击）
                    if system_status["degradation_level"] >= 1:
                        await asyncio.sleep(0.5)  # 降级模式下，添加延迟
                    
                    # 解析消息
                    msg = json.loads(message_data)
                    
                    # 确保消息包含必要字段
                    if "content" not in msg or "type" not in msg:
                        continue
                    
                    # 处理不同类型的消息
                    msg["sender"] = user_id
                    msg["room"] = room_id  # 强制设置为当前房间ID，确保消息隔离
                    msg["timestamp"] = time.time()
                    
                    # 保存消息到存储
                    msg_id = f"{room_id}:{int(time.time() * 1000)}:{user_id}"
                    
                    # 确认消息类型
                    if msg["type"] == "ping":
                        # 心跳消息，直接返回pong
                        pong_msg = {
                            "type": "pong",
                            "timestamp": time.time()
                        }
                        await websocket.send_json(pong_msg)
                        
                    elif msg["type"] in ["text", "chat"]:
                        # 普通聊天消息
                        # 保存到Redis或内存
                        if system_status["redis_connected"] and redis:
                            try:
                                # 异步保存消息
                                asyncio.create_task(
                                    store_message_to_redis(room_id, msg)
                                )
                            except Exception as e:
                                logger.error(f"保存消息到Redis失败: {e}")
                        else:
                            # 单机模式 - 保存到内存
                            asyncio.create_task(
                                store_message_in_memory(room_id, msg)
                            )
                        
                        # 广播到当前房间
                        msg["room"] = room_id  # 再次确认房间ID正确
                        logger.debug(f"广播消息到房间 {room_id}: {msg}")
                        await connection_manager.broadcast_to_room(room_id, json.dumps(msg))
                    
                    elif msg["type"] == "private" and "to" in msg:
                        # 私聊消息
                        recipient = msg["to"]
                        
                        # 修改消息类型
                        msg["type"] = "private"
                        msg["id"] = msg_id
                        
                        # 发送给接收者
                        await connection_manager.send_personal_message(recipient, json.dumps(msg))
                        # 同时发送给发送者
                        await connection_manager.send_personal_message(user_id, json.dumps(msg))
                    
                    elif msg["type"] == "command":
                        # 处理命令消息
                        if msg["content"].startswith("/help"):
                            # 发送帮助信息
                            help_msg = {
                                "type": "system",
                                "content": "可用命令:\n/help - 显示帮助\n/users - 显示在线用户\n/private <用户名> <消息> - 发送私聊消息",
                                "sender": "system",
                                "room": room_id,
                                "timestamp": time.time()
                            }
                            await connection_manager.send_personal_message(help_msg, user_id)
                        
                        elif msg["content"].startswith("/users"):
                            # 获取房间在线用户
                            online_users = []
                            if system_status["redis_connected"] and redis:
                                try:
                                    online_users = await redis.smembers(f"room:{room_id}:users")
                                except Exception as e:
                                    logger.error(f"获取在线用户列表失败: {e}")
                            else:
                                # 单机模式
                                if room_id in in_memory_rooms:
                                    online_users = list(in_memory_rooms[room_id]["users"])
                            
                            # 发送用户列表
                            users_msg = {
                                "type": "system",
                                "content": f"在线用户 ({len(online_users)}):\n" + "\n".join(online_users),
                                "sender": "system",
                                "room": room_id,
                                "timestamp": time.time()
                            }
                            await connection_manager.send_personal_message(users_msg, user_id)
                
                except json.JSONDecodeError:
                    logger.warning(f"无效的消息格式: {message_data[:100]}")
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
                    logger.error(traceback.format_exc())
            
            except asyncio.TimeoutError:
                # 接收超时，发送ping来保持连接
                try:
                    ping_msg = {
                        "type": "ping",
                        "timestamp": time.time()
                    }
                    await websocket.send_json(ping_msg)
                except Exception:
                    # 如果发送失败，说明连接可能已关闭
                    break
            except Exception as e:
                # WebSocket可能已关闭
                logger.debug(f"接收消息失败，可能连接已关闭: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"用户断开连接: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket连接错误: {e}")
        logger.error(traceback.format_exc())
    finally:
        try:
            # 断开用户连接
            # 传递正确的参数顺序：websocket对象, user_id, room_id
            await connection_manager.disconnect(websocket_obj, user_id, room_id)
            
            # 更新房间用户计数
            if system_status["redis_connected"] and redis:
                try:
                    # 从房间集合中移除用户
                    await redis.srem(f"room:{room_id}:users", user_id)
                    # 更新房间统计信息
                    await redis.hincrby(f"room:{room_id}", "user_count", -1)
                except Exception as e:
                    logger.error(f"更新房间用户数据时出错: {e}")
            else:
                # 单机模式
                if room_id in in_memory_rooms and "users" in in_memory_rooms[room_id] and user_id in in_memory_rooms[room_id]["users"]:
                    in_memory_rooms[room_id]["users"].remove(user_id)
            
            # 广播用户离开消息
            leave_msg = {
                "type": "system",
                "content": f"{user_id} 离开了聊天室",
                "sender": "system",
                "room": room_id,
                "timestamp": time.time()
            }
            try:
                # 只向当前聊天室广播
                await connection_manager.broadcast_to_room(room_id, json.dumps(leave_msg))
            except Exception as e:
                logger.error(f"广播用户离开消息出错: {e}")
        except Exception as e:
            logger.error(f"用户断开连接清理失败: {e}")

# API端点: 发送消息
@app.post("/api/messages", dependencies=[Depends(verify_api_key)])
async def send_message(message: Message, background_tasks: BackgroundTasks):
    """通过API发送消息"""
    if not system_status["is_healthy"] and message.priority > 3:
        return JSONResponse(
            status_code=503,
            content={"error": "系统处于降级状态，暂时只接受高优先级消息"}
        )
    
    try:
        # 通过连接管理器发布消息
        background_tasks.add_task(
            connection_manager.publish_message,
            user_id=message.user_id,
            room_id=message.room_id,
            message_type=message.message_type,
            content=message.content,
            priority=message.priority
        )
        
        # 增加消息计数
        system_monitor.increment_counter("messages_received")
        system_monitor.increment_counter("requests")
        
        return {"success": True, "message": "消息已发送"}
    except Exception as e:
        logger.error(f"API发送消息错误: {e}")
        system_monitor.increment_counter("errors")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# API端点: 获取房间列表
@app.get("/api/rooms")
async def get_rooms():
    """获取所有聊天室列表"""
    try:
        rooms = []
        
        if system_status["redis_connected"] and redis:
            # 从Redis获取房间信息
            room_keys = await redis.keys("room:*")
            room_ids = []
            
            for key in room_keys:
                parts = key.split(":")
                if len(parts) >= 2 and parts[0] == "room":
                    room_id = parts[1]
                    if room_id not in room_ids and not room_id.endswith(":users") and not room_id.endswith(":messages"):
                        room_ids.append(room_id)
            
            for room_id in room_ids:
                try:
                    room_data = await redis.hgetall(f"room:{room_id}")
                    user_count = await redis.scard(f"room:{room_id}:users")
                    
                    rooms.append({
                        "id": room_id,
                        "name": room_data.get("name", room_id),
                        "description": room_data.get("description", ""),
                        "users": user_count,
                        "created_at": float(room_data.get("created_at", 0))
                    })
                except Exception as e:
                    logger.error(f"获取房间 {room_id} 信息时出错: {e}")
        else:
            # 单机模式，使用内存中的房间
            for room_id, data in in_memory_rooms.items():
                rooms.append({
                    "id": room_id,
                    "name": data.get("name", room_id),
                    "description": data.get("description", ""),
                    "users": len(data.get("users", set())),
                    "created_at": data.get("created_at", time.time() - 3600)  # 假设一小时前创建
                })
        
        # 如果没有房间，添加默认房间
        if not rooms:
            for room_id in ["general", "tech", "random"]:
                rooms.append({
                    "id": room_id,
                    "name": in_memory_rooms.get(room_id, {}).get("name", f"聊天室 {room_id}"),
                    "description": in_memory_rooms.get(room_id, {}).get("description", "默认聊天室"),
                    "users": len(in_memory_rooms.get(room_id, {}).get("users", set())),
                    "created_at": time.time() - 3600
                })
        
        # 按用户数量排序
        rooms.sort(key=lambda x: x["users"], reverse=True)
        
        # 返回房间ID列表（简化的格式，适合前端）
        return {"rooms": [room["id"] for room in rooms]}
    except Exception as e:
        logger.error(f"获取房间列表错误: {e}")
        # 出错时返回默认房间
        return {"rooms": ["general", "tech", "random"]}

# API端点: 获取房间用户列表
@app.get("/api/rooms/{room_id}/users")
async def get_room_users(room_id: str):
    """获取房间内的用户列表"""
    try:
        users = []
        
        if system_status["redis_connected"] and redis:
            # 从Redis获取用户列表
            try:
                user_ids = await redis.smembers(f"room:{room_id}:users")
                users = [user_id for user_id in user_ids]
            except Exception as e:
                logger.error(f"从Redis获取房间 {room_id} 用户列表失败: {e}")
        else:
            # 单机模式，从内存获取
            if room_id in in_memory_rooms and "users" in in_memory_rooms[room_id]:
                users = list(in_memory_rooms[room_id]["users"])
        
        return {"users": users, "count": len(users)}
    except Exception as e:
        logger.error(f"获取房间用户列表错误: {e}")
        return {"users": [], "count": 0}

# API端点: 创建房间
@app.post("/api/rooms", dependencies=[Depends(verify_api_key)])
async def create_room(room: RoomCreate):
    """创建新的聊天室"""
    try:
        if not redis:
            raise HTTPException(status_code=503, detail="Redis服务不可用")
        
        # 检查房间是否已存在
        room_exists = await redis.exists(f"room:{room.room_id}:info")
        if room_exists:
            return JSONResponse(
                status_code=409,
                content={"error": f"房间 {room.room_id} 已存在"}
            )
        
        # 创建房间信息
        await redis.hset(
            f"room:{room.room_id}:info",
            mapping={
                "name": room.name,
                "description": room.description or "",
                "capacity": room.capacity,
                "created_at": time.time()
            }
        )
        
        return {
            "success": True,
            "room_id": room.room_id,
            "name": room.name
        }
    except Exception as e:
        logger.error(f"创建房间错误: {e}")
        system_monitor.increment_counter("errors")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# API端点: 获取系统状态
@app.get("/api/system/status", dependencies=[Depends(verify_api_key)])
async def get_system_status():
    """获取系统状态信息"""
    if not system_monitor:
        return JSONResponse(
            status_code=503,
            content={"error": "系统监控未初始化"}
        )
    
    try:
        status = await system_monitor.get_system_status()
        
        # 添加当前节点信息
        status["node"] = {
            "id": NODE_ID,
            "max_connections": MAX_CONNECTIONS,
            "current_connections": connection_manager.current_connections,
            "is_degraded": connection_manager.is_degraded
        }
        
        return status
    except Exception as e:
        logger.error(f"获取系统状态错误: {e}")
        system_monitor.increment_counter("errors")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# API端点: 配置系统
@app.post("/api/system/config", dependencies=[Depends(verify_api_key)])
async def configure_system(config: SystemConfig):
    """配置系统参数"""
    global MAX_CONNECTIONS
    
    try:
        # 更新最大连接数
        if config.max_connections != MAX_CONNECTIONS:
            MAX_CONNECTIONS = config.max_connections
            connection_manager.connection_limit = MAX_CONNECTIONS
            logger.info(f"最大连接数已更新为: {MAX_CONNECTIONS}")
        
        # 手动设置降级级别
        if system_status["degradation_level"] != config.degradation_level:
            old_level = system_status["degradation_level"]
            system_status["degradation_level"] = config.degradation_level
            
            # 更新连接管理器状态
            connection_manager.is_degraded = config.degradation_level > 0
            
            # 通知状态变更
            await status_change_handler({
                "node_id": NODE_ID,
                "timestamp": time.time(),
                "old_status": {"degradation_level": old_level},
                "new_status": {"degradation_level": config.degradation_level},
                "metrics": {}
            })
            
            logger.info(f"系统降级级别已手动设置为: {config.degradation_level}")
        
        return {
            "success": True,
            "max_connections": MAX_CONNECTIONS,
            "degradation_level": system_status["degradation_level"]
        }
    except Exception as e:
        logger.error(f"配置系统错误: {e}")
        system_monitor.increment_counter("errors")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# 异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    system_monitor.increment_counter("errors")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"未处理的异常: {traceback.format_exc()}")
    system_monitor.increment_counter("errors")
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误"}
    )

# 基准测试端点
@app.get("/benchmark/echo/{message}")
async def echo(message: str):
    """简单的回显端点，用于基准测试"""
    system_monitor.increment_counter("requests")
    return {"message": message, "timestamp": time.time()}

@app.get("/benchmark/redis")
async def redis_benchmark():
    """Redis操作基准测试"""
    if not REDIS_AVAILABLE:
        return {"status": "error", "message": "Redis不可用"}
    
    if not redis:
        return {"status": "error", "message": "Redis连接失败"}
    
    # 测试基本操作
    start_time = time.time()
    await redis.set("benchmark:test", "value")
    get_result = await redis.get("benchmark:test")
    basic_time = time.time() - start_time
    
    # 测试管道操作
    start_time = time.time()
    pipe = redis.pipeline()
    for i in range(100):
        pipe.set(f"benchmark:pipe:{i}", f"value_{i}")
    await pipe.execute()
    pipeline_time = time.time() - start_time
    
    # 测试HTTP请求（如果aiohttp可用）
    http_time = None
    if AIOHTTP_AVAILABLE:
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/health") as resp:
                    await resp.text()
            http_time = time.time() - start_time
        except Exception as e:
            http_time = f"错误: {str(e)}"
    else:
        http_time = "aiohttp不可用"
    
    # 清理测试数据
    await redis.delete("benchmark:test")
    for i in range(100):
        await redis.delete(f"benchmark:pipe:{i}")
    
    return {
        "status": "ok",
        "basic_op_time": basic_time,
        "pipeline_op_time": pipeline_time,
        "http_request_time": http_time
    }

# 存储消息函数
async def store_message_to_redis(room_id: str, message: Dict):
    """将消息保存到Redis中"""
    try:
        # 确保消息有时间戳
        if "timestamp" not in message:
            message["timestamp"] = time.time()
            
        # 确保所有消息字段都是字符串类型
        timestamp = message.get("timestamp", time.time())
        if not isinstance(timestamp, (int, float)):
            try:
                timestamp = float(timestamp)
            except (ValueError, TypeError):
                timestamp = time.time()
        
        # 生成消息ID
        msg_id = f"{room_id}:{int(timestamp * 1000)}:{message.get('sender', 'system')}"
            
        # 使用Redis hash存储消息
        mapping = {
            "content": str(message.get("content", "")),
            "sender": str(message.get("sender", "system")),
            "type": str(message.get("type", "text")),
            "timestamp": str(timestamp)
        }
        
        # 存储消息内容
        await redis.hset(f"message:{msg_id}", mapping=mapping)
        
        # 使用有序集合保存消息ID，以时间戳为分数
        await redis.zadd(
            f"room:{room_id}:messages", 
            {msg_id: timestamp}
        )
        
        # 限制消息数量，保留最新的100条
        await redis.zremrangebyrank(f"room:{room_id}:messages", 0, -101)
        
        # 更新房间的最后活动时间
        await redis.hset(f"room:{room_id}", "last_active", str(timestamp))
        
        return True
    except Exception as e:
        logger.error(f"保存消息到Redis失败: {e}")
        return False

async def store_message_in_memory(room_id: str, message: Dict):
    """将消息保存到内存中（Redis不可用时的备用方案）"""
    # 确保消息有时间戳
    if "timestamp" not in message:
        message["timestamp"] = time.time()
        
    # 添加到内存存储中
    if room_id not in in_memory_messages:
        in_memory_messages[room_id] = []
        
    # 添加消息
    in_memory_messages[room_id].append(message)
    
    # 限制长度
    if len(in_memory_messages[room_id]) > 100:
        in_memory_messages[room_id] = in_memory_messages[room_id][-100:]

# 单机模式下获取历史消息
async def get_room_history_from_memory(room_id: str, limit: int = 50) -> List[Dict]:
    if room_id not in in_memory_messages:
        return []
    
    # 返回最近的消息
    return in_memory_messages[room_id][-limit:]

# 主函数
def main():
    """直接运行脚本时的入口点"""
    # 设置环境变量表示Uvicorn运行
    os.environ["UVICORN_RUNNING"] = "1"
    
    # 使用Uvicorn启动应用
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        loop="uvloop"
    )

if __name__ == "__main__":
    main() 