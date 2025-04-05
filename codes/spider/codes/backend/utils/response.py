#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API响应处理工具
提供标准化的API响应格式
"""

from flask import jsonify
from datetime import datetime


def success_response(data=None, message="操作成功", code=200):
    """
    生成成功响应
    :param data: 响应数据
    :param message: 响应消息
    :param code: 响应状态码
    :return: JSON响应
    """
    response = {
        "status": "success",
        "code": code,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    
    if data is not None:
        response["data"] = data
        
    return jsonify(response), code


def error_response(message="操作失败", code=400, errors=None):
    """
    生成错误响应
    :param message: 错误消息
    :param code: 错误状态码
    :param errors: 错误详情
    :return: JSON响应
    """
    response = {
        "status": "error",
        "code": code,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    
    if errors:
        response["errors"] = errors
        
    return jsonify(response), code


def pagination_response(data, page, page_size, total, message="获取数据成功"):
    """
    生成分页响应
    :param data: 分页数据
    :param page: 当前页码
    :param page_size: 每页大小
    :param total: 总记录数
    :param message: 响应消息
    :return: JSON响应
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    response = {
        "status": "success",
        "code": 200,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total": total,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }
    
    return jsonify(response), 200 