import uuid
import bcrypt
from datetime import datetime

class User:
    """用户模型"""
    
    def __init__(self, username, email, password=None, role='user', user_id=None, 
                 created_at=None, last_login=None, status='active'):
        """初始化用户模型"""
        self.user_id = user_id or str(uuid.uuid4())
        self.username = username
        self.email = email
        self.role = role
        self.created_at = created_at or datetime.now()
        self.last_login = last_login
        self.status = status
        
        # 如果提供了密码，则进行哈希处理
        if password:
            self.set_password(password)
        else:
            self.password = None
    
    def set_password(self, password):
        """设置密码，进行哈希处理"""
        salt = bcrypt.gensalt()
        self.password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return self
    
    def check_password(self, password):
        """检查密码是否正确"""
        if not self.password:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password)
    
    def to_dict(self, include_password=False):
        """转换为字典表示"""
        result = {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'status': self.status
        }
        
        if include_password:
            result['password'] = self.password
            
        return result
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建用户对象"""
        user = cls(
            username=data.get('username'),
            email=data.get('email'),
            role=data.get('role', 'user'),
            user_id=data.get('user_id'),
            created_at=data.get('created_at'),
            last_login=data.get('last_login'),
            status=data.get('status', 'active')
        )
        
        # 如果有密码哈希值，直接设置
        if 'password' in data:
            user.password = data['password']
            
        return user
    
    def is_admin(self):
        """检查是否是管理员"""
        return self.role == 'admin'
    
    def is_active(self):
        """检查用户是否处于活动状态"""
        return self.status == 'active'
    
    def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.now()
        return self
        
    def __str__(self):
        return f"User(id={self.user_id}, username={self.username}, role={self.role})"
        
    def __repr__(self):
        return self.__str__() 