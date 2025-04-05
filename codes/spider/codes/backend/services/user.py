import uuid
import bcrypt
import logging
from datetime import datetime
from pymongo import MongoClient
import pymongo

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, mongo_uri):
        """初始化用户服务"""
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client.crawler_db
        self.users = self.db.users
        
        # 创建索引
        self.users.create_index([('username', pymongo.ASCENDING)], unique=True)
        self.users.create_index([('email', pymongo.ASCENDING)], unique=True)
        
    def register_user(self, username, password, email, role='user'):
        """注册新用户"""
        # 检查用户名是否已存在
        if self.users.find_one({'username': username}):
            return False, "用户名已存在"
            
        # 检查邮箱是否已存在
        if self.users.find_one({'email': email}):
            return False, "邮箱已被注册"
            
        # 创建用户记录
        user_id = str(uuid.uuid4())
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        user = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': role,
            'created_at': datetime.now(),
            'last_login': None,
            'status': 'active'
        }
        
        self.users.insert_one(user)
        return True, user_id
        
    def authenticate(self, username, password):
        """验证用户"""
        user = self.users.find_one({'username': username})
        if not user:
            return None
            
        # 验证密码
        if bcrypt.checkpw(password.encode('utf-8'), user['password']):
            # 更新最后登录时间
            self.users.update_one(
                {'username': username},
                {'$set': {'last_login': datetime.now()}}
            )
            return {
                'user_id': user['user_id'],
                'username': user['username'],
                'role': user['role'],
                'email': user['email']
            }
        
        return None
        
    def get_user_by_id(self, user_id):
        """根据ID获取用户信息"""
        user = self.users.find_one({'user_id': user_id})
        if not user:
            return None
            
        return {
            'user_id': user['user_id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
            'created_at': user['created_at'],
            'last_login': user['last_login'],
            'status': user['status']
        }
        
    def update_user(self, user_id, update_data):
        """更新用户信息"""
        # 不允许更新的字段
        protected_fields = ['user_id', 'password', 'created_at']
        
        # 移除保护字段
        for field in protected_fields:
            if field in update_data:
                del update_data[field]
                
        # 更新用户信息
        result = self.users.update_one(
            {'user_id': user_id},
            {'$set': update_data}
        )
        
        return result.modified_count > 0
        
    def change_password(self, user_id, old_password, new_password):
        """修改用户密码"""
        user = self.users.find_one({'user_id': user_id})
        if not user:
            return False, "用户不存在"
            
        # 验证旧密码
        if not bcrypt.checkpw(old_password.encode('utf-8'), user['password']):
            return False, "原密码不正确"
            
        # 更新密码
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), salt)
        
        self.users.update_one(
            {'user_id': user_id},
            {'$set': {'password': hashed_password}}
        )
        
        return True, "密码修改成功"
        
    def get_users(self, page=1, page_size=20, role=None):
        """获取用户列表"""
        skip = (page - 1) * page_size
        
        # 查询条件
        query = {}
        if role:
            query['role'] = role
            
        # 查询用户
        users = list(self.users.find(
            query,
            {'password': 0}  # 不返回密码字段
        ).sort('created_at', pymongo.DESCENDING)
         .skip(skip)
         .limit(page_size))
        
        # 获取总数
        total = self.users.count_documents(query)
        
        return users, total 