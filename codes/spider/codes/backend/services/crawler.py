#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫服务
提供爬虫任务的创建、管理、调度和监控功能
"""

import json
import time
import uuid
import redis
import logging
from datetime import datetime
from pymongo import MongoClient, DESCENDING
from kubernetes import client, config
import json

# 配置日志
logger = logging.getLogger('services.crawler')

class CrawlerService:
    """爬虫服务，管理爬虫任务的生命周期"""
    
    def __init__(self, redis_url, mongo_uri, kubernetes_enabled=False, 
                 kubernetes_namespace='default', crawler_image=None):
        """
        初始化爬虫服务
        :param redis_url: Redis连接URL，用于任务队列和分布式调度
        :param mongo_uri: MongoDB连接URI，用于存储爬虫配置和数据
        :param kubernetes_enabled: 是否启用Kubernetes部署
        :param kubernetes_namespace: Kubernetes命名空间
        :param crawler_image: 爬虫容器镜像地址
        """
        # 连接Redis
        self.redis = redis.from_url(redis_url)
        
        # 连接MongoDB
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client.crawler_db
        self.spiders_collection = self.db.spiders
        self.spider_stats_collection = self.db.spider_stats
        
        # Kubernetes配置
        self.kubernetes_enabled = kubernetes_enabled
        self.kubernetes_namespace = kubernetes_namespace
        self.crawler_image = crawler_image
        
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
    
    def get_all_spiders(self):
        """
        获取所有爬虫信息
        :return: 爬虫列表
        """
        spiders = list(self.spiders_collection.find({}, {'_id': 0}))
        
        # 对每个爬虫添加运行状态信息
        for spider in spiders:
            spider_id = spider['spider_id']
            spider['status'] = self._get_spider_status(spider_id)
            spider['queue_size'] = self._get_queue_size(spider_id)
            
        return spiders
    
    def get_spider(self, spider_id):
        """
        获取指定爬虫信息
        :param spider_id: 爬虫ID
        :return: 爬虫信息字典
        """
        spider = self.spiders_collection.find_one({'spider_id': spider_id}, {'_id': 0})
        
        if spider:
            # 添加运行状态信息
            spider['status'] = self._get_spider_status(spider_id)
            spider['queue_size'] = self._get_queue_size(spider_id)
            
            # 获取最新统计数据
            latest_stats = self.spider_stats_collection.find_one(
                {'spider_id': spider_id},
                sort=[('timestamp', DESCENDING)]
            )
            
            if latest_stats:
                spider['latest_stats'] = {
                    'items_scraped': latest_stats.get('items_scraped', 0),
                    'requests_count': latest_stats.get('requests_count', 0),
                    'request_errors': latest_stats.get('request_errors', 0),
                    'response_time_avg': latest_stats.get('response_time_avg', 0),
                    'timestamp': latest_stats.get('timestamp', datetime.now())
                }
            
        return spider
    
    def create_spider(self, spider_data):
        """
        创建新爬虫
        :param spider_data: 爬虫配置数据
        :return: 创建的爬虫信息
        """
        # 生成唯一爬虫ID
        spider_id = str(uuid.uuid4())
        
        # 补充默认值和元数据
        spider = {
            'spider_id': spider_id,
            'name': spider_data.get('name', ''),
            'description': spider_data.get('description', ''),
            'start_urls': spider_data.get('start_urls', []),
            'domain': spider_data.get('domain', ''),
            'allowed_domains': spider_data.get('allowed_domains', []),
            'follow_links': spider_data.get('follow_links', True),
            'max_depth': spider_data.get('max_depth', 5),
            'concurrent_requests': spider_data.get('concurrent_requests', 16),
            'download_delay': spider_data.get('download_delay', 0.5),
            'item_pipelines': spider_data.get('item_pipelines', {}),
            'use_proxy': spider_data.get('use_proxy', True),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'status': 'idle',
            'custom_settings': spider_data.get('custom_settings', {}),
            'selectors': spider_data.get('selectors', {}),
            'created_by': spider_data.get('created_by', 'system')
        }
        
        # 存储到MongoDB
        self.spiders_collection.insert_one(spider)
        
        # 不返回MongoDB的_id字段
        spider.pop('_id', None)
        
        logger.info(f"爬虫 {spider_id} 创建成功")
        return spider
    
    def start_spider(self, spider_id, concurrent_requests=None, use_proxy=None):
        """
        启动爬虫
        :param spider_id: 爬虫ID
        :param concurrent_requests: 并发请求数
        :param use_proxy: 是否使用代理
        :return: 操作结果
        """
        # 检查爬虫是否存在
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            logger.warning(f"爬虫 {spider_id} 不存在")
            return None
            
        # 检查爬虫是否已在运行
        if self._get_spider_status(spider_id) == 'running':
            logger.warning(f"爬虫 {spider_id} 已经在运行中")
            return None
        
        # 更新配置
        update_data = {'status': 'running', 'updated_at': datetime.now()}
        if concurrent_requests is not None:
            update_data['concurrent_requests'] = concurrent_requests
        if use_proxy is not None:
            update_data['use_proxy'] = use_proxy
            
        self.spiders_collection.update_one(
            {'spider_id': spider_id},
            {'$set': update_data}
        )
        
        # 将起始URL添加到Redis队列
        start_urls = spider.get('start_urls', [])
        for url in start_urls:
            self._add_url_to_queue(spider_id, url, 0)  # 0表示深度为0的起始URL
        
        # 如果启用了Kubernetes，则创建或扩展爬虫部署
        if self.kubernetes_enabled:
            replicas = 1  # 可以从配置中获取初始副本数
            self._deploy_spider_to_kubernetes(spider_id, replicas)
            
        logger.info(f"爬虫 {spider_id} 启动成功")
        return {'spider_id': spider_id, 'status': 'running'}
    
    def stop_spider(self, spider_id):
        """
        停止爬虫
        :param spider_id: 爬虫ID
        :return: 操作结果
        """
        # 检查爬虫是否存在
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            logger.warning(f"爬虫 {spider_id} 不存在")
            return None
            
        # 更新状态
        self.spiders_collection.update_one(
            {'spider_id': spider_id},
            {'$set': {'status': 'stopped', 'updated_at': datetime.now()}}
        )
        
        # 如果启用了Kubernetes，则缩减爬虫部署
        if self.kubernetes_enabled:
            try:
                self._scale_spider_deployment(spider_id, 0)
            except Exception as e:
                logger.error(f"缩减爬虫 {spider_id} 部署失败: {str(e)}")
        
        logger.info(f"爬虫 {spider_id} 停止成功")
        return {'spider_id': spider_id, 'status': 'stopped'}
    
    def pause_spider(self, spider_id):
        """
        暂停爬虫
        :param spider_id: 爬虫ID
        :return: 操作结果
        """
        # 检查爬虫是否存在并正在运行
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider or self._get_spider_status(spider_id) != 'running':
            logger.warning(f"爬虫 {spider_id} 不存在或未运行")
            return None
            
        # 更新状态
        self.spiders_collection.update_one(
            {'spider_id': spider_id},
            {'$set': {'status': 'paused', 'updated_at': datetime.now()}}
        )
        
        # 如果启用了Kubernetes，暂时不处理副本数，以保留当前状态
        
        logger.info(f"爬虫 {spider_id} 暂停成功")
        return {'spider_id': spider_id, 'status': 'paused'}
    
    def resume_spider(self, spider_id):
        """
        恢复暂停的爬虫
        :param spider_id: 爬虫ID
        :return: 操作结果
        """
        # 检查爬虫是否存在并已暂停
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider or spider.get('status') != 'paused':
            logger.warning(f"爬虫 {spider_id} 不存在或未暂停")
            return None
            
        # 更新状态
        self.spiders_collection.update_one(
            {'spider_id': spider_id},
            {'$set': {'status': 'running', 'updated_at': datetime.now()}}
        )
        
        logger.info(f"爬虫 {spider_id} 恢复成功")
        return {'spider_id': spider_id, 'status': 'running'}
    
    def delete_spider(self, spider_id):
        """
        删除爬虫
        :param spider_id: 爬虫ID
        :return: 操作结果
        """
        # 检查爬虫是否存在
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            logger.warning(f"爬虫 {spider_id} 不存在")
            return None
        
        # 如果爬虫正在运行，先停止它
        if self._get_spider_status(spider_id) == 'running':
            self.stop_spider(spider_id)
        
        # 清空爬虫队列
        self.clear_queue(spider_id)
        
        # 从数据库中删除爬虫配置
        self.spiders_collection.delete_one({'spider_id': spider_id})
        
        # 如果启用了Kubernetes，删除爬虫部署
        if self.kubernetes_enabled:
            try:
                self._delete_spider_deployment(spider_id)
            except Exception as e:
                logger.error(f"删除爬虫 {spider_id} 部署失败: {str(e)}")
        
        logger.info(f"爬虫 {spider_id} 删除成功")
        return {'spider_id': spider_id, 'status': 'deleted'}
    
    def get_spider_stats(self, spider_id, history_hours=24):
        """
        获取爬虫统计信息
        :param spider_id: 爬虫ID
        :param history_hours: 获取历史多少小时的统计数据
        :return: 统计信息
        """
        # 检查爬虫是否存在
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            logger.warning(f"爬虫 {spider_id} 不存在")
            return None
        
        # 获取最新统计数据
        latest_stats = self.spider_stats_collection.find_one(
            {'spider_id': spider_id},
            sort=[('timestamp', DESCENDING)]
        )
        
        # 获取历史统计数据
        cutoff_time = datetime.now() - time.timedelta(hours=history_hours)
        history_stats = list(self.spider_stats_collection.find(
            {'spider_id': spider_id, 'timestamp': {'$gte': cutoff_time}},
            sort=[('timestamp', DESCENDING)]
        ))
        
        # 处理统计数据显示
        if latest_stats:
            result = {
                'current': {
                    'items_scraped': latest_stats.get('items_scraped', 0),
                    'requests_count': latest_stats.get('requests_count', 0),
                    'request_errors': latest_stats.get('request_errors', 0),
                    'response_time_avg': latest_stats.get('response_time_avg', 0),
                    'memory_usage': latest_stats.get('memory_usage', 0),
                    'cpu_usage': latest_stats.get('cpu_usage', 0),
                    'timestamp': latest_stats.get('timestamp', datetime.now())
                },
                'history': [
                    {
                        'items_scraped': s.get('items_scraped', 0),
                        'requests_count': s.get('requests_count', 0),
                        'request_errors': s.get('request_errors', 0),
                        'response_time_avg': s.get('response_time_avg', 0),
                        'timestamp': s.get('timestamp', datetime.now())
                    } for s in history_stats
                ],
                'status': self._get_spider_status(spider_id),
                'queue_size': self._get_queue_size(spider_id)
            }
            return result
        else:
            return {
                'current': {},
                'history': [],
                'status': self._get_spider_status(spider_id),
                'queue_size': self._get_queue_size(spider_id)
            }
    
    def get_spider_items(self, spider_id, page=1, page_size=20):
        """
        获取爬虫采集的数据项
        :param spider_id: 爬虫ID
        :param page: 页码
        :param page_size: 每页数量
        :return: (数据项列表, 总数)
        """
        # 数据库中存储的集合名是爬虫ID
        items_collection = self.db[f"items_{spider_id}"]
        
        # 计算总数
        total = items_collection.count_documents({})
        
        # 计算偏移量
        skip = (page - 1) * page_size
        
        # 获取分页数据
        items = list(items_collection.find(
            {}, 
            {'_id': 0},
            skip=skip,
            limit=page_size,
            sort=[('crawled_at', DESCENDING)]
        ))
        
        return items, total
    
    def clear_queue(self, spider_id):
        """
        清空爬虫队列
        :param spider_id: 爬虫ID
        :return: 清空结果
        """
        # Redis队列键
        queue_key = f"queue:{spider_id}"
        
        # 检查队列是否存在
        if not self.redis.exists(queue_key):
            logger.warning(f"爬虫 {spider_id} 队列不存在")
            return False
        
        # 清空队列
        self.redis.delete(queue_key)
        
        # 清空去重集合
        dupefilter_key = f"dupefilter:{spider_id}"
        if self.redis.exists(dupefilter_key):
            self.redis.delete(dupefilter_key)
        
        logger.info(f"爬虫 {spider_id} 队列已清空")
        return True
    
    def scale_spider(self, spider_id, replicas):
        """
        扩缩容爬虫实例数量
        :param spider_id: 爬虫ID
        :param replicas: 副本数
        :return: 操作结果
        """
        # 检查是否启用Kubernetes
        if not self.kubernetes_enabled:
            logger.warning("未启用Kubernetes，无法扩缩容爬虫")
            return None
        
        # 检查爬虫是否存在
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            logger.warning(f"爬虫 {spider_id} 不存在")
            return None
        
        # 尝试扩缩容
        try:
            result = self._scale_spider_deployment(spider_id, replicas)
            logger.info(f"爬虫 {spider_id} 已扩缩为 {replicas} 个实例")
            return {'spider_id': spider_id, 'replicas': replicas}
        except Exception as e:
            logger.error(f"扩缩容爬虫 {spider_id} 失败: {str(e)}")
            return None
    
    def _get_spider_status(self, spider_id):
        """
        获取爬虫运行状态
        :param spider_id: 爬虫ID
        :return: 状态字符串
        """
        # 从数据库获取状态
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            return 'not_found'
        
        # 返回存储的状态
        return spider.get('status', 'unknown')
    
    def _get_queue_size(self, spider_id):
        """
        获取爬虫队列大小
        :param spider_id: 爬虫ID
        :return: 队列大小
        """
        # Redis队列键
        queue_key = f"queue:{spider_id}"
        
        # 如果队列不存在则返回0
        if not self.redis.exists(queue_key):
            return 0
        
        # 获取列表长度
        return self.redis.llen(queue_key)
    
    def _add_url_to_queue(self, spider_id, url, depth=0):
        """
        将URL添加到爬虫队列
        :param spider_id: 爬虫ID
        :param url: 要添加的URL
        :param depth: URL深度
        """
        # Redis队列键
        queue_key = f"queue:{spider_id}"
        
        # 创建请求项
        request_item = json.dumps({
            'url': url,
            'depth': depth,
            'dont_filter': False
        })
        
        # 添加到队列
        self.redis.rpush(queue_key, request_item)
    
    def _deploy_spider_to_kubernetes(self, spider_id, replicas=1):
        """
        将爬虫部署到Kubernetes
        :param spider_id: 爬虫ID
        :param replicas: 副本数
        """
        if not self.kubernetes_enabled:
            logger.warning("未启用Kubernetes，无法部署爬虫")
            return
        
        # 检查是否已存在部署
        try:
            self.k8s_apps_api.read_namespaced_deployment(
                name=f"crawler-{spider_id}",
                namespace=self.kubernetes_namespace
            )
            # 如果存在，则只需扩缩容
            self._scale_spider_deployment(spider_id, replicas)
            return
        except client.exceptions.ApiException as e:
            if e.status != 404:  # 404表示不存在，这是正常的
                logger.error(f"检查爬虫部署失败: {str(e)}")
                raise e
        
        # 获取爬虫配置
        spider = self.spiders_collection.find_one({'spider_id': spider_id})
        if not spider:
            logger.error(f"爬虫 {spider_id} 不存在，无法部署")
            return
        
        # 创建部署配置
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name=f"crawler-{spider_id}",
                labels={"app": "crawler", "spider-id": spider_id}
            ),
            spec=client.V1DeploymentSpec(
                replicas=replicas,
                selector=client.V1LabelSelector(
                    match_labels={"app": "crawler", "spider-id": spider_id}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={"app": "crawler", "spider-id": spider_id}
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="crawler",
                                image=self.crawler_image,
                                args=["crawl", "generic_spider", 
                                      "--set", f"SPIDER_ID={spider_id}"],
                                env=[
                                    client.V1EnvVar(
                                        name="REDIS_URL",
                                        value="redis://redis-master:6379/0"
                                    ),
                                    client.V1EnvVar(
                                        name="MONGO_URI",
                                        value="mongodb://mongodb:27017/crawler_db"
                                    ),
                                    client.V1EnvVar(
                                        name="CONCURRENT_REQUESTS",
                                        value=str(spider.get('concurrent_requests', 16))
                                    ),
                                    client.V1EnvVar(
                                        name="USE_PROXY",
                                        value=str(spider.get('use_proxy', True)).lower()
                                    )
                                ],
                                resources=client.V1ResourceRequirements(
                                    requests={"cpu": "100m", "memory": "256Mi"},
                                    limits={"cpu": "500m", "memory": "512Mi"}
                                )
                            )
                        ]
                    )
                )
            )
        )
        
        # 创建部署
        try:
            self.k8s_apps_api.create_namespaced_deployment(
                namespace=self.kubernetes_namespace,
                body=deployment
            )
            logger.info(f"爬虫 {spider_id} 部署成功")
        except Exception as e:
            logger.error(f"部署爬虫 {spider_id} 失败: {str(e)}")
            raise e
    
    def _scale_spider_deployment(self, spider_id, replicas):
        """
        扩缩爬虫部署
        :param spider_id: 爬虫ID
        :param replicas: 副本数
        """
        if not self.kubernetes_enabled:
            logger.warning("未启用Kubernetes，无法扩缩容爬虫")
            return
        
        try:
            # 获取当前部署
            deployment = self.k8s_apps_api.read_namespaced_deployment(
                name=f"crawler-{spider_id}",
                namespace=self.kubernetes_namespace
            )
            
            # 更新副本数
            deployment.spec.replicas = replicas
            
            # 应用更新
            self.k8s_apps_api.patch_namespaced_deployment(
                name=f"crawler-{spider_id}",
                namespace=self.kubernetes_namespace,
                body=deployment
            )
            
            logger.info(f"爬虫 {spider_id} 扩缩为 {replicas} 个实例")
            return True
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.warning(f"爬虫 {spider_id} 部署不存在")
                return False
            logger.error(f"扩缩爬虫 {spider_id} 失败: {str(e)}")
            raise e
    
    def _delete_spider_deployment(self, spider_id):
        """
        删除爬虫部署
        :param spider_id: 爬虫ID
        """
        if not self.kubernetes_enabled:
            logger.warning("未启用Kubernetes，无法删除爬虫部署")
            return
        
        try:
            # 删除部署
            self.k8s_apps_api.delete_namespaced_deployment(
                name=f"crawler-{spider_id}",
                namespace=self.kubernetes_namespace
            )
            
            logger.info(f"爬虫 {spider_id} 部署已删除")
            return True
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.warning(f"爬虫 {spider_id} 部署不存在")
                return True
            logger.error(f"删除爬虫 {spider_id} 部署失败: {str(e)}")
            raise e 