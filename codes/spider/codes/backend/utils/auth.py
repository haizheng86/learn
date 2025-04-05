#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
认证相关工具函数
提供用户认证、权限验证等功能
"""

import jwt
import logging
from functools import wraps
from flask import request, current_app, g
from datetime import datetime, timedelta
from .response import error_response

# 配置日志
logger = logging.getLogger('utils.auth')

def generate_token(user_id, username, role='user', expires_in=3600):
    """
    生成JWT令牌
    :param user_id: 用户ID
    :param username: 用户名
    :param role: 用户角色
    :param expires_in: 过期时间（秒）
    :return: JWT令牌
    """
    payload = {
        'sub': str(user_id),
        'username': username,
        'role': role,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=expires_in)
    }
    
    token = jwt.encode(
        payload, 
        current_app.config['JWT_SECRET_KEY'], 
        algorithm='HS256'
    )
    
    return token

def verify_token(token):
    """
    验证JWT令牌
    :param token: JWT令牌
    :return: 解码后的载荷或None
    """
    try:
        payload = jwt.decode(
            token, 
            current_app.config['JWT_SECRET_KEY'], 
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("令牌已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"无效的令牌: {str(e)}")
        return None

def login_required(f):
    """
    需要登录的装饰器
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 获取Authorization头
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            logger.warning("请求缺少认证信息")
            return error_response("需要认证", code=401)
        
        # 解析Bearer令牌
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            logger.warning("认证格式无效")
            return error_response("认证格式无效", code=401)
        
        token = parts[1]
        payload = verify_token(token)
        
        if not payload:
            return error_response("无效或过期的令牌", code=401)
        
        # 将用户信息存储在g对象中，以便在视图函数中使用
        g.user = {
            'id': payload['sub'],
            'username': payload['username'],
            'role': payload['role']
        }
        
        return f(*args, **kwargs)
    
    return decorated_function

def admin_required(f):
    """
    需要管理员权限的装饰器
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 先验证用户是否已登录
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            logger.warning("请求缺少认证信息")
            return error_response("需要认证", code=401)
        
        # 解析Bearer令牌
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            logger.warning("认证格式无效")
            return error_response("认证格式无效", code=401)
        
        token = parts[1]
        payload = verify_token(token)
        
        if not payload:
            return error_response("无效或过期的令牌", code=401)
        
        # 验证用户角色
        if payload['role'] != 'admin':
            logger.warning(f"用户 {payload['username']} 尝试访问管理员资源")
            return error_response("需要管理员权限", code=403)
        
        # 将用户信息存储在g对象中，以便在视图函数中使用
        g.user = {
            'id': payload['sub'],
            'username': payload['username'],
            'role': payload['role']
        }
        
        return f(*args, **kwargs)
    
    return decorated_function 