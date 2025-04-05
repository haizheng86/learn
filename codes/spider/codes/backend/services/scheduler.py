import uuid
import time
import logging
import redis
from datetime import datetime, timedelta
from pymongo import MongoClient
import pymongo

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, mongo_uri, redis_url, crawler_service):
        """初始化调度服务"""
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client.crawler_db
        self.schedules = self.db.schedules
        self.redis = redis.from_url(redis_url)
        self.crawler_service = crawler_service
        
        # 创建索引
        self.schedules.create_index([('schedule_id', pymongo.ASCENDING)], unique=True)
        self.schedules.create_index([('spider_id', pymongo.ASCENDING)])
        self.schedules.create_index([('next_run', pymongo.ASCENDING)])
        
        # 启动调度器
        self.start_scheduler()
        
    def start_scheduler(self):
        """启动调度器"""
        import threading
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("调度器线程已启动")
        
    def _scheduler_loop(self):
        """调度器主循环"""
        while True:
            try:
                self._check_scheduled_tasks()
            except Exception as e:
                logger.error(f"调度器检查任务出错: {str(e)}")
            
            # 每分钟检查一次
            time.sleep(60)
            
    def _check_scheduled_tasks(self):
        """检查并执行计划任务"""
        now = datetime.now()
        
        # 查找所有到期的调度
        due_schedules = list(self.schedules.find({
            'next_run': {'$lte': now},
            'enabled': True
        }))
        
        if due_schedules:
            logger.info(f"发现 {len(due_schedules)} 个需要执行的计划任务")
        
        for schedule in due_schedules:
            try:
                # 启动爬虫
                spider_id = schedule['spider_id']
                self.crawler_service.start_spider(
                    spider_id,
                    concurrent_requests=schedule.get('concurrent_requests'),
                    use_proxy=schedule.get('use_proxy', True)
                )
                
                # 更新下次运行时间
                next_run = self._calculate_next_run(schedule)
                
                self.schedules.update_one(
                    {'schedule_id': schedule['schedule_id']},
                    {
                        '$set': {
                            'next_run': next_run,
                            'last_run': now
                        },
                        '$inc': {'run_count': 1}
                    }
                )
                
                logger.info(f"已调度爬虫 {spider_id}, 下次运行时间: {next_run}")
            except Exception as e:
                logger.error(f"执行调度 {schedule['schedule_id']} 失败: {str(e)}")
                
    def _calculate_next_run(self, schedule):
        """计算下次运行时间"""
        now = datetime.now()
        schedule_type = schedule.get('schedule_type', 'once')
        
        if schedule_type == 'once':
            # 一次性任务不再运行
            return None
            
        elif schedule_type == 'interval':
            # 间隔执行
            interval_unit = schedule.get('interval_unit', 'hours')
            interval_value = schedule.get('interval_value', 24)
            
            if interval_unit == 'minutes':
                return now + timedelta(minutes=interval_value)
            elif interval_unit == 'hours':
                return now + timedelta(hours=interval_value)
            elif interval_unit == 'days':
                return now + timedelta(days=interval_value)
            elif interval_unit == 'weeks':
                return now + timedelta(weeks=interval_value)
                
        elif schedule_type == 'cron':
            # 暂不实现复杂的cron调度
            # 这里可以集成第三方库如APScheduler进行cron解析
            pass
            
        # 默认24小时后
        return now + timedelta(hours=24)
        
    def create_schedule(self, spider_id, schedule_data):
        """创建新调度计划"""
        # 获取爬虫信息
        spider = self.crawler_service.get_spider(spider_id)
        if not spider:
            return None, "爬虫不存在"
            
        # 生成调度ID
        schedule_id = str(uuid.uuid4())
        
        # 计算首次运行时间
        first_run = schedule_data.get('first_run')
        if not first_run:
            # 如果没有指定首次运行时间，默认为当前时间
            first_run = datetime.now()
            
        # 预处理调度数据
        now = datetime.now()
        schedule_data.update({
            'schedule_id': schedule_id,
            'spider_id': spider_id,
            'created_at': now,
            'updated_at': now,
            'next_run': first_run,
            'last_run': None,
            'run_count': 0,
            'enabled': schedule_data.get('enabled', True)
        })
        
        # 保存到数据库
        self.schedules.insert_one(schedule_data)
        
        return schedule_data, None
        
    def get_schedules(self, spider_id=None, page=1, page_size=20):
        """获取调度计划列表"""
        skip = (page - 1) * page_size
        
        # 查询条件
        query = {}
        if spider_id:
            query['spider_id'] = spider_id
            
        # 查询调度计划
        schedules = list(self.schedules.find(
            query
        ).sort('next_run', pymongo.ASCENDING)
         .skip(skip)
         .limit(page_size))
        
        # 获取总数
        total = self.schedules.count_documents(query)
        
        return schedules, total
        
    def update_schedule(self, schedule_id, update_data):
        """更新调度计划"""
        # 不允许更新的字段
        protected_fields = ['schedule_id', 'spider_id', 'created_at', 'run_count', 'last_run']
        
        # 移除保护字段
        for field in protected_fields:
            if field in update_data:
                del update_data[field]
                
        # 更新时间
        update_data['updated_at'] = datetime.now()
        
        # 更新调度计划
        result = self.schedules.update_one(
            {'schedule_id': schedule_id},
            {'$set': update_data}
        )
        
        return result.modified_count > 0
        
    def delete_schedule(self, schedule_id):
        """删除调度计划"""
        result = self.schedules.delete_one({'schedule_id': schedule_id})
        return result.deleted_count > 0
        
    def enable_schedule(self, schedule_id, enabled=True):
        """启用或禁用调度计划"""
        result = self.schedules.update_one(
            {'schedule_id': schedule_id},
            {
                '$set': {
                    'enabled': enabled,
                    'updated_at': datetime.now()
                }
            }
        )
        
        return result.modified_count > 0 