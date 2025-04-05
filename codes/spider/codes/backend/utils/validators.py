import re
import logging
from functools import wraps
from flask import request, jsonify
from utils.response import error_response

logger = logging.getLogger(__name__)

# 邮箱地址正则表达式
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# URL正则表达式
URL_REGEX = re.compile(
    r'^(?:http|ftp)s?://'  # http://, https://, ftp://, ftps://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # 域名
    r'localhost|'  # localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
    r'(?::\d+)?'  # 可选端口
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)  # 路径和参数

# 用户名正则表达式：字母开头，只包含字母、数字和下划线，长度5-20
USERNAME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{4,19}$')

def validate_email(email):
    """验证邮箱地址格式"""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email))

def validate_url(url):
    """验证URL格式"""
    if not url or not isinstance(url, str):
        return False
    return bool(URL_REGEX.match(url))

def validate_username(username):
    """验证用户名格式"""
    if not username or not isinstance(username, str):
        return False
    return bool(USERNAME_REGEX.match(username))

def validate_password_strength(password):
    """验证密码强度"""
    if not password or not isinstance(password, str):
        return False, "密码不能为空"
        
    if len(password) < 8:
        return False, "密码长度至少为8个字符"
        
    # 检查是否包含大小写字母和数字
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "密码必须包含大小写字母和数字"
        
    return True, "密码强度符合要求"

def validate_spider_config(config):
    """验证爬虫配置"""
    required_fields = ['name', 'domain']
    for field in required_fields:
        if field not in config:
            return False, f"缺少必填字段: {field}"
            
    # 验证起始URL
    if 'start_urls' in config:
        for url in config['start_urls']:
            if not validate_url(url):
                return False, f"无效的URL: {url}"
                
    return True, "配置有效"

def validate_proxy(proxy_data):
    """验证代理数据"""
    required_fields = ['ip', 'port']
    for field in required_fields:
        if field not in proxy_data:
            return False, f"缺少必填字段: {field}"
            
    # 验证IP地址格式
    ip = proxy_data['ip']
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
        return False, f"无效的IP地址: {ip}"
        
    # 验证端口号
    port = proxy_data['port']
    if not isinstance(port, int) or port < 1 or port > 65535:
        return False, f"无效的端口号: {port}"
        
    return True, "代理数据有效"

def validate_schedule(schedule_data):
    """验证调度计划数据"""
    required_fields = ['spider_id', 'schedule_type']
    for field in required_fields:
        if field not in schedule_data:
            return False, f"缺少必填字段: {field}"
            
    schedule_type = schedule_data['schedule_type']
    
    # 如果是间隔执行，需要验证interval_value和interval_unit
    if schedule_type == 'interval':
        if 'interval_value' not in schedule_data:
            return False, "间隔执行需要指定interval_value"
            
        interval_value = schedule_data['interval_value']
        if not isinstance(interval_value, int) or interval_value < 1:
            return False, "interval_value必须是大于0的整数"
            
        if 'interval_unit' not in schedule_data:
            return False, "间隔执行需要指定interval_unit"
            
        interval_unit = schedule_data['interval_unit']
        if interval_unit not in ['minutes', 'hours', 'days', 'weeks']:
            return False, f"无效的interval_unit: {interval_unit}"
            
    # 验证first_run
    if 'first_run' in schedule_data:
        first_run = schedule_data['first_run']
        if not isinstance(first_run, str):
            return False, "first_run必须是ISO8601格式的日期时间字符串"
            
        try:
            import dateutil.parser
            dateutil.parser.parse(first_run)
        except Exception as e:
            return False, f"无效的first_run格式: {str(e)}"
            
    return True, "调度计划数据有效"

def required_params(**param_types):
    """装饰器：验证请求参数"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 根据请求方法获取参数
            if request.method == 'GET':
                req_params = request.args
            else:
                req_params = request.json or {}
                
            missing_params = []
            invalid_params = []
            
            # 验证参数
            for param_name, param_type in param_types.items():
                if param_name not in req_params:
                    missing_params.append(param_name)
                    continue
                    
                value = req_params[param_name]
                
                # 验证类型
                if param_type == int:
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        invalid_params.append(f"{param_name}必须是整数")
                elif param_type == float:
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        invalid_params.append(f"{param_name}必须是数字")
                elif param_type == bool:
                    if not isinstance(value, bool) and value not in ('true', 'false', '0', '1'):
                        invalid_params.append(f"{param_name}必须是布尔值")
                elif param_type == list:
                    if not isinstance(value, list):
                        invalid_params.append(f"{param_name}必须是数组")
                elif param_type == dict:
                    if not isinstance(value, dict):
                        invalid_params.append(f"{param_name}必须是对象")
                        
            # 如果存在缺失或无效参数，返回错误
            if missing_params:
                return error_response(f"缺少必填参数: {', '.join(missing_params)}", 400)
                
            if invalid_params:
                return error_response(f"参数验证失败: {'; '.join(invalid_params)}", 400)
                
            return func(*args, **kwargs)
            
        return wrapper
    return decorator 