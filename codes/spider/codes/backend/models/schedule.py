import uuid
from datetime import datetime, timedelta

class Schedule:
    """调度计划模型"""
    
    def __init__(self, spider_id, schedule_type='once', interval_value=None, interval_unit=None,
                 first_run=None, next_run=None, last_run=None, enabled=True, schedule_id=None,
                 created_at=None, updated_at=None, run_count=0, params=None):
        """初始化调度计划模型"""
        self.schedule_id = schedule_id or str(uuid.uuid4())
        self.spider_id = spider_id
        self.schedule_type = schedule_type
        self.interval_value = interval_value
        self.interval_unit = interval_unit
        self.first_run = first_run or datetime.now()
        self.next_run = next_run or self.first_run
        self.last_run = last_run
        self.enabled = enabled
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.run_count = run_count
        self.params = params or {}
    
    def calculate_next_run(self):
        """计算下次运行时间"""
        if self.schedule_type == 'once':
            # 一次性任务不再运行
            return None
            
        elif self.schedule_type == 'interval':
            # 间隔执行
            now = datetime.now()
            
            if not self.interval_value or not self.interval_unit:
                # 默认24小时
                return now + timedelta(hours=24)
                
            if self.interval_unit == 'minutes':
                return now + timedelta(minutes=self.interval_value)
            elif self.interval_unit == 'hours':
                return now + timedelta(hours=self.interval_value)
            elif self.interval_unit == 'days':
                return now + timedelta(days=self.interval_value)
            elif self.interval_unit == 'weeks':
                return now + timedelta(weeks=self.interval_value)
                
        # 默认24小时后
        return datetime.now() + timedelta(hours=24)
    
    def record_run(self):
        """记录执行结果"""
        now = datetime.now()
        self.last_run = now
        self.run_count += 1
        self.next_run = self.calculate_next_run()
        self.updated_at = now
        return self
    
    def to_dict(self):
        """转换为字典表示"""
        return {
            'schedule_id': self.schedule_id,
            'spider_id': self.spider_id,
            'schedule_type': self.schedule_type,
            'interval_value': self.interval_value,
            'interval_unit': self.interval_unit,
            'first_run': self.first_run,
            'next_run': self.next_run,
            'last_run': self.last_run,
            'enabled': self.enabled,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'run_count': self.run_count,
            'params': self.params
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建调度计划对象"""
        return cls(
            spider_id=data.get('spider_id'),
            schedule_type=data.get('schedule_type', 'once'),
            interval_value=data.get('interval_value'),
            interval_unit=data.get('interval_unit'),
            first_run=data.get('first_run'),
            next_run=data.get('next_run'),
            last_run=data.get('last_run'),
            enabled=data.get('enabled', True),
            schedule_id=data.get('schedule_id'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            run_count=data.get('run_count', 0),
            params=data.get('params', {})
        )
    
    def is_due(self, now=None):
        """检查是否到期"""
        if not self.enabled:
            return False
            
        if not self.next_run:
            return False
            
        now = now or datetime.now()
        return self.next_run <= now
        
    def __str__(self):
        return f"Schedule(id={self.schedule_id}, spider={self.spider_id}, type={self.schedule_type}, next_run={self.next_run})"
        
    def __repr__(self):
        return self.__str__() 