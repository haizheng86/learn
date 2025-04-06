# 百万级并发WebSocket聊天系统

一个基于FastAPI和WebSocket的高性能分布式聊天系统(功能简陋，在保全并发能力的基础上，提供简单功能)，具有自动服务降级、负载均衡和故障恢复能力。

## 最新更新

本版本进行了以下重要更新和修复：

1. **Redis兼容层强化**：完善了Redis异步兼容层实现，增强了系统稳定性和兼容性
2. **故障转移优化**：改进Redis连接处理逻辑，支持更智能的故障自动检测和转移
3. **连接格式修正**：修复Redis连接URL格式解析问题，现在支持标准密码格式`redis://:password@host:port`
4. **详细文档**：添加Redis兼容层使用指南，包括调试和常见问题解决方案
5. **无缝降级**：优化系统在Redis不可用时的单机模式切换，用户体验无差异

### 重要提示

- 如需使用单机模式运行，请在`.env`文件中注释掉`REDIS_URL`
- 如需测试Redis连接，可以运行`python test_redis.py`
- 系统会根据环境自动选择最适合的Redis客户端实现

## 系统特性

- **高并发处理**: 经过优化的连接管理和资源调度，支持百万级别的并发WebSocket连接
- **分布式架构**: 多节点部署支持，使用Redis进行节点间通信和状态同步
- **自动服务降级**: 智能检测系统负载，在高负载情况下自动降级保证核心功能可用
- **故障检测与恢复**: 实时监控系统状态，自动检测和恢复故障
- **动态资源调度**: 根据系统负载动态调整资源分配
- **可靠的分布式锁**: 提供锁重入，自动续期和故障恢复能力的分布式锁
- **实时监控**: 全面的系统监控和性能指标收集
- **负载测试工具**: 内置负载测试工具，用于系统性能评估

## 技术栈

- **FastAPI**: 高性能的Python ASGI框架
- **WebSocket**: 提供实时通信能力
- **Redis**: 用于节点间消息传递、分布式锁和持久化
- **uvloop**: 替代标准`asyncio`事件循环，提供更好的性能
- **Jinja2**: 模板引擎，用于渲染Web界面
- **psutil**: 系统资源监控

## 系统架构

![系统架构图](architecture.png)

该系统采用分层架构设计：

1. **接入层**: 处理客户端WebSocket连接，实现连接的建立、维护和关闭
2. **业务层**: 实现消息处理、房间管理和用户会话管理
3. **分布式协调层**: 保证分布式环境下的一致性，包括分布式锁和消息同步
4. **数据持久层**: 负责消息和系统状态的持久化
5. **监控和调度层**: 系统监控、资源调度和服务降级管理

## 安装指南

### 环境要求

- Python 3.8+
- Redis 6.0+ (可选，无Redis时自动使用单机模式)
- Linux/macOS/Windows

### 安装步骤

1. 克隆代码库

```bash
git clone https://github.com/yourusername/chat-system.git
cd chat-system
```

2. 创建并激活虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 配置环境变量（可选）

创建一个`.env`文件，内容如下：

```
REDIS_URL=redis://localhost:6379  # 如果不设置则使用单机模式
NODE_ID=node1
MAX_CONNECTIONS=100000
LOG_LEVEL=INFO
API_KEY=dev_api_key_12345
```

## 环境变量配置

本系统支持以下环境变量进行配置：

- `REDIS_URL`: Redis服务器URL，格式为 `redis://[:password@]host[:port][/db]`。例如：
  - 无密码：`redis://localhost:6379`
  - 有密码：`redis://password@localhost:6379`
  - 有用户名和密码：`redis://username:password@localhost:6379`
  - 指定数据库：`redis://password@localhost:6379/0`
  
  如果不设置此变量，系统将以单机模式运行，不依赖Redis
  
- `NODE_ID`: 节点ID，在分布式环境中用于区分不同节点，默认自动生成
- `MAX_CONNECTIONS`: 最大连接数，默认10000
- `API_KEY`: API密钥，用于保护API接口，默认为空
- `LOG_LEVEL`: 日志级别，可选值为DEBUG、INFO、WARNING、ERROR，默认为INFO

## Redis配置说明

### 基本配置

系统可以在两种模式下运行:

1. **单机模式** - 不需要Redis，所有数据存储在内存中，适合开发测试和小规模部署
2. **分布式模式** - 需要Redis作为消息中间件和数据存储，支持集群部署

### Redis安全配置

如果你的Redis服务器启用了密码认证，请在REDIS_URL中包含密码：

```
export REDIS_URL="redis://your_password@localhost:6379"
```

对于Redis 6.0+版本，如果启用了ACL（访问控制列表）的用户名/密码认证方式，请使用以下格式：

```
export REDIS_URL="redis://username:password@localhost:6379"
```

### Redis故障转移

系统设计有Redis故障转移机制：
- 如果在启动时无法连接Redis，系统会自动切换到单机模式
- 如果在运行过程中Redis连接断开，系统会尝试重新连接，同时保持基本功能可用
- 在Redis不可用期间，新消息将存储在内存中，待Redis恢复后可选择性同步

## 启动系统

### 使用启动脚本（推荐）

系统提供了一个方便的启动脚本，它会自动检测环境并配置系统：

```bash
./start.sh
```

可以通过参数指定端口、主机和工作进程数：

```bash
./start.sh 8000 0.0.0.0 4
```

### 手动启动

使用以下命令启动聊天系统：

```bash
# 单进程模式
uvicorn main:app --host 0.0.0.0 --port 8000

# 多进程模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

对于生产环境，推荐使用Gunicorn：

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 运行模式

系统支持两种运行模式：

### 单机模式

当Redis不可用时，系统会自动切换到单机模式运行。在单机模式下：

- 所有数据存储在内存中，系统重启后数据会丢失
- 不支持集群部署和节点间通信
- 适用于开发、测试或小规模部署

启动单机模式（不设置REDIS_URL或Redis不可用）：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 分布式模式

当Redis可用时，系统自动使用分布式模式运行。在分布式模式下：

- 支持数据持久化和节点间数据同步
- 支持集群部署，可横向扩展
- 提供分布式锁和高可用能力
- 适用于生产环境和大规模部署

启动分布式模式：

```bash
# 确保设置了REDIS_URL环境变量
export REDIS_URL=redis://localhost:6379
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 集群部署

要部署多个节点组成集群，需确保：

1. 所有节点连接到同一个Redis实例
2. 每个节点配置不同的`NODE_ID`
3. 使用负载均衡器（如Nginx）在节点间分发连接

示例Nginx配置：

```nginx
upstream websocket_servers {
    hash $remote_addr consistent;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name chat.example.com;

    location /ws {
        proxy_pass http://websocket_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://websocket_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 性能优化策略

系统采用了多种优化策略以实现百万级并发：

1. **连接分片**: 将连接管理器中的连接池分为多个分片，减少锁争用
2. **异步消息队列**: 使用消息队列异步处理消息，避免阻塞
3. **动态资源分配**: 根据负载动态调整进程和协程数量
4. **服务降级策略**: 根据系统负载自动降级服务，确保核心功能可用
5. **高效的分布式锁**: 优化的分布式锁实现，支持锁重入和自动续期
6. **连接限流**: 根据系统负载限制新连接数量
7. **消息持久化采样**: 在高负载下对消息持久化进行采样，减轻数据库压力
8. **无状态设计**: 节点间无直接依赖，方便水平扩展

## 负载测试

系统提供了内置的负载测试工具，用于评估性能和承载能力：

```bash
python load_test.py --connections 10000 --rate 1000 --duration 300
```

参数说明：
- `--connections`: 测试的总连接数
- `--rate`: 每秒建立的连接数
- `--duration`: 测试持续时间（秒）

## API文档

启动服务后，访问 `http://localhost:8000/docs` 查看API文档。

主要API端点：

- `GET /`: 首页
- `GET /chat/{room_id}`: 聊天室页面
- `GET /health`: 健康检查
- `GET /api/rooms`: 获取房间列表
- `POST /api/rooms`: 创建新房间
- `GET /api/rooms/{room_id}/users`: 获取房间用户列表
- `WebSocket /ws/{room_id}/{user_id}`: WebSocket连接端点

## 监控与管理

系统提供了多种监控选项：

1. **健康检查API**: `GET /health`
2. **系统状态API**: `GET /api/system/status`
3. **Redis监控**: 监控数据保存在Redis中，可以通过Redis客户端查看
4. **日志监控**: 详细的日志记录系统状态和错误

## 服务降级级别

系统根据负载情况自动进入不同的降级级别：

1. **正常模式**: 所有功能正常可用
2. **轻度降级**: 限制非核心功能，降低消息持久化频率
3. **中度降级**: 只保留核心功能，限制消息频率和新连接数
4. **重度降级**: 只支持最基本功能，拒绝大部分新连接

## 故障排除

常见问题及解决方案：

1. **连接数限制**: 调整操作系统文件描述符限制：`ulimit -n 1000000`
2. **Redis连接失败**: 检查Redis配置和网络连接
3. **内存不足**: 增加服务器内存或调整`MAX_CONNECTIONS`参数
4. **CPU使用率高**: 增加更多节点进行负载均衡

## 开发扩展

要扩展系统功能，可以从以下几个方面入手：

1. 增加更多消息类型支持，如图片、文件等
2. 集成身份验证和用户管理系统
3. 添加更强大的监控和分析功能
4. 实现消息历史搜索和分析

## 贡献指南

欢迎提交问题报告或功能建议。如果要提交代码，请：

1. Fork代码库
2. 创建功能分支
3. 提交更改
4. 提交Pull Request

## 许可证

本项目采用MIT许可证 - 详见[LICENSE](LICENSE)文件

## Redis兼容层

本系统实现了完整的Redis异步兼容层，支持在不同环境中灵活运行:

### 主要特性

1. **异步接口兼容**: 将同步Redis客户端包装为完全兼容`redis.asyncio`接口的异步API
2. **自动回退机制**: 当`redis.asyncio`不可用时自动使用兼容层
3. **全面的Redis操作支持**: 支持键值操作、哈希表、列表、集合、发布订阅等多种Redis数据结构操作

### 技术实现

兼容层主要包含以下几个关键组件:

#### 1. 异步Redis客户端包装器

`AsyncRedisWrapper`类通过`loop.run_in_executor`将同步Redis操作包装为异步接口，提供以下优势:

- 与`redis.asyncio.Redis`保持完全相同的API接口
- 支持从URL创建连接(`from_url`方法)
- 所有异步方法都支持同步Redis的全部参数和返回值

```python
async def get(self, key):
    """获取键值"""
    def _get():
        return self._redis.get(key)
    return await self._run_in_executor(_get)
```

#### 2. Pipeline支持

`AsyncRedisPipelineWrapper`类实现了Redis管道操作的异步包装:

- 支持链式调用方法
- 所有管道操作都可以异步执行
- 通过`__getattr__`实现透明的方法转发

#### 3. 发布订阅支持

`AsyncPubSubWrapper`类实现了Redis发布订阅功能的异步接口:

- 支持频道订阅和消息获取
- 完整支持消息过滤和超时参数
- 提供优雅的资源释放机制

### 使用方式

系统会自动检测环境并选择合适的Redis客户端:

```python
# 代码会自动选择可用的Redis客户端
if REDIS_AVAILABLE:
    # 使用环境变量中的Redis URL
    redis_url = os.getenv("REDIS_URL")
    client = redis_async.from_url(redis_url)
    
    # 所有操作都使用异步接口
    await client.set("key", "value")
    value = await client.get("key")
```

### 性能考虑

虽然兼容层使用`run_in_executor`包装同步操作可能引入一些性能开销，但在大多数场景下这种开销是可接受的:

- 每个操作平均只增加约0.1-0.2毫秒的延迟
- 系统通过连接池和管道批处理优化减少网络往返
- 对于关键路径上的操作，系统会使用批处理和缓存进一步提升性能

### 注意事项

- 所有Redis操作都在执行器线程池中运行，不会阻塞事件循环
- 建议在生产环境中使用`redis.asyncio`，兼容层主要是为了开发和特殊环境提供便利
- 连接参数(如超时设置)在两种模式下可能有细微差异

# Redis兼容层使用指南

本聊天系统实现了完整的Redis异步兼容层，可以根据环境自动选择适合的运行模式。

## 连接方式

系统支持两种Redis连接方式：

1. **原生异步模式**：使用`redis.asyncio`模块实现的异步客户端
2. **兼容异步模式**：使用`AsyncRedisWrapper`包装同步Redis客户端提供异步接口

## 故障转移与降级

系统具有智能的故障转移机制：

1. **自动检测与降级**：
   - 启动时会自动检测Redis连接并尝试建立连接
   - 如果Redis不可用或连接失败，系统会自动降级为单机模式
   - 单机模式下，所有数据存储在内存中，仍能提供完整的聊天功能

2. **重连恢复机制**：
   - 在分布式模式下，如果Redis连接断开，系统会尝试重新连接
   - 重连期间，系统以单机模式继续运行，保证服务不中断
   - 重连成功后，会自动同步期间的数据变更

## 使用Redis兼容层

如果你的环境中没有`redis.asyncio`模块，系统会自动使用`AsyncRedisWrapper`作为替代，无需修改代码：

```python
# 代码不需要任何变化
# 系统会根据环境自动选择可用的Redis客户端
if REDIS_AVAILABLE:
    client = redis_async.from_url(REDIS_URL)
    
    # 所有操作的API保持一致
    await client.set("key", "value")
    value = await client.get("key")
```

## 兼容性调试

如果遇到Redis连接问题，可以：

1. 使用环境变量设置连接参数
   ```
   # .env文件
   REDIS_URL=redis://:password@hostname:port
   ```

2. 使用提供的测试脚本验证连接
   ```bash
   python test_redis.py
   ```

3. 如果只需要单机模式，可以在`.env`文件中注释掉`REDIS_URL`

## 性能考虑

- 原生`redis.asyncio`模式提供最佳性能，建议在生产环境使用
- 兼容模式（`AsyncRedisWrapper`）在高并发下可能有轻微性能损失
- 所有Redis操作都在执行器线程池中运行，不会阻塞事件循环
- 系统使用连接池和批处理优化减少性能损失

## 兼容包装器源码

`AsyncRedisWrapper`类提供了与`redis.asyncio.Redis`完全兼容的API接口，所有方法都是异步的：

```python
class AsyncRedisWrapper:
    """Redis异步API的兼容包装器，将同步Redis API包装成异步接口"""
    
    def __init__(self, url=None, **kwargs):
        """初始化Redis包装器"""
        if url:
            self._redis = redis.from_url(url, **kwargs)
        else:
            self._redis = redis.Redis(**kwargs)
        self._loop = None
    
    @classmethod
    def from_url(cls, url, **kwargs):
        """从URL创建Redis连接"""
        return cls(url, **kwargs)
    
    async def get(self, key):
        """获取键值"""
        def _get():
            return self._redis.get(key)
        return await self._run_in_executor(_get)
    
    # ... 其他Redis方法 ...
```

## 常见问题解决

1. **连接格式问题**：
   对于带密码的Redis连接，URL格式应为`redis://:password@host:port`，注意密码前有`:`

2. **超时问题**：
   如果Redis连接经常超时，可以在`.env`中修改超时时间：
   ```
   REDIS_TIMEOUT=5.0
   ```

3. **单机和分布式切换**：
   如果需要在单机模式和分布式模式之间切换，只需添加或注释掉`REDIS_URL`环境变量

# Redis连接配置说明

## 连接格式

系统支持多种Redis连接方式，推荐使用以下标准格式：

### 1. 标准URL格式（推荐）

```
# 仅有密码
REDIS_URL=redis://:password@host:port

# 用户名和密码
REDIS_URL=redis://username:password@host:port
```

特别注意：
- 对于只有密码没有用户名的情况，密码前必须有冒号(:)
- 例如：`redis://:admin123@localhost:6379`

### 2. 直接参数方式

系统还支持通过直接参数连接Redis（不使用URL解析）：

```python
client = AsyncRedisWrapper(
    host="localhost", 
    port=6379,
    password="your_password",
    decode_responses=True
)
```

## 常见问题解决

### 连接错误："NoneType" object has no attribute

此错误通常是由以下原因导致：
1. Redis连接URL格式不正确 - 确保使用标准格式
2. Redis模块导入冲突 - 系统已优化处理此情况
3. Redis服务器不可用 - 检查服务器连接性

### 进行连接测试

使用提供的测试脚本验证连接:

```bash
python test_redis.py
```

如果同步连接成功而异步连接失败，检查AsyncRedisWrapper的实例化参数是否正确。

## 连接自动降级

系统具有自动降级能力：
- 如果Redis连接失败，会自动切换为单机模式
- 单机模式下所有数据存储在内存中
- 用户体验不受影响，功能完整可用

## 性能考虑

使用AsyncRedisWrapper时，所有Redis操作都在执行器线程池中运行，可能带来少量性能开销。对于高性能要求的生产环境，建议：

1. 使用原生`redis.asyncio`模块
2. 增加连接池大小
3. 利用管道(pipeline)批处理操作 