#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
监控服务
提供系统各项指标的收集、统计和分析
"""

import time
import logging
import redis
import json
import csv
import io
from datetime import datetime, timedelta
from pymongo import MongoClient, DESCENDING, ASCENDING

# 配置日志
logger = logging.getLogger('services.monitor')

class MonitorService:
    """监控服务，提供系统指标监控和分析"""
    
    def __init__(self, redis_url, mongo_uri):
        """
        初始化监控服务
        :param redis_url: Redis连接URL，用于任务队列和实时指标
        :param mongo_uri: MongoDB连接URI，用于存储监控数据
        """
        # 连接Redis
        self.redis = redis.from_url(redis_url)
        
        # 连接MongoDB
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client.crawler_db
        self.stats_collection = self.db.system_stats
        self.daily_stats_collection = self.db.daily_stats
        self.error_stats_collection = self.db.error_stats
        
        # 创建索引
        self.stats_collection.create_index([("timestamp", DESCENDING)])
        self.daily_stats_collection.create_index([("date", DESCENDING)])
        self.error_stats_collection.create_index([("timestamp", DESCENDING)])
        self.error_stats_collection.create_index([("error_type", ASCENDING)])
        
        logger.info("监控服务初始化完成")
    
    def get_summary_stats(self):
        """
        获取系统概要统计信息
        :return: 统计信息字典
        """
        # 获取爬虫数量
        spider_count = self.db.spiders.count_documents({})
        
        # 获取队列状态
        queue_stats = self.get_queue_stats()
        
        # 获取活跃爬虫数
        active_spiders = self.db.spiders.count_documents({"status": "running"})
        
        # 获取今日爬取数据量
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_stats = self.daily_stats_collection.find_one({"date": today})
        today_items = today_stats.get("items_scraped", 0) if today_stats else 0
        
        # 获取总数据量
        total_items = sum(self.db[coll].count_documents({}) for coll in self.db.list_collection_names() if coll.startswith("items_"))
        
        # 获取最近的错误数量
        yesterday = today - timedelta(days=1)
        recent_errors = self.error_stats_collection.count_documents({"timestamp": {"$gte": yesterday}})
        
        # 获取系统性能指标
        latest_stats = self.stats_collection.find_one(sort=[("timestamp", DESCENDING)])
        system_load = latest_stats.get("system_load", [0, 0, 0]) if latest_stats else [0, 0, 0]
        memory_usage = latest_stats.get("memory_usage", 0) if latest_stats else 0
        
        return {
            "spiders": {
                "total": spider_count,
                "active": active_spiders
            },
            "queues": queue_stats,
            "data": {
                "today_items": today_items,
                "total_items": total_items
            },
            "system": {
                "load": system_load,
                "memory_usage": memory_usage,
                "recent_errors": recent_errors
            }
        }
    
    def get_daily_stats(self, days=30):
        """
        获取每日统计数据
        :param days: 获取最近多少天的数据
        :return: 每日统计数据列表
        """
        # 计算起始日期
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)
        
        # 查询数据
        daily_stats = list(self.daily_stats_collection.find(
            {"date": {"$gte": start_date}},
            {"_id": 0},
            sort=[("date", ASCENDING)]
        ))
        
        # 确保数据连续
        result = []
        current_date = start_date
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        while current_date < end_date:
            # 查找当前日期的数据
            day_data = next((item for item in daily_stats if item["date"].day == current_date.day and 
                             item["date"].month == current_date.month and 
                             item["date"].year == current_date.year), None)
            
            if day_data:
                result.append(day_data)
            else:
                # 如果没有数据，则添加空数据
                result.append({
                    "date": current_date,
                    "items_scraped": 0,
                    "requests_count": 0,
                    "request_errors": 0,
                    "domains_count": 0,
                    "spiders_count": 0
                })
            
            current_date += timedelta(days=1)
        
        return result
    
    def get_performance_stats(self, hours=24):
        """
        获取系统性能统计
        :param hours: 获取最近多少小时的数据
        :return: 性能统计数据列表
        """
        # 计算起始时间
        start_time = datetime.now() - timedelta(hours=hours)
        
        # 查询数据
        performance_stats = list(self.stats_collection.find(
            {"timestamp": {"$gte": start_time}},
            {"_id": 0, "timestamp": 1, "system_load": 1, "memory_usage": 1, 
             "cpu_usage": 1, "disk_usage": 1, "network_io": 1, "request_rate": 1},
            sort=[("timestamp", ASCENDING)]
        ))
        
        # 按小时间隔采样
        result = []
        hour_groups = {}
        
        for stat in performance_stats:
            # 按小时分组
            hour_key = stat["timestamp"].replace(minute=0, second=0, microsecond=0)
            if hour_key not in hour_groups:
                hour_groups[hour_key] = []
            hour_groups[hour_key].append(stat)
        
        # 计算每小时平均值
        for hour, stats in hour_groups.items():
            if not stats:
                continue
                
            avg_stat = {
                "timestamp": hour,
                "system_load": sum(s.get("system_load", [0, 0, 0])[0] for s in stats) / len(stats),
                "memory_usage": sum(s.get("memory_usage", 0) for s in stats) / len(stats),
                "cpu_usage": sum(s.get("cpu_usage", 0) for s in stats) / len(stats),
                "disk_usage": sum(s.get("disk_usage", 0) for s in stats) / len(stats) if "disk_usage" in stats[0] else 0,
                "network_io": {
                    "in": sum(s.get("network_io", {}).get("in", 0) for s in stats) / len(stats) if "network_io" in stats[0] else 0,
                    "out": sum(s.get("network_io", {}).get("out", 0) for s in stats) / len(stats) if "network_io" in stats[0] else 0
                },
                "request_rate": sum(s.get("request_rate", 0) for s in stats) / len(stats)
            }
            result.append(avg_stat)
        
        # 按时间排序
        result.sort(key=lambda x: x["timestamp"])
        
        return result
    
    def get_domain_stats(self, days=30, limit=10):
        """
        获取按域名统计的数据量
        :param days: 获取最近多少天的数据
        :param limit: 返回前多少个域名
        :return: 域名统计数据
        """
        # 计算起始时间
        start_time = datetime.now() - timedelta(days=days)
        
        # 获取所有爬虫ID
        spider_domains = {}
        spiders = list(self.db.spiders.find({}, {"spider_id": 1, "domain": 1}))
        for spider in spiders:
            if "domain" in spider:
                spider_domains[spider["spider_id"]] = spider["domain"]
        
        # 统计每个域名的数据量
        domain_stats = {}
        
        # 遍历所有爬虫的数据集合
        for spider_id, domain in spider_domains.items():
            collection_name = f"items_{spider_id}"
            if collection_name in self.db.list_collection_names():
                count = self.db[collection_name].count_documents({
                    "crawled_at": {"$gte": start_time}
                })
                
                if domain not in domain_stats:
                    domain_stats[domain] = 0
                domain_stats[domain] += count
        
        # 转换为列表并排序
        result = [{"domain": domain, "count": count} for domain, count in domain_stats.items()]
        result.sort(key=lambda x: x["count"], reverse=True)
        
        # 限制返回数量
        return result[:limit]
    
    def get_error_stats(self, days=7, limit=20):
        """
        获取错误统计
        :param days: 获取最近多少天的数据
        :param limit: 返回前多少个错误类型
        :return: 错误统计数据
        """
        # 计算起始时间
        start_time = datetime.now() - timedelta(days=days)
        
        # 按错误类型聚合
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_time}}},
            {"$group": {
                "_id": "$error_type",
                "count": {"$sum": 1},
                "latest": {"$max": "$timestamp"},
                "examples": {"$push": {
                    "url": "$url", 
                    "message": "$message", 
                    "spider_id": "$spider_id",
                    "timestamp": "$timestamp"
                }}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit},
            {"$project": {
                "error_type": "$_id",
                "count": 1,
                "latest": 1,
                "examples": {"$slice": ["$examples", 3]}  # 只保留3个示例
            }}
        ]
        
        error_stats = list(self.error_stats_collection.aggregate(pipeline))
        
        # 处理 _id 字段
        for stat in error_stats:
            stat["error_type"] = stat.pop("_id")
        
        return error_stats
    
    def get_prometheus_metrics(self):
        """
        获取Prometheus监控指标信息
        :return: 监控指标信息
        """
        # 这里假设Prometheus指标已经在另一个服务中收集和存储
        # 我们只需访问Redis中存储的最新指标
        metrics_key = "prometheus:metrics:latest"
        metrics_data = self.redis.get(metrics_key)
        
        if metrics_data:
            try:
                return json.loads(metrics_data)
            except:
                logger.error("解析Prometheus指标数据失败")
        
        # 如果没有数据，返回空字典
        return {}
    
    def get_queue_stats(self):
        """
        获取队列统计信息
        :return: 队列统计信息
        """
        result = {
            "total_queues": 0,
            "total_requests": 0,
            "queues": []
        }
        
        # 获取所有爬虫队列的键
        queue_keys = self.redis.keys("queue:*")
        result["total_queues"] = len(queue_keys)
        
        # 获取每个队列的大小
        for key in queue_keys:
            queue_size = self.redis.llen(key)
            result["total_requests"] += queue_size
            
            # 解析爬虫ID
            spider_id = key.decode('utf-8').split(':')[1] if isinstance(key, bytes) else key.split(':')[1]
            
            # 获取爬虫名称
            spider = self.db.spiders.find_one({"spider_id": spider_id}, {"name": 1, "_id": 0})
            spider_name = spider["name"] if spider and "name" in spider else "未知爬虫"
            
            result["queues"].append({
                "queue_key": key.decode('utf-8') if isinstance(key, bytes) else key,
                "spider_id": spider_id,
                "spider_name": spider_name,
                "size": queue_size
            })
        
        # 按队列大小排序
        result["queues"].sort(key=lambda x: x["size"], reverse=True)
        
        return result
    
    def get_storage_stats(self):
        """
        获取存储统计信息
        :return: 存储统计信息
        """
        result = {
            "collections": [],
            "total_size_mb": 0,
            "total_documents": 0
        }
        
        # 获取所有集合的统计信息
        for collection_name in self.db.list_collection_names():
            # 忽略系统集合
            if collection_name.startswith("system."):
                continue
                
            # 获取集合统计信息
            stats = self.db.command("collStats", collection_name)
            
            # 提取关键信息
            collection_stats = {
                "name": collection_name,
                "size_mb": stats.get("size", 0) / (1024 * 1024),
                "document_count": stats.get("count", 0),
                "avg_document_size_bytes": stats.get("avgObjSize", 0) if stats.get("count", 0) > 0 else 0
            }
            
            result["collections"].append(collection_stats)
            result["total_size_mb"] += collection_stats["size_mb"]
            result["total_documents"] += collection_stats["document_count"]
        
        # 按大小排序
        result["collections"].sort(key=lambda x: x["size_mb"], reverse=True)
        
        # 获取MongoDB服务器信息
        try:
            server_status = self.mongo_client.admin.command("serverStatus")
            result["server"] = {
                "version": server_status.get("version", "未知"),
                "uptime_days": server_status.get("uptime", 0) / (60 * 60 * 24),
                "connections": server_status.get("connections", {}).get("current", 0)
            }
        except:
            result["server"] = {"version": "未知", "uptime_days": 0, "connections": 0}
        
        return result
    
    def export_stats(self, days=30, format_type="json"):
        """
        导出统计数据
        :param days: 导出最近多少天的数据
        :param format_type: 导出格式 (json 或 csv)
        :return: 导出的数据
        """
        # 获取每日统计数据
        daily_stats = self.get_daily_stats(days)
        
        if format_type == "json":
            return daily_stats
        elif format_type == "csv":
            # 创建CSV内存流
            output = io.StringIO()
            
            # 确定字段列表
            if daily_stats:
                fieldnames = list(daily_stats[0].keys())
            else:
                fieldnames = ["date", "items_scraped", "requests_count", "request_errors", "domains_count", "spiders_count"]
            
            # 创建CSV写入器
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            # 格式化日期字段并写入数据
            for stat in daily_stats:
                # 将日期对象转换为字符串
                if "date" in stat and isinstance(stat["date"], datetime):
                    stat["date"] = stat["date"].strftime("%Y-%m-%d")
                writer.writerow(stat)
            
            # 获取CSV内容
            csv_data = output.getvalue()
            output.close()
            
            return csv_data
        else:
            raise ValueError(f"不支持的导出格式: {format_type}")
            
    def record_system_stats(self, stats_data):
        """
        记录系统统计数据
        :param stats_data: 统计数据字典
        :return: 是否成功
        """
        # 添加时间戳
        if "timestamp" not in stats_data:
            stats_data["timestamp"] = datetime.now()
            
        try:
            # 写入数据库
            self.stats_collection.insert_one(stats_data)
            return True
        except Exception as e:
            logger.error(f"记录系统统计数据失败: {str(e)}")
            return False
            
    def record_error(self, error_data):
        """
        记录错误信息
        :param error_data: 错误数据字典
        :return: 是否成功
        """
        # 添加时间戳
        if "timestamp" not in error_data:
            error_data["timestamp"] = datetime.now()
            
        try:
            # 写入数据库
            self.error_stats_collection.insert_one(error_data)
            return True
        except Exception as e:
            logger.error(f"记录错误信息失败: {str(e)}")
            return False
            
    def update_daily_stats(self, date=None):
        """
        更新每日统计数据
        :param date: 要更新的日期，默认为今天
        :return: 是否成功
        """
        if date is None:
            date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            # 计算今日爬取数据量
            items_scraped = 0
            for coll in self.db.list_collection_names():
                if coll.startswith("items_"):
                    items_scraped += self.db[coll].count_documents({
                        "crawled_at": {"$gte": date, "$lt": date + timedelta(days=1)}
                    })
            
            # 计算请求次数和错误数
            requests_count = self.stats_collection.count_documents({
                "timestamp": {"$gte": date, "$lt": date + timedelta(days=1)}
            })
            
            request_errors = self.error_stats_collection.count_documents({
                "timestamp": {"$gte": date, "$lt": date + timedelta(days=1)}
            })
            
            # 计算活跃域名数和爬虫数
            active_spiders = self.db.spiders.count_documents({
                "updated_at": {"$gte": date, "$lt": date + timedelta(days=1)}
            })
            
            domains = set()
            for spider in self.db.spiders.find({"updated_at": {"$gte": date, "$lt": date + timedelta(days=1)}}):
                if "domain" in spider:
                    domains.add(spider["domain"])
            
            # 更新或创建每日统计记录
            self.daily_stats_collection.update_one(
                {"date": date},
                {
                    "$set": {
                        "items_scraped": items_scraped,
                        "requests_count": requests_count,
                        "request_errors": request_errors,
                        "domains_count": len(domains),
                        "spiders_count": active_spiders,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
            
            return True
        except Exception as e:
            logger.error(f"更新每日统计数据失败: {str(e)}")
            return False 