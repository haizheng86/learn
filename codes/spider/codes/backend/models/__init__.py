"""数据模型定义

这个模块包含系统中使用的所有数据模型类定义。
虽然MongoDB是无模式的，但我们仍然定义模型类来提供数据结构约束和业务逻辑封装。
"""

from .spider import Spider
from .proxy import Proxy
from .user import User
from .schedule import Schedule

__all__ = ['Spider', 'Proxy', 'User', 'Schedule'] 