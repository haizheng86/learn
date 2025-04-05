#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
代理池服务
代理IP池管理、验证和调度，提高爬虫系统稳定性和效率
"""

import threading
import time
import logging
import requests
import json
from datetime import datetime, timedelta
from pymongo import MongoClient, DESCENDING, ASCENDING
from bson.objectid import ObjectId

# 配置日志
logger = logging.getLogger('services.proxy')

class ProxyPoolService:
    """代理池服务，管理和调度代理IP资源"""
    
    def __init__(self, mongo_uri, db_name='proxy_db', collection_name='proxies', proxy_sources=None):
        """
        初始化代理池服务
        :param mongo_uri: MongoDB连接URI
        :param db_name: 数据库名
        :param collection_name: 代理存储集合名
        :param proxy_sources: 代理获取源列表
        """
        # 连接MongoDB
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        
        # 创建索引
        self.collection.create_index([("ip", ASCENDING), ("port", ASCENDING)], unique=True)
        self.collection.create_index([("success_rate", DESCENDING)])
        self.collection.create_index([("last_check", ASCENDING)])
        
        self.proxy_sources = proxy_sources or []
        
        # 验证网站列表
        self.validation_urls = [
            "https://www.baidu.com",
            "https://www.qq.com",
            "https://www.163.com",
        ]
        
        # 异步任务锁
        self.validate_lock = threading.Lock()
        self.fetch_lock = threading.Lock()
        
        logger.info("代理池服务初始化完成")
    
    def get_proxies(self, page=1, page_size=20, min_success_rate=0):
        """
        获取代理列表
        :param page: 页码
        :param page_size: 每页数量
        :param min_success_rate: 最低成功率过滤
        :return: (代理列表, 总数)
        """
        # 构建查询条件
        query = {}
        if min_success_rate > 0:
            query["success_rate"] = {"$gte": min_success_rate}
        
        # 计算总数
        total = self.collection.count_documents(query)
        
        # 计算偏移量
        skip = (page - 1) * page_size
        
        # 获取分页数据
        proxies = list(self.collection.find(
            query,
            {'_id': 1, 'ip': 1, 'port': 1, 'success_rate': 1, 'last_check': 1, 
             'total': 1, 'success': 1, 'failure': 1, 'first_seen': 1},
            skip=skip,
            limit=page_size,
            sort=[('success_rate', DESCENDING), ('last_check', DESCENDING)]
        ))
        
        # 将_id转为字符串
        for proxy in proxies:
            proxy['_id'] = str(proxy['_id'])
        
        return proxies, total
    
    def get_stats(self):
        """
        获取代理池统计信息
        :return: 统计信息字典
        """
        total_count = self.collection.count_documents({})
        available_count = self.collection.count_documents({"success_rate": {"$gte": 0.5}, "total": {"$gte": 3}})
        
        # 计算平均成功率
        pipeline = [
            {"$match": {"total": {"$gte": 3}}},
            {"$group": {"_id": None, "avg_success_rate": {"$avg": "$success_rate"}}}
        ]
        avg_result = list(self.collection.aggregate(pipeline))
        avg_success_rate = avg_result[0]['avg_success_rate'] if avg_result else 0
        
        # 获取最近添加的代理
        recent_proxies = list(self.collection.find(
            {},
            {'_id': 0, 'ip': 1, 'port': 1, 'success_rate': 1, 'first_seen': 1},
            sort=[('first_seen', DESCENDING)],
            limit=5
        ))
        
        # 获取最高成功率的代理
        top_proxies = list(self.collection.find(
            {"total": {"$gte": 5}},
            {'_id': 0, 'ip': 1, 'port': 1, 'success_rate': 1, 'total': 1},
            sort=[('success_rate', DESCENDING)],
            limit=5
        ))
        
        # 按来源统计
        sources_stats = []
        if 'source' in self.collection.find_one({}, {'source': 1, '_id': 0}):
            pipeline = [
                {"$group": {"_id": "$source", "count": {"$sum": 1}}}
            ]
            sources_stats = list(self.collection.aggregate(pipeline))
        
        return {
            "total": total_count,
            "available": available_count,
            "available_percent": (available_count / total_count * 100) if total_count > 0 else 0,
            "avg_success_rate": avg_success_rate,
            "recent_proxies": recent_proxies,
            "top_proxies": top_proxies,
            "sources": sources_stats
        }
    
    def validate_proxies_async(self):
        """异步验证所有代理"""
        if self.validate_lock.locked():
            logger.warning("代理验证任务已经在运行中")
            return False
            
        def validate_task():
            with self.validate_lock:
                logger.info("开始异步验证所有代理")
                proxies = list(self.collection.find({}, {"ip": 1, "port": 1, "_id": 0}))
                
                if not proxies:
                    logger.warning("代理池为空，无代理可验证")
                    return
                    
                logger.info(f"找到 {len(proxies)} 个代理待验证")
                
                # 使用线程池并发验证
                with ThreadPoolExecutor(max_workers=10) as executor:
                    for proxy in proxies:
                        executor.submit(self._validate_proxy, proxy)
                
                logger.info("代理验证完成")
        
        # 启动异步任务
        threading.Thread(target=validate_task).start()
        return True
    
    def fetch_proxies_async(self):
        """异步获取新代理"""
        if self.fetch_lock.locked():
            logger.warning("代理获取任务已经在运行中")
            return False
        
        if not self.proxy_sources:
            logger.warning("未配置代理来源")
            return False
            
        def fetch_task():
            with self.fetch_lock:
                logger.info("开始异步获取新代理")
                
                for source in self.proxy_sources:
                    try:
                        name = source.get('name', '未知来源')
                        logger.info(f"从 {name} 获取代理")
                        
                        # 构建请求头
                        headers = source.get('headers', {})
                        if 'api_key' in source and source['api_key']:
                            headers['Authorization'] = f"Bearer {source['api_key']}"
                        
                        # 发起请求
                        url = source.get('url', '')
                        if not url:
                            logger.warning(f"来源 {name} 未配置URL，跳过")
                            continue
                            
                        response = requests.get(url, headers=headers, timeout=30)
                        
                        if response.status_code != 200:
                            logger.error(f"从 {name} 获取代理失败，状态码: {response.status_code}")
                            continue
                        
                        # 解析代理
                        source_type = source.get('type', 'json')
                        if source_type == 'json':
                            proxies = self._parse_json_proxies(response.text, source.get('json_path', []))
                        else:
                            proxies = self._parse_text_proxies(response.text)
                        
                        # 添加来源信息
                        for proxy in proxies:
                            proxy['source'] = name
                        
                        # 添加到数据库
                        added = self._add_new_proxies(proxies)
                        logger.info(f"从 {name} 获取到 {len(proxies)} 个代理，成功添加 {added} 个")
                        
                    except Exception as e:
                        logger.error(f"从 {name} 获取代理出错: {str(e)}")
                
                logger.info("代理获取任务完成")
        
        # 启动异步任务
        threading.Thread(target=fetch_task).start()
        return True
    
    def _validate_proxy(self, proxy):
        """
        验证单个代理
        :param proxy: 代理字典或(ip,port)元组
        :return: 是否有效
        """
        if isinstance(proxy, dict) and 'ip' in proxy and 'port' in proxy:
            ip = proxy['ip']
            port = proxy['port']
        else:
            ip, port = self._parse_proxy(proxy)
            
        proxy_dict = {
            "http": f"http://{ip}:{port}",
            "https": f"http://{ip}:{port}"
        }
        
        # 随机选择一个验证URL
        import random
        test_url = random.choice(self.validation_urls)
        
        try:
            response = requests.get(
                test_url, 
                proxies=proxy_dict, 
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            
            if response.status_code == 200:
                self._update_proxy_status(ip, port, success=True)
                return True
            else:
                self._update_proxy_status(ip, port, success=False)
                return False
                
        except Exception as e:
            logger.debug(f"代理 {ip}:{port} 验证失败: {str(e)}")
            self._update_proxy_status(ip, port, success=False)
            return False
    
    def _update_proxy_status(self, ip, port, success=True):
        """
        更新代理状态
        :param ip: 代理IP
        :param port: 代理端口
        :param success: 是否成功
        """
        update_data = {
            "$inc": {
                "total": 1,
                "success" if success else "failure": 1
            },
            "$set": {
                "last_check": datetime.now(),
                "last_status": "success" if success else "failure"
            },
            "$setOnInsert": {
                "first_seen": datetime.now()
            }
        }
        
        # 更新文档
        self.collection.update_one(
            {"ip": ip, "port": port},
            update_data,
            upsert=True
        )
        
        # 更新成功率
        self.collection.update_one(
            {"ip": ip, "port": port},
            [
                {
                    "$set": {
                        "success_rate": {
                            "$cond": [
                                {"$eq": ["$total", 0]},
                                0,
                                {"$divide": ["$success", "$total"]}
                            ]
                        }
                    }
                }
            ]
        )
    
    def _parse_proxy(self, proxy):
        """
        从代理对象解析IP和端口
        :param proxy: 代理对象
        :return: (ip, port)
        """
        if isinstance(proxy, dict):
            if 'ip' in proxy and 'port' in proxy:
                return proxy['ip'], int(proxy['port'])
            elif 'http' in proxy:
                http_proxy = proxy['http']
                if http_proxy.startswith('http://'):
                    http_proxy = http_proxy[7:]
                ip, port = http_proxy.split(':')
                return ip, int(port)
        elif isinstance(proxy, str):
            if proxy.startswith('http://'):
                proxy = proxy[7:]
            ip, port = proxy.split(':')
            return ip, int(port)
        elif isinstance(proxy, tuple) and len(proxy) == 2:
            return proxy[0], int(proxy[1])
        
        raise ValueError(f"无法解析代理格式: {proxy}")
    
    def _parse_json_proxies(self, data, json_path=None):
        """
        解析JSON格式的代理数据
        :param data: JSON字符串
        :param json_path: JSON路径，指定代理数组位置
        :return: 代理列表
        """
        try:
            # 解析JSON
            json_data = json.loads(data)
            
            # 如果指定了JSON路径，则按路径获取代理数组
            if json_path:
                current = json_data
                for key in json_path:
                    if key in current:
                        current = current[key]
                    else:
                        logger.warning(f"JSON路径错误: {key} 不存在")
                        return []
                
                proxies_data = current
            else:
                # 否则假设JSON本身是代理数组
                proxies_data = json_data
            
            # 解析代理
            proxies = []
            if isinstance(proxies_data, list):
                for item in proxies_data:
                    if isinstance(item, dict):
                        # 尝试多种常见的字段名称
                        ip = item.get('ip') or item.get('host') or item.get('addr')
                        port = item.get('port')
                        
                        if ip and port:
                            proxies.append({'ip': ip, 'port': int(port)})
                    elif isinstance(item, str):
                        # 尝试解析 ip:port 格式
                        try:
                            ip, port = item.split(':')
                            proxies.append({'ip': ip, 'port': int(port)})
                        except:
                            logger.warning(f"无法解析代理字符串: {item}")
            
            return proxies
            
        except Exception as e:
            logger.error(f"解析JSON代理数据失败: {str(e)}")
            return []
    
    def _parse_text_proxies(self, text):
        """
        解析文本格式的代理数据
        :param text: 文本数据
        :return: 代理列表
        """
        proxies = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
                
            # 尝试解析 ip:port 格式
            try:
                if ':' in line:
                    ip, port = line.split(':', 1)
                    ip = ip.strip()
                    port = int(port.strip())
                    proxies.append({'ip': ip, 'port': port})
            except:
                logger.warning(f"无法解析代理文本行: {line}")
                
        return proxies
    
    def _add_new_proxies(self, proxies):
        """
        添加新代理到数据库
        :param proxies: 代理列表
        :return: 添加成功的数量
        """
        added = 0
        for proxy in proxies:
            if 'ip' in proxy and 'port' in proxy:
                try:
                    # 使用upsert确保不重复
                    result = self.collection.update_one(
                        {"ip": proxy['ip'], "port": proxy['port']},
                        {
                            "$setOnInsert": {
                                "first_seen": datetime.now(),
                                "success": 0,
                                "failure": 0,
                                "total": 0,
                                "success_rate": 0,
                                "last_check": datetime.now(),
                                "source": proxy.get('source', '未知来源')
                            }
                        },
                        upsert=True
                    )
                    
                    if result.upserted_id:
                        added += 1
                except Exception as e:
                    logger.error(f"添加代理 {proxy['ip']}:{proxy['port']} 失败: {str(e)}")
        
        return added
    
    def clean_proxies(self, min_success_rate=0.1, max_age_days=7):
        """
        清理低质量代理
        :param min_success_rate: 最低成功率
        :param max_age_days: 最大保留天数
        :return: 清理结果
        """
        # 计算截止时间
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # 清理条件
        query = {
            "$or": [
                # 低成功率且请求次数足够多
                {"success_rate": {"$lt": min_success_rate}, "total": {"$gte": 3}},
                # 长时间未验证的代理
                {"last_check": {"$lt": cutoff_date}}
            ]
        }
        
        # 获取要删除的代理数量
        to_delete = self.collection.count_documents(query)
        
        # 执行删除
        result = self.collection.delete_many(query)
        
        logger.info(f"清理了 {result.deleted_count} 个低质量代理")
        
        return {
            "cleaned": result.deleted_count,
            "planned": to_delete,
            "remaining": self.collection.count_documents({})
        }
    
    def delete_proxy(self, proxy_id):
        """
        删除指定代理
        :param proxy_id: 代理ID
        :return: 是否成功
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(proxy_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"删除代理 {proxy_id} 失败: {str(e)}")
            return False
    
    def verify_proxy(self, proxy):
        """
        验证指定代理
        :param proxy: 代理字符串(ip:port)或字典
        :return: 是否有效
        """
        return self._validate_proxy(proxy)
    
    def export_proxies(self, min_success_rate=0.7, limit=100):
        """
        导出高质量代理
        :param min_success_rate: 最低成功率
        :param limit: 最大数量
        :return: 代理列表
        """
        proxies = list(self.collection.find(
            {"success_rate": {"$gte": min_success_rate}, "total": {"$gte": 3}},
            {'_id': 0, 'ip': 1, 'port': 1, 'success_rate': 1, 'total': 1},
            sort=[('success_rate', DESCENDING)],
            limit=limit
        ))
        
        # 格式化为字符串格式
        formatted_proxies = [
            {
                "address": f"{p['ip']}:{p['port']}",
                "http": f"http://{p['ip']}:{p['port']}",
                "https": f"http://{p['ip']}:{p['port']}",
                "success_rate": p['success_rate'],
                "total_requests": p.get('total', 0)
            }
            for p in proxies
        ]
        
        return formatted_proxies
    
    def add_proxy(self, proxy_data, validate=True):
        """
        手动添加代理
        :param proxy_data: 代理数据
        :param validate: 是否验证
        :return: 添加结果
        """
        if not isinstance(proxy_data, dict) or 'ip' not in proxy_data or 'port' not in proxy_data:
            raise ValueError("代理数据格式错误，应包含ip和port字段")
            
        # 标准化数据
        ip = proxy_data['ip'].strip()
        port = int(proxy_data['port'])
        
        # 可选额外数据
        source = proxy_data.get('source', '手动添加')
        
        # 添加到数据库
        result = self.collection.update_one(
            {"ip": ip, "port": port},
            {
                "$setOnInsert": {
                    "first_seen": datetime.now(),
                    "success": 0,
                    "failure": 0,
                    "total": 0,
                    "success_rate": 0,
                    "last_check": datetime.now(),
                    "source": source
                }
            },
            upsert=True
        )
        
        # 验证代理
        is_valid = False
        if validate:
            is_valid = self._validate_proxy({"ip": ip, "port": port})
        
        return {
            "ip": ip,
            "port": port,
            "added": result.upserted_id is not None,
            "valid": is_valid,
        } 