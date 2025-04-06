from typing import Dict, List, Set, Optional, Any, Tuple
import json
import asyncio
import logging
import time
from collections import defaultdict
import random
import os
import uuid
from datetime import datetime
from starlette.websockets import WebSocket, WebSocketState

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
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ConnectionManager")

class ConnectionManager:
    """
    WebSocket连接管理器，负责处理多个客户端连接、消息广播和用户状态管理
    设计为单例模式，确保整个应用中只有一个连接管理实例
    优化支持百万级并发连接
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConnectionManager, cls).__new__(cls)
            # 使用分片存储连接，提高并发性能
            cls._instance.connection_shards = [defaultdict(dict) for _ in range(64)]
            cls._instance.user_room_map: Dict[str, Set[str]] = {}
            cls._instance.room_user_map: Dict[str, Set[str]] = {}
            cls._instance.redis_client = None
            cls._instance.initialized = False
            cls._instance.message_queue = asyncio.Queue()
            cls._instance.broadcast_queues = [asyncio.Queue() for _ in range(16)]  # 广播消息队列分片
            cls._instance.processing_messages = False
            cls._instance.node_id = os.getenv("NODE_ID", f"node-{random.randint(1000, 9999)}")
            cls._instance.connection_limit = int(os.getenv("MAX_CONNECTIONS", "100000"))
            cls._instance.current_connections = 0
            cls._instance.is_degraded = False
            cls._instance.healthy = True
        return cls._instance
    
    async def initialize(self, redis_conn = None):
        """初始化连接管理器"""
        if self.initialized:
            return
            
        self.redis_client = redis_conn
        
        # 启动消息处理器
        self.processing_messages = True
        
        # 启动多个消息处理任务，提高消息处理的并行度
        for i in range(8):
            asyncio.create_task(self.message_processor(f"processor-{i}"))
        
        # 启动多个广播处理任务
        for i in range(16):
            asyncio.create_task(self.broadcast_processor(i))
            
        # 启动Redis订阅，用于跨节点消息同步（仅当Redis可用时）
        if self.redis_client:
            asyncio.create_task(self._start_redis_subscriber())
        
        # 启动健康检查
        asyncio.create_task(self._health_check())
        
        # 启动过期连接清理任务
        asyncio.create_task(self._clean_stale_connections())
        
        # 初始化完成
        self.initialized = True
        
        logger.info(f"连接管理器已初始化, 节点ID: {self.node_id}, 模式: {'分布式' if self.redis_client else '单机'}")
    
    async def _start_redis_subscriber(self):
        """启动Redis订阅，用于跨节点消息同步"""
        if not self.redis_client:
            return
            
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe("chat:broadcast")
            
            logger.info("Started Redis subscriber for chat:broadcast channel")
            
            # 持续监听消息
            while self.processing_messages:
                try:
                    # 使用超时获取消息
                    try:
                        message = await asyncio.wait_for(
                            pubsub.get_message(ignore_subscribe_messages=True),
                            timeout=1.0
                        )
                        
                        if message and message["type"] == "message":
                            data = json.loads(message["data"])
                            # 只处理来自其他节点的消息，避免重复广播
                            if data.get("source_node") != self.node_id:
                                await self._broadcast_from_redis(data)
                    except asyncio.TimeoutError:
                        # 超时是正常的，继续轮询
                        await asyncio.sleep(0.1)
                except Exception as e:
                    # 降低错误日志频率
                    if random.random() < 0.05:  # 只记录5%的错误
                        logger.error(f"Redis订阅者错误: {str(e)}")
                    await asyncio.sleep(1)  # 错误后短暂延迟，避免CPU占用过高
        except Exception as e:
            logger.error(f"Redis订阅初始化错误: {e}")
            # 不抛出异常，让系统继续运行在单机模式下
    
    def _get_shard_index(self, key: str) -> int:
        """计算分片索引，使用简单的哈希函数"""
        return hash(key) % len(self.connection_shards)
    
    def _get_broadcast_queue_index(self, room_id: str) -> int:
        """计算广播队列索引"""
        return hash(room_id) % len(self.broadcast_queues)
    
    async def connect(self, websocket: WebSocket, user_id: str, room_id: str):
        """建立新的WebSocket连接"""
        # 检查是否超过连接限制
        if self.current_connections >= self.connection_limit:
            if not self.is_degraded:
                logger.warning(f"连接数达到上限 ({self.connection_limit})，启动服务降级模式")
                self.is_degraded = True
            
            # 降级处理：拒绝新连接或限制某些功能
            await websocket.accept()
            await websocket.send_text(json.dumps({
                "type": "system",
                "content": "服务器负载过高，已进入降级模式，部分功能可能受限",
                "timestamp": time.time()
            }))
            return False
        
        try:
            # 接受WebSocket连接
            await websocket.accept()
            
            # 计算用户分片索引
            shard_index = self._get_shard_index(user_id)
            
            # 初始化用户连接字典
            self.connection_shards[shard_index][user_id][room_id] = websocket
            
            # 更新用户-房间映射
            if user_id not in self.user_room_map:
                self.user_room_map[user_id] = set()
            self.user_room_map[user_id].add(room_id)
            
            # 更新房间-用户映射
            if room_id not in self.room_user_map:
                self.room_user_map[room_id] = set()
            self.room_user_map[room_id].add(user_id)
            
            # 递增连接计数
            self.current_connections += 1
            
            logger.info(f"用户 {user_id} 连接到房间 {room_id}, 当前连接数: {self.current_connections}")
            
            # 更新Redis中的房间用户列表（仅当Redis可用时）
            if self.redis_client:
                await self.redis_client.sadd(f"room:{room_id}:users", user_id)
                await self.redis_client.sadd(f"node:{self.node_id}:users", user_id)
                
                # 存储用户连接时间和最后活动时间
                await self.redis_client.hset(
                    f"user:{user_id}:meta",
                    mapping={
                        "connected_at": time.time(),
                        "last_activity": time.time(),
                        "node_id": self.node_id
                    }
                )
            
            # 恢复服务降级状态（如果之前是降级状态）
            if self.is_degraded and self.current_connections < self.connection_limit * 0.8:
                logger.info("连接数降至安全水平，退出服务降级模式")
                self.is_degraded = False
            
            return True
        except Exception as e:
            logger.error(f"建立连接失败: {e}")
            return False
    
    async def disconnect(self, websocket: WebSocket, user_id: str, room_id: str):
        """断开WebSocket连接"""
        try:
            # 计算用户分片索引
            shard_index = self._get_shard_index(user_id)
            
            # 移除连接对象
            if user_id in self.connection_shards[shard_index] and room_id in self.connection_shards[shard_index][user_id]:
                del self.connection_shards[shard_index][user_id][room_id]
                
                # 如果用户没有其他连接，清理映射
                if not self.connection_shards[shard_index][user_id]:
                    del self.connection_shards[shard_index][user_id]
            
            # 更新用户-房间映射
            if user_id in self.user_room_map:
                self.user_room_map[user_id].discard(room_id)
                if not self.user_room_map[user_id]:
                    del self.user_room_map[user_id]
            
            # 更新房间-用户映射
            if room_id in self.room_user_map:
                self.room_user_map[room_id].discard(user_id)
                if not self.room_user_map[room_id]:
                    del self.room_user_map[room_id]
            
            # 递减连接计数
            self.current_connections = max(0, self.current_connections - 1)
            
            # 更新Redis中的数据（仅当Redis可用时）
            if self.redis_client:
                await self.redis_client.srem(f"room:{room_id}:users", user_id)
                await self.redis_client.srem(f"node:{self.node_id}:users", user_id)
                
                # 发布用户离开消息
                await self.publish_message(
                    user_id="system",
                    room_id=room_id,
                    message_type="system",
                    content=f"用户 {user_id} 离开了聊天室"
                )
            
            logger.info(f"用户 {user_id} 断开与房间 {room_id} 的连接, 当前连接数: {self.current_connections}")
            
            # 恢复服务降级状态（如果之前是降级状态）
            if self.is_degraded and self.current_connections < self.connection_limit * 0.8:
                logger.info("连接数降至安全水平，退出服务降级模式")
                self.is_degraded = False
            
            return True
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            return False
    
    async def send_personal_message(self, user_id: str, message: str):
        """发送个人消息"""
        # 获取用户的分片索引
        shard_index = self._get_shard_index(user_id)
        
        if user_id in self.connection_shards[shard_index]:
            failed_rooms = []
            for room_id, websocket in self.connection_shards[shard_index][user_id].items():
                try:
                    if websocket.client_state != WebSocketState.DISCONNECTED:
                        await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"发送个人消息失败 {user_id}/{room_id}: {e}")
                    failed_rooms.append(room_id)
            
            # 清理失败的连接
            for room_id in failed_rooms:
                if room_id in self.connection_shards[shard_index][user_id]:
                    await self.disconnect(
                        self.connection_shards[shard_index][user_id][room_id], 
                        user_id, 
                        room_id
                    )
            
            return True
        return False
    
    async def broadcast_to_room(self, room_id: str, message: str):
        """广播消息到指定房间，使用队列提高性能"""
        # 使用广播队列处理房间消息
        queue_index = self._get_broadcast_queue_index(room_id)
        await self.broadcast_queues[queue_index].put((room_id, message))
        return True
    
    async def broadcast_processor(self, queue_index: int):
        """广播队列处理器"""
        while self.processing_messages:
            try:
                # 从队列获取广播任务
                room_id, message = await self.broadcast_queues[queue_index].get()
                
                # 添加调试日志
                try:
                    msg_data = json.loads(message)
                    msg_room = msg_data.get("room", "unknown")
                    msg_type = msg_data.get("type", "unknown")
                    
                    # 验证消息的room字段与目标房间匹配
                    if msg_room != "unknown" and msg_room != room_id:
                        logger.warning(f"消息的room字段({msg_room})与目标房间({room_id})不匹配，消息将被丢弃")
                        # 不处理房间不匹配的消息，确保完全隔离
                        self.broadcast_queues[queue_index].task_done()
                        continue
                    
                    # 确保消息总是包含正确的房间ID
                    if msg_room == "unknown" or not msg_room:
                        msg_data["room"] = room_id
                        message = json.dumps(msg_data)
                    
                    logger.debug(f"处理广播消息: room={room_id}, type={msg_type}")
                except Exception as e:
                    logger.warning(f"解析广播消息时出错: {e}")
                    # JSON解析错误时，标记任务完成并跳过
                    self.broadcast_queues[queue_index].task_done()
                    continue
                
                if room_id in self.room_user_map:
                    disconnected_users = []
                    
                    for user_id in self.room_user_map[room_id]:
                        # 获取用户的分片索引
                        shard_index = self._get_shard_index(user_id)
                        
                        if (user_id in self.connection_shards[shard_index] and 
                            room_id in self.connection_shards[shard_index][user_id]):
                            websocket = self.connection_shards[shard_index][user_id][room_id]
                            try:
                                if websocket.client_state != WebSocketState.DISCONNECTED:
                                    await websocket.send_text(message)
                            except Exception as e:
                                logger.error(f"向房间广播失败 {user_id}/{room_id}: {e}")
                                disconnected_users.append((user_id, room_id))
                    
                    # 清理断开的连接
                    for user_id, room_id in disconnected_users:
                        shard_index = self._get_shard_index(user_id)
                        if (user_id in self.connection_shards[shard_index] and 
                            room_id in self.connection_shards[shard_index][user_id]):
                            await self.disconnect(
                                self.connection_shards[shard_index][user_id][room_id],
                                user_id,
                                room_id
                            )
                
                # 标记广播任务完成
                self.broadcast_queues[queue_index].task_done()
                
            except Exception as e:
                logger.error(f"广播处理器错误: {e}")
                await asyncio.sleep(0.1)  # 避免因错误导致CPU过度使用
    
    async def publish_message(self, user_id: str, room_id: str, message_type: str, content: str, **kwargs):
        """发布消息到队列"""
        # 消息限流：降级模式下减少消息频率
        if self.is_degraded and message_type not in ["system", "error"]:
            # 对非系统消息进行采样，降级模式下只处理部分消息
            if random.random() > 0.3:  # 只处理30%的消息
                return False
        
        message = {
            "user_id": user_id,
            "room_id": room_id,
            "type": message_type,
            "content": content,
            "timestamp": time.time(),
            "source_node": self.node_id,
            **kwargs
        }
        
        # 将消息添加到队列
        await self.message_queue.put(message)
        
        # 更新用户最后活动时间
        if user_id != "system" and self.redis_client:
            await self.redis_client.hset(f"user:{user_id}:meta", "last_activity", time.time())
        
        return True
    
    async def message_processor(self, processor_id: str):
        """处理消息队列中的消息"""
        logger.info(f"启动消息处理器 {processor_id}")
        
        while self.processing_messages:
            try:
                # 从队列获取消息
                message = await self.message_queue.get()
                
                # 确保消息包含有效的房间ID
                room_id = message.get("room_id")
                if not room_id:
                    logger.warning(f"消息缺少有效的room_id字段: {message}")
                    self.message_queue.task_done()
                    continue
                
                # 强制验证消息的room字段与room_id一致，并修复不一致的情况
                if "room" not in message:
                    message["room"] = room_id
                elif message["room"] != room_id:
                    # 记录警告，但统一修正为room_id
                    logger.warning(f"消息的room字段({message['room']})与room_id({room_id})不一致，已修正")
                    message["room"] = room_id
                
                # 消息序列化
                message_json = json.dumps(message)
                
                # 根据消息类型处理
                if message["type"] in ["chat", "text"]:  # 支持两种类型名称
                    # 广播到房间
                    await self.broadcast_to_room(room_id, message_json)
                    
                    # 持久化消息
                    await self.persist_message(message)
                    
                elif message["type"] == "private":
                    # 发送私信
                    target_user = message.get("target")
                    if target_user:
                        await self.send_personal_message(target_user, message_json)
                        await self.send_personal_message(message["user_id"], message_json)
                        
                        # 持久化私信
                        await self.persist_private_message(message)
                
                elif message["type"] == "system":
                    # 广播系统消息
                    await self.broadcast_to_room(room_id, message_json)
                    
                    # 系统消息也持久化
                    await self.persist_message(message)
                
                # 发布到Redis频道，供其他节点消费（仅当Redis可用时）
                if self.redis_client:
                    await self.redis_client.publish("chat:broadcast", message_json)
                
                # 标记任务完成
                self.message_queue.task_done()
            
            except Exception as e:
                logger.error(f"消息处理错误: {e}")
                # 防止因错误导致CPU过度使用
                await asyncio.sleep(0.1)
    
    async def persist_message(self, message: Dict[str, Any]):
        """持久化聊天消息到Redis"""
        # Redis不可用时跳过
        if not self.redis_client:
            return
            
        try:
            # 降级模式下减少消息持久化
            if self.is_degraded and message["type"] not in ["system", "error"]:
                # 只保存部分聊天消息
                if random.random() > 0.5:  # 只保存50%的消息
                    return
            
            # 准备消息数据
            room_id = message["room_id"]
            
            # 确保消息有时间戳
            timestamp = message.get("timestamp", time.time())
            if not isinstance(timestamp, (int, float)):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = time.time()
            
            # 生成消息ID
            msg_id = f"{room_id}:{int(timestamp * 1000)}:{message.get('user_id', 'system')}"
            
            # 使用哈希表存储消息内容
            mapping = {
                "content": str(message.get("content", "")),
                "sender": str(message.get("user_id", "system")),
                "type": str(message.get("type", "text")),
                "timestamp": str(timestamp)
            }
            
            # 使用超时机制
            async def save_message():
                # 存储消息内容
                await self.redis_client.hset(f"message:{msg_id}", mapping=mapping)
                
                # 使用有序集合保存消息ID，以时间戳为分数
                await self.redis_client.zadd(f"room:{room_id}:messages", {msg_id: timestamp})
                
                # 限制消息数量，保留最新的1000条
                await self.redis_client.zremrangebyrank(f"room:{room_id}:messages", 0, -1001)
            
            # 设置超时，避免阻塞
            try:
                await asyncio.wait_for(save_message(), timeout=1.0)
            except asyncio.TimeoutError:
                # 忽略超时，不阻塞主流程
                return
                
        except Exception as e:
            # 降低错误日志频率
            if random.random() < 0.1:  # 只记录10%的错误
                logger.error(f"持久化消息失败: {e}")
    
    async def persist_private_message(self, message: Dict[str, Any]):
        """持久化私信消息到Redis"""
        try:
            # Redis不可用时跳过
            if not self.redis_client:
                return
            
            # 确保消息有时间戳
            timestamp = message.get("timestamp", time.time())
            if not isinstance(timestamp, (int, float)):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = time.time()
            
            # 获取对话双方用户ID
            user1 = message.get("user_id", "unknown")
            user2 = message.get("target", "unknown")
            
            if user1 == "unknown" or user2 == "unknown":
                logger.warning("私信消息缺少用户ID或目标用户ID")
                return
            
            # 确保用户ID排序一致，便于查询
            if user1 > user2:
                user1, user2 = user2, user1
            
            # 生成消息ID
            msg_id = f"private:{user1}:{user2}:{int(timestamp * 1000)}"
            
            # 使用哈希表存储消息内容
            mapping = {
                "content": str(message.get("content", "")),
                "sender": str(message.get("user_id", "system")),
                "receiver": str(message.get("target", "")),
                "type": "private",
                "timestamp": str(timestamp)
            }
            
            # 异步存储，带超时保护
            async def save_message():
                # 存储消息内容
                await self.redis_client.hset(f"message:{msg_id}", mapping=mapping)
                
                # 在有序集合中存储消息ID，对双方用户都存储一份
                key = f"private:{user1}:{user2}:messages"
                await self.redis_client.zadd(key, {msg_id: timestamp})
                
                # 限制消息数量，保留最新的100条
                await self.redis_client.zremrangebyrank(key, 0, -101)
            
            # 设置超时保护
            try:
                await asyncio.wait_for(save_message(), timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("保存私信消息超时")
                return
            
        except Exception as e:
            logger.error(f"持久化私信失败: {e}")
    
    async def get_room_history(self, room_id: str, limit: int = 50) -> List[Dict]:
        """获取房间历史消息"""
        try:
            if not self.redis_client:
                return []
            
            try:
                # 使用超时机制
                async def fetch_history():
                    messages = []
                    # 使用有序集合而不是列表
                    key = f"room:{room_id}:messages"
                    # 获取消息ID
                    msg_ids = await self.redis_client.zrevrange(key, 0, limit - 1)
                    
                    for msg_id in msg_ids:
                        # 处理可能的bytes类型
                        if isinstance(msg_id, bytes):
                            msg_id_str = msg_id.decode('utf-8')
                        else:
                            msg_id_str = str(msg_id)
                            
                        # 获取消息详情
                        msg_data = await self.redis_client.hgetall(f"message:{msg_id_str}")
                        if msg_data:
                            # 处理bytes类型
                            msg_dict = {}
                            for k, v in msg_data.items():
                                if isinstance(k, bytes):
                                    k = k.decode('utf-8')
                                if isinstance(v, bytes):
                                    v = v.decode('utf-8')
                                msg_dict[k] = v
                            
                            # 尝试转换时间戳
                            try:
                                msg_dict["timestamp"] = float(msg_dict.get("timestamp", 0))
                            except (ValueError, TypeError):
                                msg_dict["timestamp"] = 0
                                
                            msg_dict["room"] = room_id
                            msg_dict["id"] = msg_id_str
                            messages.append(msg_dict)
                    
                    return sorted(messages, key=lambda x: x.get("timestamp", 0))
                
                # 设置超时，避免阻塞
                return await asyncio.wait_for(fetch_history(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning(f"获取房间历史消息超时: {room_id}")
                return []
                
        except Exception as e:
            # 降低错误日志频率
            if random.random() < 0.1:  # 只记录10%的错误
                logger.error(f"获取房间历史消息失败: {e}")
            return []
    
    async def get_private_history(self, user1: str, user2: str, limit: int = 50) -> List[Dict]:
        """获取两用户间的私信历史"""
        try:
            if not self.redis_client:
                return []
            
            # 确保用户ID排序一致
            if user1 > user2:
                user1, user2 = user2, user1
            
            # 获取私信历史
            messages = []    
            key = f"private:{user1}:{user2}:messages"
            
            # 使用超时机制
            async def fetch_history():
                # 获取消息ID
                msg_ids = await self.redis_client.zrevrange(key, 0, limit - 1)
                result = []
                
                for msg_id in msg_ids:
                    # 处理可能的bytes类型
                    if isinstance(msg_id, bytes):
                        msg_id_str = msg_id.decode('utf-8')
                    else:
                        msg_id_str = str(msg_id)
                        
                    # 获取消息详情
                    msg_data = await self.redis_client.hgetall(f"message:{msg_id_str}")
                    if msg_data:
                        # 处理bytes类型
                        msg_dict = {}
                        for k, v in msg_data.items():
                            if isinstance(k, bytes):
                                k = k.decode('utf-8')
                            if isinstance(v, bytes):
                                v = v.decode('utf-8')
                            msg_dict[k] = v
                        
                        # 添加额外信息
                        msg_dict["id"] = msg_id_str
                        
                        # 尝试转换时间戳
                        try:
                            msg_dict["timestamp"] = float(msg_dict.get("timestamp", 0))
                        except (ValueError, TypeError):
                            msg_dict["timestamp"] = 0
                            
                        result.append(msg_dict)
                
                return sorted(result, key=lambda x: x.get("timestamp", 0))
            
            # 使用超时机制
            try:
                messages = await asyncio.wait_for(fetch_history(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning(f"获取私信历史超时: {user1}-{user2}")
                return []
                
            return messages
        except Exception as e:
            logger.error(f"获取私信历史失败: {e}")
            return []
    
    async def get_room_users(self, room_id: str) -> List[str]:
        """获取房间用户列表"""
        try:
            if room_id in self.room_user_map:
                return list(self.room_user_map[room_id])
            
            if not self.redis_client:
                return []
            
            users = await self.redis_client.smembers(f"room:{room_id}:users")
            return [user.decode('utf-8') for user in users]
        except Exception as e:
            logger.error(f"获取房间用户列表失败: {e}")
            return []
    
    async def get_user_rooms(self, user_id: str) -> List[str]:
        """获取用户加入的房间列表"""
        if user_id in self.user_room_map:
            return list(self.user_room_map[user_id])
        return []
    
    async def process_long_message(self, user_id: str, room_id: str, content: str):
        """处理长消息，可能需要分片或特殊处理"""
        # 长消息处理示例：将长消息分片发送
        if len(content) > 1000:
            chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
            
            for i, chunk in enumerate(chunks):
                await self.publish_message(
                    user_id=user_id,
                    room_id=room_id,
                    message_type="chat_chunk",
                    content=chunk,
                    chunk_index=i,
                    total_chunks=len(chunks)
                )
            
            return True
        
        return False
    
    async def _clean_stale_connections(self, interval: int = 60):
        """定期清理长时间无活动的连接"""
        while self.processing_messages:
            try:
                # 等待间隔时间
                await asyncio.sleep(interval)
                
                stale_users = []
                
                # 检查Redis用户元数据（仅当Redis可用时）
                if self.redis_client:
                    # 获取所有用户元数据
                    all_users = await self.redis_client.keys("user:*:meta")
                    current_time = time.time()
                    
                    # 检查每个用户的最后活动时间
                    for user_key in all_users:
                        user_id = user_key.decode('utf-8').split(':')[1]
                        user_data = await self.redis_client.hgetall(user_key)
                        
                        if b'last_activity' in user_data:
                            last_activity = float(user_data[b'last_activity'])
                            node = user_data.get(b'node_id', b'unknown').decode('utf-8')
                            
                            # 仅处理当前节点上的用户
                            if node == self.node_id and current_time - last_activity > 300:  # 5分钟无活动
                                stale_users.append(user_id)
                
                # 在单机模式下，检查所有分片中的连接
                else:
                    timeout = 300  # 5分钟超时
                    current_time = time.time()
                    
                    # 为简化实现，在单机模式下我们暂不检测过期连接
                
                # 断开长时间无活动的连接
                for user_id in stale_users:
                    shard_index = self._get_shard_index(user_id)
                    if user_id in self.connection_shards[shard_index]:
                        for room_id, websocket in list(self.connection_shards[shard_index][user_id].items()):
                            logger.info(f"断开长时间无活动的连接: {user_id}/{room_id}")
                            await self.disconnect(websocket, user_id, room_id)
                
                if stale_users:
                    logger.info(f"清理完成，共断开 {len(stale_users)} 个长时间无活动的连接")
                
            except Exception as e:
                logger.error(f"清理过期连接错误: {e}")
    
    async def _health_check(self, interval: int = 30):
        """健康检查，定期检查系统状态"""
        while self.processing_messages:
            try:
                await asyncio.sleep(interval)
                
                # 检查Redis连接
                redis_ok = await self._check_redis() if self.redis_client else True
                
                # 检查消息队列大小
                queue_size = self.message_queue.qsize()
                queue_threshold = 10000  # 消息队列阈值
                queue_ok = queue_size < queue_threshold
                
                # 检查连接数量
                connections_ok = self.current_connections < self.connection_limit
                
                # 更新健康状态
                old_healthy = self.healthy
                self.healthy = redis_ok and queue_ok and connections_ok
                
                # 如果健康状态发生变化，记录日志
                if old_healthy != self.healthy:
                    if self.healthy:
                        logger.info("系统恢复健康状态")
                    else:
                        # 降低日志频率
                        if random.random() < 0.5:  # 只记录一半的状态变化
                            logger.warning(f"系统进入不健康状态: Redis={redis_ok}, 队列={queue_ok}({queue_size}/{queue_threshold}), 连接={connections_ok}({self.current_connections}/{self.connection_limit})")
                
                # 处理服务降级
                if not self.healthy and not self.is_degraded:
                    logger.warning("启动服务降级模式")
                    self.is_degraded = True
                elif self.healthy and self.is_degraded:
                    logger.info("退出服务降级模式")
                    self.is_degraded = False
                
                # 更新Redis中的节点状态
                if self.redis_client and redis_ok:
                    try:
                        # 使用超时机制
                        async def update_status():
                            await self.redis_client.hset(
                                "nodes:status",
                                self.node_id,
                                json.dumps({
                                    "healthy": self.healthy,
                                    "is_degraded": self.is_degraded,
                                    "connections": self.current_connections,
                                    "message_queue_size": queue_size,
                                    "timestamp": time.time()
                                })
                            )
                        # 设置1秒超时
                        await asyncio.wait_for(update_status(), timeout=1.0)
                    except (asyncio.TimeoutError, Exception) as e:
                        # 不记录错误，避免日志爆炸
                        pass
                
            except Exception as e:
                # 降低错误日志频率
                if random.random() < 0.1:  # 只记录10%的错误
                    logger.error(f"健康检查错误: {e}")
    
    async def _check_redis(self) -> bool:
        """检查Redis连接状态"""
        try:
            # 使用超时，避免长时间阻塞
            try:
                await asyncio.wait_for(self.redis_client.ping(), timeout=1.0)
                return True
            except asyncio.TimeoutError:
                return False
        except Exception:
            return False
    
    async def shutdown(self):
        """关闭连接管理器"""
        logger.info("关闭连接管理器...")
        
        # 停止消息处理
        self.processing_messages = False
        
        # 关闭所有WebSocket连接
        close_tasks = []
        
        for shard in self.connection_shards:
            for user_id, rooms in list(shard.items()):
                for room_id, websocket in list(rooms.items()):
                    try:
                        close_tasks.append(self.disconnect(websocket, user_id, room_id))
                    except Exception as e:
                        logger.error(f"关闭连接错误 {user_id}/{room_id}: {e}")
        
        # 等待所有连接关闭完成
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # 从Redis中移除节点信息
        if self.redis_client:
            try:
                await self.redis_client.srem("monitor:active_nodes", self.node_id)
                await self.redis_client.hdel("nodes:status", self.node_id)
            except Exception as e:
                logger.error(f"移除节点信息错误: {e}")
        
        logger.info("连接管理器已关闭")
    
    async def get_connection_stats(self) -> Dict:
        """获取连接统计信息"""
        total_connections = sum(len(users) for users in self.room_user_map.values())
        return {
            "total_connections": total_connections,
            "active_rooms": len(self.room_user_map),
            "queue_size": self.message_queue.qsize(),
            "is_degraded": self.is_degraded,
            "healthy": self.healthy,
            "node_id": self.node_id
        }
    
    async def broadcast_system_message(self, message: str) -> bool:
        """
        向所有连接的客户端广播系统消息
        
        Args:
            message: 要广播的系统消息内容
            
        Returns:
            广播是否成功
        """
        try:
            # 构建系统消息
            system_msg = {
                "type": "system",
                "content": message,
                "sender": "system",
                "timestamp": time.time()
            }
            
            # 将消息转换为JSON字符串
            message_json = json.dumps(system_msg)
            
            # 为每个活跃的聊天室创建广播任务
            broadcast_tasks = []
            for room_id in self.room_user_map:
                if self.room_user_map[room_id]:  # 确保房间中有用户
                    broadcast_tasks.append(self.broadcast_to_room(room_id, message_json))
            
            # 并行执行所有广播任务
            if broadcast_tasks:
                await asyncio.gather(*broadcast_tasks)
            
            # 如果有Redis客户端，也将消息发布到Redis
            if self.redis_client:
                try:
                    await self.redis_client.publish("chat:system", message_json)
                except Exception as e:
                    logger.error(f"发布系统消息到Redis失败: {e}")
            
            return True
        except Exception as e:
            logger.error(f"广播系统消息失败: {e}")
            return False
    
    async def _broadcast_from_redis(self, message: dict):
        """处理来自Redis的广播消息"""
        try:
            # 忽略来自自身的消息
            if message.get("source_node") == self.node_id:
                return
                
            # 获取消息类型和目标
            message_type = message.get("type")
            room_id = message.get("room_id")
            
            # 根据消息类型处理
            message_json = json.dumps(message)
            
            if message_type == "private":
                # 私信消息
                target_user = message.get("target")
                if target_user:
                    await self.send_personal_message(target_user, message_json)
            elif room_id:
                # 房间消息
                await self.broadcast_to_room(room_id, message_json)
                
        except Exception as e:
            logger.error(f"处理Redis广播消息错误: {e}")
    
    async def cleanup_expired_connections(self):
        """定期清理过期和无效的连接"""
        try:
            # 这个方法目前还没有完全实现，跳过执行
            return
            
            # 下面的代码有bug，先禁用
            inactive_timeout = 120  # 用户连接超过120秒无活动将被清理
            current_time = time.time()
            
            user_ids_to_cleanup = []
            
            for user_id, connection in list(self.active_connections.items()):
                try:
                    if not connection["websocket"] or connection["websocket"].client_state == WebSocketState.DISCONNECTED:
                        user_ids_to_cleanup.append(user_id)
                        continue
                    
                    # 检查最后活动时间
                    if current_time - connection.get("last_active", 0) > inactive_timeout:
                        # 发送Ping检查连接状态
                        try:
                            pong_waiter = await connection["websocket"].ping()
                            await asyncio.wait_for(pong_waiter, timeout=2.0)
                        except Exception:
                            # Ping失败，连接已断开
                            user_ids_to_cleanup.append(user_id)
                except Exception as e:
                    logger.warning(f"检查连接 {user_id} 状态时出错: {e}")
                    user_ids_to_cleanup.append(user_id)
            
            # 清理过期连接
            for user_id in user_ids_to_cleanup:
                await self.disconnect_user(user_id)
                
            # 清理Redis用户列表中已断开的用户
            if self.redis_client:
                try:
                    # 获取所有房间
                    room_patterns = ["room:*:users", "chat:room:*:users"]
                    room_keys = []
                    
                    for pattern in room_patterns:
                        try:
                            keys = await self.redis_client.keys(pattern)
                            room_keys.extend(keys)
                        except Exception as e:
                            logger.warning(f"获取Redis房间键模式 {pattern} 时出错: {e}")
                    
                    # 检查每个房间的在线用户
                    for room_key in room_keys:
                        try:
                            members = await self.redis_client.smembers(room_key)
                            for member in members:
                                # 处理可能的字符串或字节类型
                                user_id = member
                                if isinstance(member, bytes):
                                    try:
                                        user_id = member.decode('utf-8')
                                    except Exception:
                                        continue
                                
                                # 检查用户是否仍在活动连接中
                                if user_id not in self.active_connections:
                                    # 从Redis集合中移除
                                    await self.redis_client.srem(room_key, member)
                        except Exception as e:
                            logger.warning(f"清理房间 {room_key} 用户时出错: {e}")
                    
                except Exception as e:
                    logger.warning(f"清理Redis用户列表时出错: {e}")
        except Exception as e:
            logger.error(f"清理过期连接错误: {e}") 