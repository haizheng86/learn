from flask import Blueprint, request, jsonify, g
from services.user import UserService
from utils.auth import token_required, admin_required
from utils.response import success_response, error_response
import logging

logger = logging.getLogger(__name__)

# 初始化蓝图
bp = Blueprint('user', __name__, url_prefix='/api/users')

# 获取用户服务实例
def get_user_service():
    from app import get_mongo_uri
    if not hasattr(g, 'user_service'):
        g.user_service = UserService(get_mongo_uri())
    return g.user_service

@bp.route('/register', methods=['POST'])
def register():
    """注册新用户"""
    data = request.json
    
    # 验证请求数据
    required_fields = ['username', 'password', 'email']
    for field in required_fields:
        if field not in data:
            return error_response(f"缺少必填字段: {field}", 400)
    
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    # 注册用户
    user_service = get_user_service()
    success, result = user_service.register_user(username, password, email)
    
    if success:
        return success_response({"user_id": result}, "用户注册成功")
    else:
        return error_response(result, 400)

@bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    
    # 验证请求数据
    required_fields = ['username', 'password']
    for field in required_fields:
        if field not in data:
            return error_response(f"缺少必填字段: {field}", 400)
    
    username = data.get('username')
    password = data.get('password')
    
    # 用户认证
    user_service = get_user_service()
    user = user_service.authenticate(username, password)
    
    if user:
        # 生成JWT令牌
        from utils.auth import generate_token
        token = generate_token(user)
        
        return success_response({
            "token": token,
            "user": user
        }, "登录成功")
    else:
        return error_response("用户名或密码错误", 401)

@bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """获取当前用户信息"""
    user_id = g.current_user.get('user_id')
    user_service = get_user_service()
    user = user_service.get_user_by_id(user_id)
    
    if user:
        return success_response(user, "获取用户信息成功")
    else:
        return error_response("用户不存在", 404)

@bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    """更新当前用户信息"""
    user_id = g.current_user.get('user_id')
    data = request.json
    
    user_service = get_user_service()
    result = user_service.update_user(user_id, data)
    
    if result:
        return success_response({}, "用户信息更新成功")
    else:
        return error_response("更新失败", 400)

@bp.route('/password', methods=['PUT'])
@token_required
def change_password():
    """修改密码"""
    data = request.json
    
    # 验证请求数据
    required_fields = ['old_password', 'new_password']
    for field in required_fields:
        if field not in data:
            return error_response(f"缺少必填字段: {field}", 400)
    
    user_id = g.current_user.get('user_id')
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    user_service = get_user_service()
    success, message = user_service.change_password(user_id, old_password, new_password)
    
    if success:
        return success_response({}, message)
    else:
        return error_response(message, 400)

@bp.route('/', methods=['GET'])
@token_required
@admin_required
def get_users():
    """获取用户列表（仅管理员）"""
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    role = request.args.get('role')
    
    user_service = get_user_service()
    users, total = user_service.get_users(page, page_size, role)
    
    return success_response({
        "users": users,
        "total": total,
        "page": page,
        "page_size": page_size
    }, "获取用户列表成功")

@bp.route('/<user_id>', methods=['GET'])
@token_required
@admin_required
def get_user(user_id):
    """获取指定用户信息（仅管理员）"""
    user_service = get_user_service()
    user = user_service.get_user_by_id(user_id)
    
    if user:
        return success_response(user, "获取用户信息成功")
    else:
        return error_response("用户不存在", 404)

@bp.route('/<user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user(user_id):
    """更新指定用户信息（仅管理员）"""
    data = request.json
    
    user_service = get_user_service()
    result = user_service.update_user(user_id, data)
    
    if result:
        return success_response({}, "用户信息更新成功")
    else:
        return error_response("更新失败，用户可能不存在", 400) 