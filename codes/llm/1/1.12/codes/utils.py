import os
import re
import json
import logging
import time
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Union, Optional, Any
from datetime import datetime
import mimetypes
import tempfile
import threading

# 配置日志
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("utils")

def generate_unique_id(prefix: str = "item") -> str:
    """
    生成唯一ID
    
    基于当前时间戳和随机性生成唯一标识符
    
    Args:
        prefix: ID前缀
        
    Returns:
        唯一ID字符串
    """
    timestamp = int(time.time() * 1000)
    random_part = os.urandom(4).hex()
    return f"{prefix}_{timestamp}_{random_part}"

def hash_content(content: Union[str, bytes]) -> str:
    """
    计算内容的哈希值
    
    Args:
        content: 要哈希的内容，可以是字符串或字节
        
    Returns:
        MD5哈希值
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    
    return hashlib.md5(content).hexdigest()

def encode_file_to_base64(file_path: Union[str, Path]) -> Optional[str]:
    """
    将文件编码为Base64
    
    Args:
        file_path: 文件路径
        
    Returns:
        Base64编码字符串或None（如果出错）
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
            return base64.b64encode(file_data).decode('utf-8')
    except Exception as e:
        logger.error(f"编码文件时出错: {str(e)}")
        return None

def decode_base64_to_file(base64_data: str, output_path: Union[str, Path], file_ext: Optional[str] = None) -> Optional[Path]:
    """
    将Base64数据解码并保存到文件
    
    Args:
        base64_data: Base64编码字符串
        output_path: 输出文件路径
        file_ext: 文件扩展名，如果output_path没有扩展名
        
    Returns:
        文件路径或None（如果出错）
    """
    try:
        output_path = Path(output_path)
        
        # 如果需要添加扩展名
        if file_ext and not output_path.suffix:
            output_path = output_path.with_suffix(f".{file_ext.lstrip('.')}")
        
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 解码并写入文件
        binary_data = base64.b64decode(base64_data)
        with open(output_path, 'wb') as f:
            f.write(binary_data)
        
        return output_path
    except Exception as e:
        logger.error(f"解码Base64数据时出错: {str(e)}")
        return None

def guess_file_type(file_path: Union[str, Path]) -> Dict[str, str]:
    """
    猜测文件类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        包含文件类型信息的字典
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return {
            "mime_type": "unknown",
            "category": "unknown",
            "extension": file_path.suffix.lstrip('.') if file_path.suffix else "unknown"
        }
    
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    extension = file_path.suffix.lstrip('.')
    
    # 确定类别
    category = "other"
    if mime_type.startswith('image/'):
        category = "image"
    elif mime_type.startswith('video/'):
        category = "video"
    elif mime_type.startswith('audio/'):
        category = "audio"
    elif mime_type.startswith('text/') or mime_type in ('application/json', 'application/xml'):
        category = "text"
    elif mime_type == 'application/pdf':
        category = "document"
    elif mime_type in ('application/zip', 'application/x-rar-compressed', 'application/x-tar'):
        category = "archive"
    
    return {
        "mime_type": mime_type,
        "category": category,
        "extension": extension
    }

def format_timestamp(timestamp: Optional[float] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳
    
    Args:
        timestamp: UNIX时间戳，如果为None则使用当前时间
        format_str: 日期时间格式字符串
        
    Returns:
        格式化后的日期时间字符串
    """
    if timestamp is None:
        timestamp = time.time()
    
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime(format_str)

def get_file_size_formatted(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def extract_keywords_simple(text: str, max_keywords: int = 10, min_word_length: int = 2) -> List[str]:
    """
    从文本中提取关键词的简单实现
    
    Args:
        text: 文本内容
        max_keywords: 最大关键词数量
        min_word_length: 最小词长度
        
    Returns:
        关键词列表
    """
    # 简单的停用词列表
    stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'of', 'to', 'for', 'and', 'or', 'but', 'is', 'are', 
                'was', 'were', 'be', 'been', 'being', 'by', 'with', 'from', 'as', 'this', 'that', 'these', 
                'those', 'it', 'its', 'they', 'them', 'their', 'have', 'has', 'had', 'do', 'does', 'did',
                '的', '了', '和', '是', '在', '我', '有', '就', '不', '人', '都', '一', '一个', '上', '也',
                '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好'}
    
    # 分割文本为单词
    words = re.findall(r'\b\w+\b', text.lower())
    
    # 过滤掉停用词和短词
    filtered_words = [word for word in words if word not in stopwords and len(word) >= min_word_length]
    
    # 计算词频
    word_freq = {}
    for word in filtered_words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # 按频率排序并取前N个
    keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_keywords]
    
    return [word for word, _ in keywords]

def is_binary_file(file_path: Union[str, Path]) -> bool:
    """
    检查文件是否为二进制文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        如果是二进制文件则为True，否则为False
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)  # 尝试以文本模式读取
        return False  # 如果没有异常，则是文本文件
    except UnicodeDecodeError:
        return True  # 解码错误，可能是二进制文件

def save_to_temp_file(content: Union[str, bytes], prefix: str = "temp", suffix: str = ".txt") -> Optional[str]:
    """
    将内容保存到临时文件
    
    Args:
        content: 要保存的内容
        prefix: 文件名前缀
        suffix: 文件扩展名
        
    Returns:
        临时文件路径或None（如果出错）
    """
    try:
        mode = "w" if isinstance(content, str) else "wb"
        encoding = "utf-8" if isinstance(content, str) else None
        
        with tempfile.NamedTemporaryFile(mode=mode, delete=False, prefix=prefix, suffix=suffix, encoding=encoding) as f:
            f.write(content)
            return f.name
    except Exception as e:
        logger.error(f"保存临时文件时出错: {str(e)}")
        return None

def load_json_file(file_path: Union[str, Path]) -> Optional[Any]:
    """
    从JSON文件加载数据
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        解析后的JSON数据或None（如果出错）
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载JSON文件时出错: {str(e)}")
        return None

def save_json_file(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
    """
    将数据保存为JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 输出文件路径
        indent: JSON缩进
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        logger.error(f"保存JSON文件时出错: {str(e)}")
        return False

def run_with_timeout(func, args=(), kwargs={}, timeout_seconds=30, default=None):
    """
    在超时内运行函数
    
    Args:
        func: 要运行的函数
        args: 函数参数
        kwargs: 函数关键字参数
        timeout_seconds: 超时时间（秒）
        default: 超时时返回的默认值
        
    Returns:
        函数结果或超时时的默认值
    """
    result = [default]
    
    def _target():
        result[0] = func(*args, **kwargs)
    
    thread = threading.Thread(target=_target)
    thread.daemon = True
    
    try:
        thread.start()
        thread.join(timeout_seconds)
        
        if thread.is_alive():
            logger.warning(f"函数 {func.__name__} 执行超时 ({timeout_seconds}秒)")
            return default
        
        return result[0]
    except Exception as e:
        logger.error(f"执行函数时出错: {str(e)}")
        return default

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 要截断的文本
        max_length: 最大长度
        suffix: 截断后添加的后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length-len(suffix)] + suffix

def is_valid_file_path(path: str) -> bool:
    """
    检查文件路径是否有效
    
    Args:
        path: 要检查的路径
        
    Returns:
        如果是有效路径则为True，否则为False
    """
    try:
        path_obj = Path(path)
        
        # 检查路径是否包含无效字符
        if os.name == 'nt':  # Windows
            forbidden_chars = '<>:"|?*'
            for char in forbidden_chars:
                if char in str(path_obj.name):
                    return False
        
        # 尝试进行规范化
        path_obj.resolve()
        
        return True
    except Exception:
        return False

def clean_filename(filename: str) -> str:
    """
    清理文件名，移除不允许的字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 移除路径分隔符和不允许的字符
    if os.name == 'nt':  # Windows
        forbidden_chars = r'<>:"/\|?*'
    else:  # Unix/Linux
        forbidden_chars = r'/'
    
    for char in forbidden_chars:
        filename = filename.replace(char, '_')
    
    # 限制长度（Windows路径长度限制）
    if len(filename) > 240:
        base, ext = os.path.splitext(filename)
        filename = base[:240-len(ext)] + ext
    
    return filename

def create_directory_if_not_exists(directory_path: Union[str, Path]) -> bool:
    """
    如果目录不存在则创建
    
    Args:
        directory_path: 目录路径
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        directory_path = Path(directory_path)
        if not directory_path.exists():
            directory_path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录时出错: {str(e)}")
        return False

# 测试代码
if __name__ == "__main__":
    # 测试时间格式化
    print(f"当前时间: {format_timestamp()}")
    
    # 测试唯一ID生成
    print(f"唯一ID: {generate_unique_id()}")
    
    # 测试文件大小格式化
    sizes = [100, 1024, 2048, 1024*1024, 1024*1024*1024]
    for size in sizes:
        print(f"{size} bytes = {get_file_size_formatted(size)}")
    
    # 测试关键词提取
    test_text = """
    Python标准库是Python编程语言的核心组件，提供了丰富的功能模块。
    使用这些模块可以大大提高开发效率，避免重复造轮子。
    本文将介绍Python标准库中最常用的几个模块及其应用场景。
    """
    keywords = extract_keywords_simple(test_text)
    print(f"关键词: {keywords}")
    
    # 测试文本截断
    long_text = "这是一个很长的文本，需要被截断以便于显示。" * 5
    print(f"截断文本: {truncate_text(long_text, 30)}")
    
    # 测试文件名清理
    print(f"清理后的文件名: {clean_filename('file<>:"/\\|?*name.txt')}") 