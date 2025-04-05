#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
智能代理IP池
用于管理、验证和调度代理IP资源，提高爬虫系统稳定性和效率
"""

import time
import random
import requests
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('proxy_pool')

class ProxyPool:
    """代理IP池管理器"""
    
    def __init__(self, mongo_uri, db_name='proxy_db', collection_name='proxies', proxy_sources=None):
        """
        初始化代理池
        :param mongo_uri: MongoDB连接URI
        :param db_name: 数据库名称
        :param collection_name: 存储代理的集合名称
        :param proxy_sources: 代理获取源列表
        """
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        
        # 创建索引
        self.collection.create_index([("last_check", ASCENDING)])
        self.collection.create_index([("success_rate", DESCENDING)])
        self.collection.create_index([("ip", ASCENDING), ("port", ASCENDING)], unique=True)
        
        self.proxy_sources = proxy_sources or []
        self.logger = logger
        
        # 验证网站列表
        self.validation_urls = [
            "https://www.baidu.com",
            "https://www.qq.com",
            "https://www.163.com",
        ]
    
    def get_proxy(self, min_success_rate=0.7, min_requests=3):
        """
        获取一个可用代理
        :param min_success_rate: 最低成功率要求
        :param min_requests: 最低请求次数要求，避免成功率样本太少
        :return: 代理字典或None
        """
        # 先尝试获取高质量代理
        proxy_doc = self.collection.find_one(
            {
                "success_rate": {"$gte": min_success_rate},
                "total": {"$gte": min_requests}
            },
            sort=[("success_rate", DESCENDING), ("last_check", DESCENDING)]
        )
        
        # 如果没有高质量代理，降低要求再次尝试
        if not proxy_doc:
            self.logger.warning("无符合条件的高质量代理，尝试获取任一可用代理")
            proxy_doc = self.collection.find_one(
                {"total": {"$gte": 1}},
                sort=[("success_rate", DESCENDING), ("last_check", DESCENDING)]
            )
        
        # 仍然没有可用代理，返回任何代理
        if not proxy_doc:
            self.logger.error("代理池中无可用代理！")
            # 尝试获取新代理
            self.fetch_new_proxies()
            proxy_doc = self.collection.find_one()
        
        if not proxy_doc:
            return None
            
        # 构造代理格式
        return {
            "http": f"http://{proxy_doc['ip']}:{proxy_doc['port']}",
            "https": f"http://{proxy_doc['ip']}:{proxy_doc['port']}",
            "meta": {
                "success_rate": proxy_doc.get('success_rate', 0),
                "total_requests": proxy_doc.get('total', 0)
            }
        }
    
    def update_proxy_status(self, proxy, success=True):
        """
        更新代理状态
        :param proxy: 代理字典或IP:端口元组
        :param success: 是否成功
        """
        ip, port = self._parse_proxy(proxy)
        
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
        
        if success:
            log_msg = f"代理 {ip}:{port} 请求成功"
        else:
            log_msg = f"代理 {ip}:{port} 请求失败"
        
        self.logger.debug(log_msg)
    
    def _parse_proxy(self, proxy):
        """
        从代理字典或字符串中解析IP和端口
        :param proxy: 代理字典、字符串或(ip,port)元组
        :return: (ip, port)
        """
        if isinstance(proxy, dict):
            http_proxy = proxy.get("http", "")
            if http_proxy.startswith("http://"):
                http_proxy = http_proxy[7:]
            ip, port = http_proxy.split(":")
            return ip, int(port)
        elif isinstance(proxy, tuple) and len(proxy) == 2:
            return proxy[0], int(proxy[1])
        elif isinstance(proxy, str):
            if proxy.startswith("http://"):
                proxy = proxy[7:]
            ip, port = proxy.split(":")
            return ip, int(port)
        else:
            raise ValueError(f"无法解析代理格式: {proxy}")
    
    def validate_all_proxies(self, max_workers=20):
        """
        验证所有代理的可用性
        :param max_workers: 最大线程数
        """
        self.logger.info("开始验证所有代理...")
        proxies = list(self.collection.find({}, {"ip": 1, "port": 1, "_id": 0}))
        
        if not proxies:
            self.logger.warning("代理池为空，无代理可验证")
            return
            
        self.logger.info(f"找到 {len(proxies)} 个代理待验证")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for proxy in proxies:
                executor.submit(self._validate_proxy, proxy)
        
        self.logger.info("代理验证完成")
        
        # 统计当前代理池状态
        total = self.collection.count_documents({})
        available = self.collection.count_documents({"success_rate": {"$gte": 0.5}, "total": {"$gte": 3}})
        self.logger.info(f"代理池状态: 总计 {total} 个代理，可用 {available} 个")
    
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
                self.update_proxy_status(proxy_dict, success=True)
                return True
            else:
                self.update_proxy_status(proxy_dict, success=False)
                return False
                
        except Exception as e:
            self.logger.debug(f"代理 {ip}:{port} 验证失败: {str(e)}")
            self.update_proxy_status(proxy_dict, success=False)
            return False
    
    def fetch_new_proxies(self):
        """从配置的来源获取新代理"""
        self.logger.info("开始获取新代理...")
        total_added = 0
        
        for source in self.proxy_sources:
            try:
                self.logger.debug(f"从 {source['name']} 获取代理")
                
                # 调用API获取代理
                if 'api_key' in source:
                    headers = source.get('headers', {})
                    headers['Authorization'] = f"Bearer {source['api_key']}"
                else:
                    headers = source.get('headers', {})
                
                response = requests.get(
                    source['url'], 
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    # 根据source中配置的解析方法处理响应
                    parser = source.get('parser')
                    if parser == 'json':
                        data = response.json()
                        proxies = self._parse_json_proxies(data, source.get('json_path', []))
                    elif parser == 'text':
                        proxies = self._parse_text_proxies(response.text)
                    elif callable(parser):
                        proxies = parser(response.text)
                    else:
                        self.logger.error(f"未知的解析器类型: {parser}")
                        continue
                    
                    added = self._add_new_proxies(proxies)
                    total_added += added
                    self.logger.info(f"从 {source['name']} 添加了 {added} 个新代理")
                else:
                    self.logger.error(f"从 {source['name']} 获取代理失败: HTTP {response.status_code}")
                    
            except Exception as e:
                self.logger.error(f"从 {source['name']} 获取代理出错: {str(e)}")
        
        self.logger.info(f"获取新代理完成，共添加 {total_added} 个")
        
        # 如果有新代理，立即验证
        if total_added > 0:
            # 只验证新增的代理
            new_proxies = list(self.collection.find(
                {"total": 0},
                {"ip": 1, "port": 1, "_id": 0}
            ))
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                for proxy in new_proxies:
                    executor.submit(self._validate_proxy, proxy)
            
            self.logger.info(f"完成 {len(new_proxies)} 个新代理的验证")
    
    def _parse_json_proxies(self, data, json_path):
        """
        解析JSON格式的代理数据
        :param data: JSON数据
        :param json_path: 访问代理数据的路径列表
        :return: 代理列表
        """
        result = []
        
        # 根据路径获取代理列表
        proxy_data = data
        for key in json_path:
            if key in proxy_data:
                proxy_data = proxy_data[key]
            else:
                self.logger.error(f"无法在JSON数据中找到路径: {json_path}")
                return []
        
        # 如果不是列表，则返回空
        if not isinstance(proxy_data, list):
            self.logger.error(f"解析后的数据不是列表: {type(proxy_data)}")
            return []
        
        # 尝试从列表中提取IP和端口
        for item in proxy_data:
            try:
                if isinstance(item, dict):
                    # 常见的字段名格式
                    ip_fields = ['ip', 'IP', 'ipAddress', 'host']
                    port_fields = ['port', 'PORT', 'portNumber']
                    
                    ip = None
                    port = None
                    
                    # 查找IP字段
                    for field in ip_fields:
                        if field in item:
                            ip = item[field]
                            break
                    
                    # 查找端口字段
                    for field in port_fields:
                        if field in item:
                            port = int(item[field])
                            break
                    
                    if ip and port:
                        result.append({'ip': ip, 'port': port})
                    else:
                        # 可能有特殊格式，比如合并在一个字段中
                        for field, value in item.items():
                            if isinstance(value, str) and ':' in value:
                                parts = value.split(':')
                                if len(parts) == 2 and parts[0] and parts[1].isdigit():
                                    result.append({'ip': parts[0], 'port': int(parts[1])})
                                    break
                elif isinstance(item, str) and ':' in item:
                    # 字符串格式 "ip:port"
                    ip, port = item.split(':')
                    if ip and port.isdigit():
                        result.append({'ip': ip, 'port': int(port)})
            except Exception as e:
                self.logger.error(f"解析代理项时出错: {str(e)}, 数据: {item}")
        
        return result
    
    def _parse_text_proxies(self, text):
        """
        解析文本格式的代理数据，通常是每行一个 "ip:port"
        :param text: 文本数据
        :return: 代理列表
        """
        result = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                try:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        ip = parts[0]
                        port = parts[1]
                        # 可能有协议前缀或后缀，只取端口数字部分
                        port = ''.join(c for c in port if c.isdigit())
                        if ip and port.isdigit():
                            result.append({'ip': ip, 'port': int(port)})
                except Exception as e:
                    self.logger.error(f"解析代理行时出错: {str(e)}, 数据: {line}")
        
        return result
    
    def _add_new_proxies(self, proxies):
        """
        添加新代理到数据库
        :param proxies: 代理列表，每个代理是包含ip和port字段的字典
        :return: 添加的代理数量
        """
        if not proxies:
            return 0
            
        added_count = 0
        for proxy in proxies:
            if 'ip' in proxy and 'port' in proxy:
                try:
                    # 使用upsert避免重复，但只在不存在时设置初始值
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
                                "last_status": "new"
                            }
                        },
                        upsert=True
                    )
                    
                    if result.upserted_id:
                        added_count += 1
                except Exception as e:
                    self.logger.error(f"添加代理 {proxy['ip']}:{proxy['port']} 时出错: {str(e)}")
        
        return added_count
    
    def clean_proxies(self, min_success_rate=0.1, max_age_days=7):
        """
        清理低质量和过期的代理
        :param min_success_rate: 最低成功率
        :param max_age_days: 最大保留天数
        """
        self.logger.info("开始清理代理池...")
        
        # 删除成功率过低的代理
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # 查找低质量代理: 请求次数足够多且成功率低于阈值
        result = self.collection.delete_many({
            "total": {"$gte": 5},
            "success_rate": {"$lt": min_success_rate}
        })
        
        self.logger.info(f"删除了 {result.deleted_count} 个低质量代理")
        
        # 查找过期代理: 最后检查时间超过指定天数
        result = self.collection.delete_many({
            "last_check": {"$lt": cutoff_date}
        })
        
        self.logger.info(f"删除了 {result.deleted_count} 个过期代理")
    
    def get_stats(self):
        """获取代理池统计信息"""
        total = self.collection.count_documents({})
        available = self.collection.count_documents({"success_rate": {"$gte": 0.5}, "total": {"$gte": 3}})
        
        high_quality = self.collection.count_documents({
            "success_rate": {"$gte": 0.8}, 
            "total": {"$gte": 5}
        })
        
        medium_quality = self.collection.count_documents({
            "success_rate": {"$gte": 0.5, "$lt": 0.8}, 
            "total": {"$gte": 3}
        })
        
        low_quality = self.collection.count_documents({
            "success_rate": {"$lt": 0.5}, 
            "total": {"$gte": 3}
        })
        
        untested = self.collection.count_documents({"total": 0})
        
        # 获取部分代理示例
        samples = list(self.collection.find(
            {"success_rate": {"$gte": 0.8}, "total": {"$gte": 5}},
            {"ip": 1, "port": 1, "success_rate": 1, "total": 1, "_id": 0}
        ).sort("success_rate", DESCENDING).limit(5))
        
        return {
            "total": total,
            "available": available,
            "high_quality": high_quality,
            "medium_quality": medium_quality,
            "low_quality": low_quality,
            "untested": untested,
            "samples": samples
        }
        
    def export_proxies(self, min_success_rate=0.7, limit=100):
        """
        导出高质量代理列表
        :param min_success_rate: 最低成功率
        :param limit: 最大数量
        :return: 代理列表
        """
        proxies = list(self.collection.find(
            {"success_rate": {"$gte": min_success_rate}, "total": {"$gte": 3}},
            {"ip": 1, "port": 1, "success_rate": 1, "_id": 0}
        ).sort("success_rate", DESCENDING).limit(limit))
        
        return [f"{p['ip']}:{p['port']}" for p in proxies]


# 测试代码
if __name__ == "__main__":
    # 配置参数
    mongo_uri = "mongodb://localhost:27017/"
    
    # 代理源示例
    proxy_sources = [
        {
            "name": "ProxyListPlus",
            "url": "https://list.proxylistplus.com/Fresh-HTTP-Proxy-List-1",
            "parser": "text"
        }
    ]
    
    # 创建代理池
    pool = ProxyPool(mongo_uri, proxy_sources=proxy_sources)
    
    # 测试获取新代理
    pool.fetch_new_proxies()
    
    # 验证代理
    pool.validate_all_proxies()
    
    # 获取并使用代理
    proxy = pool.get_proxy()
    print(f"获取到代理: {proxy}")
    
    # 更新代理状态（模拟请求成功）
    if proxy:
        pool.update_proxy_status(proxy, success=True)
    
    # 显示统计信息
    stats = pool.get_stats()
    print(json.dumps(stats, indent=2, default=str))
    
    # 导出高质量代理
    good_proxies = pool.export_proxies(min_success_rate=0.7, limit=10)
    print(f"高质量代理列表: {good_proxies}")
    
    # 清理低质量代理
    pool.clean_proxies() 