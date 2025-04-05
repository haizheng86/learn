# 分布式爬虫系统管理平台

这是一个基于Scrapy-Redis、Flask和MongoDB的分布式爬虫管理平台，用于构建、部署和监控百万级数据采集任务。(代码没有前端代码，只有后端服务)

## 功能特点

- **分布式架构**：基于Scrapy-Redis实现的分布式爬虫系统
- **弹性扩展**：支持Kubernetes部署，实现爬虫节点弹性伸缩
- **高效URL去重**：使用布隆过滤器实现高效大规模URL去重
- **智能代理池**：自动管理和评估代理IP质量
- **实时监控**：集成Prometheus监控，提供关键性能指标
- **Web管理界面**：可视化管理爬虫任务和系统状态
- **用户权限管理**：完整的用户注册、认证和权限控制
- **定时任务调度**：灵活的爬虫任务定时和周期性执行
- **统一管理控制台**：集中化的系统资源和性能监控

## 系统要求

- Python 3.9+
- Docker 20.10+
- Kubernetes 1.22+ (可选，用于生产环境部署)
- Redis 6.0+
- MongoDB 4.4+
- Node.js 14+ (用于前端开发)

## 快速开始

### 本地开发环境

1. 克隆仓库
```bash
git clone https://github.com/yourusername/crawler-platform.git
cd crawler-platform
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 启动Redis和MongoDB
```bash
docker-compose up -d redis mongodb
```

4. 启动Web管理平台
```bash
cd backend
python app.py
```

5. 在新终端启动前端开发服务器
```bash
cd frontend
npm install
npm run serve
```

6. 访问管理界面: http://localhost:8080

### 使用Docker Compose

1. 使用Docker Compose启动完整环境
```bash
docker-compose up -d
```

2. 访问管理界面: http://localhost:8080

### Kubernetes部署

请参考 `k8s/` 目录下的部署配置文件和说明。

## 项目结构

```
crawler-platform/
├── backend/                 # 后端Flask应用
│   ├── app.py               # 应用入口
│   ├── api/                 # API接口
│   │   ├── crawler.py       # 爬虫控制接口
│   │   ├── proxies.py       # 代理管理接口
│   │   ├── scheduler.py     # 调度管理接口
│   │   ├── spiders.py       # 爬虫定义接口
│   │   ├── stats.py         # 统计数据接口
│   │   ├── system.py        # 系统管理接口
│   │   └── user.py          # 用户管理接口
│   ├── services/            # 业务逻辑
│   │   ├── crawler.py       # 爬虫服务
│   │   ├── monitor.py       # 监控服务
│   │   ├── proxy.py         # 代理池服务
│   │   ├── scheduler.py     # 调度服务
│   │   ├── system.py        # 系统服务
│   │   └── user.py          # 用户服务
│   ├── models/              # 数据模型
│   │   ├── schedule.py      # 调度模型
│   │   ├── user.py          # 用户模型
│   │   └── proxy.py         # 代理模型
│   ├── utils/               # 工具函数
│   │   ├── auth.py          # 认证工具
│   │   ├── response.py      # 响应格式化
│   │   └── validators.py    # 数据验证
│   └── config.py            # 配置文件
├── crawler/                 # Scrapy爬虫项目
│   ├── spiders/             # 爬虫定义
│   ├── middlewares.py       # 爬虫中间件
│   ├── pipelines.py         # 数据处理管道
│   └── settings.py          # 爬虫配置
├── bloom_filter.py          # 布隆过滤器实现
├── proxy_pool.py            # 代理池核心实现
├── frontend/                # Vue.js前端项目
├── k8s/                     # Kubernetes配置
│   ├── crawler.yaml         # 爬虫部署配置
│   ├── redis.yaml           # Redis配置
│   └── mongodb.yaml         # MongoDB配置
└── docker-compose.yml       # 容器编排配置
```

## 配置说明

### 环境变量配置

系统支持通过环境变量进行配置：

- `REDIS_HOST`：Redis主机地址
- `REDIS_PORT`：Redis端口
- `REDIS_PASSWORD`：Redis密码
- `MONGO_HOST`：MongoDB主机地址
- `MONGO_PORT`：MongoDB端口
- `MONGO_USER`：MongoDB用户名
- `MONGO_PASSWORD`：MongoDB密码
- `MONGO_DB`：MongoDB数据库名
- `SECRET_KEY`：JWT加密密钥
- `PROMETHEUS_PORT`：Prometheus指标暴露端口
- `FLASK_DEBUG`：Flask调试模式

### 爬虫配置

在 `crawler/settings.py` 中可以配置以下选项：

- `REDIS_URL`: Redis连接URL
- `MONGO_URI`: MongoDB连接URI
- `CONCURRENT_REQUESTS`: 并发请求数
- `DOWNLOAD_DELAY`: 下载延迟
- `RETRY_TIMES`: 重试次数

### 代理池配置

在 `crawler/settings.py` 中配置代理池选项：

- `PROXY_POOL_ENABLED`: 是否启用代理池
- `PROXY_POOL_MONGO_URI`: 代理池数据库连接URI
- `PROXY_POOL_COLLECTION`: 代理集合名
- `PROXY_MIN_SUCCESS_RATE`: 最低可用代理成功率

## API文档

Web管理平台提供以下主要API：

### 爬虫管理
- `GET /api/spiders`: 获取所有爬虫信息
- `GET /api/spiders/<spider_id>`: 获取指定爬虫信息
- `POST /api/spiders`: 创建新爬虫任务
- `POST /api/spiders/<spider_id>/start`: 启动爬虫
- `POST /api/spiders/<spider_id>/stop`: 停止爬虫

### 代理管理
- `GET /api/proxies`: 获取代理IP池状态
- `POST /api/proxies`: 添加新代理
- `POST /api/proxies/validate`: 验证所有代理
- `GET /api/proxies/stats`: 获取代理统计信息

### 用户管理
- `POST /api/users/register`: 用户注册
- `POST /api/users/login`: 用户登录
- `GET /api/users/profile`: 获取当前用户信息
- `PUT /api/users/profile`: 更新用户信息
- `PUT /api/users/password`: 修改密码

### 任务调度
- `GET /api/schedules`: 获取调度计划列表
- `POST /api/schedules`: 创建新调度计划
- `PUT /api/schedules/<schedule_id>`: 更新调度计划
- `DELETE /api/schedules/<schedule_id>`: 删除调度计划
- `POST /api/schedules/<schedule_id>/enable`: 启用调度计划
- `POST /api/schedules/<schedule_id>/disable`: 禁用调度计划

### 系统管理
- `GET /api/stats`: 获取系统统计信息
- `GET /api/system/info`: 获取系统基本信息
- `GET /api/system/status`: 获取系统运行状态

## 监控指标

系统集成了Prometheus监控，提供以下关键指标：

- `crawler_requests_total`: 请求总数
- `crawler_response_time_seconds`: 响应时间
- `crawler_items_scraped_total`: 采集数据总量
- `crawler_queue_size`: 队列大小
- `crawler_proxy_success_total`: 代理成功次数
- `crawler_proxy_failure_total`: 代理失败次数

## 性能优化

1. **布隆过滤器优化URL去重**
   - 内存占用比Redis SET低10倍以上
   - 处理亿级URL时效果明显

2. **异步数据写入**
   - 采用Kafka缓冲，异步批量写入数据库
   - 减轻数据库压力

3. **智能代理调度**
   - 基于成功率智能选择代理
   - 定期验证代理可用性

4. **分布式任务调度**
   - 基于Redis实现的分布式锁
   - 支持横向扩展调度器

5. **模块化设计**
   - 松耦合的服务架构
   - 支持按需扩展各组件

## 常见问题

**Q: 系统支持的最大并发量是多少？**

A: 默认配置下单个爬虫节点支持16个并发请求，集群可通过增加节点数实现线性扩展。十个节点可稳定支持160个并发请求。单个后端API服务可支持约2000-3000并发请求。

**Q: 如何管理代理IP资源？**

A: 系统支持多种代理来源，包括付费API和自建代理池。可通过添加解析器支持各种代理格式。代理池自动评估代理质量并选择最优代理。

**Q: 数据量大时如何优化存储？**

A: 对于超大规模数据，建议配置MongoDB分片集群，并使用Kafka作为数据缓冲层，实现批量写入。

**Q: 如何扩展系统支持更多类型的爬虫？**

A: 系统采用插件式设计，可以通过实现标准接口添加新类型的爬虫。只需在crawler/spiders/目录添加新的爬虫类，并在Web界面中注册即可。

**Q: 如何保证系统安全性？**

A: 系统实现了完整的用户认证和权限管理，所有API接口都需要JWT令牌验证。此外，可以启用IP白名单和请求频率限制来增强安全性。

## 问题反馈

如有问题或建议，请在GitHub Issues中提出，或发送邮件至：your-email@example.com

## 许可证

MIT 