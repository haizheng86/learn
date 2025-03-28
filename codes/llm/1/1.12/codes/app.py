#!/usr/bin/env python3
# app.py - 多模态内容助手Web应用

import os
import time
import logging
import json
import tempfile
from collections import Counter, defaultdict
import re
import argparse
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from PIL import Image
import sys
import webbrowser
from threading import Timer
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Optional, Any, Tuple
import subprocess
import openai
import nltk
import numpy as np

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("multimodal_assistant")

# 停用词集合 - 简化版
STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
    'when', 'where', 'how', 'why', 'which', 'who', 'this', 'that',
    'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'to', 'at', 'by', 'for',
    'with', 'about', 'against', 'between', 'into', 'through',
    '的', '了', '和', '是', '在', '我', '有', '就', '不', '人', '都',
    '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
    '会', '着', '没有', '看', '好', '自己', '这个'
}

class TextAnalyzer:
    """文本分析器，提供关键词提取、情感分析等功能"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 尝试加载NLTK资源
        try:
            import nltk
            nltk_data_path = os.path.join(os.path.dirname(__file__), 'nltk_data')
            print(f"NLTK数据路径: {nltk_data_path}")
            nltk.data.path.append(nltk_data_path)
            
            # 检查NLTK资源是否已下载到项目目录
            required_resources = ['tokenizers/punkt', 'corpora/stopwords', 'sentiment/vader_lexicon']
            resources_exist = all(os.path.exists(os.path.join(nltk_data_path, resource)) for resource in required_resources)
            
            if not resources_exist:
                logger.info("正在下载NLTK资源到项目目录...")
                try:
                    # 确保nltk_data目录存在
                    os.makedirs(nltk_data_path, exist_ok=True)
                    
                    # 下载资源到指定目录
                    for resource in required_resources:
                        nltk.download(resource, download_dir=nltk_data_path, quiet=True)
                    logger.info("NLTK资源下载完成")
                except Exception as e:
                    logger.error(f"下载NLTK资源失败: {str(e)}")
                    raise
            else:
                logger.info("NLTK资源已存在于项目目录中")
                
        except ImportError:
            self.logger.warning("未安装NLTK，将使用简化的文本分析")
    
    def analyze(self, text_path=None, text_content=None):
        """分析文本内容"""
        if text_path:
            with open(text_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif text_content:
            text = text_content
        else:
            raise ValueError("需要提供文本路径或文本内容")
            
        try:
            # 分析文本内容
            result = {
                'content_type': 'text',
                'length': len(text),
                'language': self.detect_language(text),
                'keywords': self.extract_keywords(text),
                'sentiment': self.analyze_sentiment(text),
                'timestamps': self.extract_timestamps(text)
            }
            
            # 添加字数和句子数统计
            words = text.split()
            sentences = re.split(r'[.!?。！？\n]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            result['word_count'] = len(words)
            result['sentence_count'] = len(sentences)
            result['avg_word_length'] = sum(len(word) for word in words) / max(1, len(words))
            result['avg_sentence_length'] = len(words) / max(1, len(sentences))
            
            # 添加简短摘要（前100个字符）
            result['summary'] = text[:100] + ('...' if len(text) > 100 else '')
            
            return result
        except Exception as e:
            self.logger.error(f"文本分析错误: {str(e)}")
            return {
                'content_type': 'text',
                'error': str(e)
            }
    
    def extract_keywords(self, text):
        """提取文本关键词"""
        try:
            import jieba.analyse
            # 使用jieba提取关键词
            keywords = jieba.analyse.extract_tags(text, topK=10)
            return keywords
        except ImportError:
            # 如果没有jieba，使用简单的词频统计
            try:
                from collections import Counter
                import re
                # 简单分词
                words = re.findall(r'\w+', text.lower())
                # 过滤常见停用词和短词
                stopwords = {'的', '了', '和', '是', '在', '我', '有', '为', '这', '你', 'the', 'and', 'to', 'of', 'a', 'in', 'is', 'that', 'it', 'with'}
                filtered_words = [word for word in words if word not in stopwords and len(word) > 1]
                # 统计词频
                word_counter = Counter(filtered_words)
                # 返回最常见的10个词
                return [word for word, _ in word_counter.most_common(10)]
            except Exception as e:
                self.logger.error(f"关键词提取错误: {str(e)}")
                return []
    
    def analyze_sentiment(self, text):
        """分析文本情感"""
        try:
            # 尝试使用NLTK的VADER进行情感分析
            try:
                from nltk.sentiment.vader import SentimentIntensityAnalyzer
                
                # 尝试初始化VADER分析器
                try:
                    sid = SentimentIntensityAnalyzer()
                    scores = sid.polarity_scores(text)
                    
                    # 根据compound分数确定情感
                    sentiment, score = None, None
                    if scores['compound'] >= 0.05:
                        sentiment, score = "积极", scores['compound']
                    elif scores['compound'] <= -0.05:
                        sentiment, score = "消极", abs(scores['compound'])
                    else:
                        sentiment, score = "中性", 0.5
                        
                    # 返回标准化结果
                    return self._normalize_sentiment(sentiment)
                        
                except Exception as e:
                    self.logger.warning(f"VADER情感分析失败: {str(e)}")
                    # 优雅地回退到简单情感分析
            except ImportError:
                self.logger.warning("NLTK VADER未安装，使用简单情感分析")
            
            # 简单的情感分析，通过计算积极和消极词的数量
            # 积极和消极词汇列表（简化版）
            positive_words = ['好', '喜欢', '棒', '赞', '优秀', '美', '爱', '开心', '快乐', '高兴', '精彩',
                             'good', 'great', 'excellent', 'like', 'love', 'happy', 'best', 'amazing']
            negative_words = ['差', '不好', '糟', '坏', '讨厌', '失望', '难过', '伤心', '痛苦', '恨', '烂',
                             'bad', 'worse', 'worst', 'hate', 'dislike', 'terrible', 'poor', 'awful']
            
            # 计算出现次数
            positive_count = sum(1 for word in positive_words if word in text.lower())
            negative_count = sum(1 for word in negative_words if word in text.lower())
            
            # 确定情感
            sentiment = None
            if positive_count > negative_count:
                sentiment = "积极"
            elif negative_count > positive_count:
                sentiment = "消极"
            else:
                sentiment = "中性"
                
            # 返回标准化结果
            return self._normalize_sentiment(sentiment)
                
        except Exception as e:
            self.logger.error(f"情感分析错误: {str(e)}")
            return 'unknown'
            
    def _normalize_sentiment(self, sentiment):
        """标准化情感结果"""
        # 映射中文情感标签到英文
        sentiment_map = {
            "积极": "positive",
            "消极": "negative",
            "中性": "neutral",
            "未知": "unknown"
        }
        
        return sentiment_map.get(sentiment, 'unknown')
    
    def detect_language(self, text):
        """检测文本语言"""
        try:
            # 简单语言检测，通过统计特定字符
            chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            english_chars = sum(1 for char in text if 'a' <= char.lower() <= 'z')
            
            if chinese_chars > english_chars:
                return 'chinese'
            elif english_chars > chinese_chars:
                return 'english'
            else:
                return 'unknown'
                
        except Exception as e:
            self.logger.error(f"语言检测错误: {str(e)}")
            return 'unknown'
    
    def extract_timestamps(self, text):
        """提取文本中的时间戳"""
        try:
            # 匹配常见时间格式，如 YYYY-MM-DD, HH:MM:SS
            time_patterns = [
                r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                r'\d{2}:\d{2}:\d{2}',  # HH:MM:SS
                r'\d{4}年\d{1,2}月\d{1,2}日',  # YYYY年MM月DD日
                r'\d{1,2}月\d{1,2}日',  # MM月DD日
                r'\d{1,2}:\d{2}'  # HH:MM
            ]
            
            timestamps = []
            for pattern in time_patterns:
                timestamps.extend(re.findall(pattern, text))
                
            return timestamps
            
        except Exception as e:
            self.logger.error(f"时间戳提取错误: {str(e)}")
            return []

class MediaProcessor:
    """媒体处理器，支持图片、音频、视频分析"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 定义支持的文件类型映射
        self.supported_types = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'],
            'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.3gp'],
            'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma'],
            'text': ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.log', '.py', '.js', '.css']
        }
    
    def _detect_type(self, file_path):
        """
        检测文件类型，返回标准MIME类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件MIME类型字符串
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # 基于扩展名的简单类型检测
        # 图像文件
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg']:
            self.logger.info(f"根据扩展名判断文件类型: image/{ext[1:]}")
            return f"image/{ext[1:]}"
            
        # 视频文件
        elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v']:
            self.logger.info(f"根据扩展名判断文件类型: video/{ext[1:]}")
            return f"video/{ext[1:]}"
            
        # 音频文件
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma']:
            self.logger.info(f"根据扩展名判断文件类型: audio/{ext[1:]}")
            return f"audio/{ext[1:]}"
            
        # 文本文件
        elif ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.css', '.js', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.pl', '.sh', '.bat', '.log', '.ini', '.config', '.yaml', '.yml']:
            self.logger.info(f"根据扩展名判断文件类型: text")
            return "text"
            
        # 文档文件
        elif ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp']:
            self.logger.info(f"根据扩展名判断文件类型: application/{ext[1:]}")
            return f"application/{ext[1:]}"
            
        # 压缩文件
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']:
            self.logger.info(f"根据扩展名判断文件类型: application/{ext[1:]}")
            return f"application/{ext[1:]}"
            
        # 无法判断时，尝试使用Python的mimetypes模块
        try:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                self.logger.info(f"使用mimetypes判断文件类型: {mime_type}")
                return mime_type
        except:
            pass
            
        # 无法识别类型，返回未知类型
        self.logger.warning(f"无法识别的文件类型: {ext}")
        return "application/octet-stream"
    
    def analyze(self, file_path):
        """
        分析文件内容，根据文件类型进行不同的处理
        
        Args:
            file_path: 文件路径
            
        Returns:
            分析结果字典
        """
        try:
            # 检测文件类型
            file_type = self._detect_type(file_path)
            
            # 获取文件基本信息
            file_info = {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size": os.path.getsize(file_path),
                "size_formatted": self._format_size(os.path.getsize(file_path)),
                "type": file_type,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
            # 根据文件类型进行分析
            content_analysis = {}
            
            if file_type.startswith("image/"):
                # 图像分析
                self.logger.info(f"分析图像文件: {file_path}")
                content_analysis = self._analyze_image(file_path)
                
            elif file_type.startswith("video/"):
                # 视频分析
                self.logger.info(f"分析视频文件: {file_path}")
                content_analysis = self._analyze_video(file_path)
                
            elif file_type.startswith("audio/"):
                # 音频分析
                self.logger.info(f"分析音频文件: {file_path}")
                content_analysis = self._analyze_audio(file_path)
                
            elif file_type == "text":
                # 文本分析 - 读取文件并提供文本预览
                self.logger.info(f"分析文本文件: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    
                    # 限制预览长度
                    preview_length = min(5000, len(text))
                    text_preview = text[:preview_length]
                    if len(text) > preview_length:
                        text_preview += "..."
                    
                    # 统计行数和字符数
                    line_count = text.count('\n') + 1
                    char_count = len(text)
                    word_count = len(text.split())
                    
                    content_analysis = {
                        "text_info": {
                            "preview": text_preview,
                            "full_length": len(text),
                            "line_count": line_count,
                            "char_count": char_count,
                            "word_count": word_count
                        }
                    }
                except Exception as e:
                    self.logger.error(f"读取文本文件出错: {str(e)}")
                    content_analysis = {"error": f"读取文本文件出错: {str(e)}"}
            else:
                # 未知或不支持的文件类型
                self.logger.warning(f"不支持的媒体类型: {file_type}")
                content_analysis = {"error": f"不支持的媒体类型: {file_type}"}
            
            # 合并文件信息和内容分析结果
            result = {
                "file_info": file_info,
                **content_analysis
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"文件分析错误: {str(e)}")
            return {
                "error": f"文件分析错误: {str(e)}",
                "file": os.path.basename(file_path) if file_path else "未知文件"
            }
    
    def _analyze_image(self, image_path):
        """分析图片，提取元数据和内容特征"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                format_name = img.format
                mode = img.mode
                
                # 基本图片信息
                image_info = {
                    "width": width,
                    "height": height,
                    "format": format_name,
                    "mode": mode,
                    "aspect_ratio": round(width / height, 2) if height > 0 else 0
                }
                
                # 色彩分析
                color_analysis = self._analyze_image_colors(img)
                image_info["color_analysis"] = color_analysis
                
                # 图像内容分析
                content_analysis = self._analyze_image_content(img)
                image_info["content_analysis"] = content_analysis
                
                # 图像深度内容识别
                try:
                    content_recognition = self._recognize_image_content(image_path)
                    if content_recognition:
                        image_info["content_recognition"] = content_recognition
                except Exception as e:
                    self.logger.error(f"识别图像内容时出错: {str(e)}")
                
                # 检测图像中的文本
                try:
                    text_detection = self._detect_image_text(image_path)
                    if text_detection:
                        image_info["text_detection"] = text_detection
                except Exception as e:
                    self.logger.error(f"检测图像文本时出错: {str(e)}")
                
                return image_info
                
        except Exception as e:
            self.logger.error(f"分析图片时出错: {str(e)}")
            return {"error": f"分析图片时出错: {str(e)}"}
    
    def _recognize_image_content(self, image_path):
        """识别图片内容（对象、场景、人物等）使用大模型API"""
        try:
            # 基本图像信息
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height if height > 0 else 0
                format_type = "横向" if aspect_ratio > 1.2 else "竖向" if aspect_ratio < 0.8 else "方形"
                size_desc = "高清大图" if width > 1920 or height > 1920 else "小尺寸图片" if width < 400 or height < 400 else "标准尺寸图片"
            
            # 使用AIService进行图像识别
            global ai_service
            
            # 如果全局实例不可用，创建一个新的
            if 'ai_service' not in globals() or ai_service is None:
                self.logger.info("创建新的AIService实例")
                api_key = os.getenv("OPENAI_API_KEY")
                # 这里不需要导入，直接使用当前模块中定义的AIService类
                ai_service = AIService(api_key=api_key)
            
            # 使用AI服务分析图像
            result = ai_service.analyze_image(image_path)
            
            if result.get("success", False):
                # API分析成功
                data = result.get("data", {})
                
                # 提取对象和场景信息
                objects = data.get("objects", [])
                scene_type = data.get("scene_type", "未知场景")
                description = data.get("description", "")
                
                recognition_result = {
                    "objects": objects,
                    "scene_type": scene_type,
                    "format_type": format_type,
                    "size_description": size_desc,
                    "aspect_ratio": round(aspect_ratio, 2),
                    "description": description,
                    "method": "api"
                }
                
                self.logger.info(f"使用API成功识别图像内容: {scene_type}")
                return recognition_result
            else:
                # API分析失败，使用本地方法
                self.logger.warning(f"API分析失败: {result.get('error', '未知错误')}，使用本地方法")
            
            # 回退到本地识别方法
            self.logger.info("使用本地方法进行图像内容识别")
            objects_detected = self._detect_objects_with_yolo(image_path)
            scene_type = self._classify_scene(image_path)
            
            # 构建分析结果
            recognition_result = {
                "objects": objects_detected,
                "scene_type": scene_type,
                "format_type": format_type,
                "size_description": size_desc,
                "aspect_ratio": round(aspect_ratio, 2),
                "method": "local"
            }
            
            # 生成描述性文本
            description = f"这是一张{format_type}{size_desc}，"
            
            if objects_detected:
                description += f"图中包含以下物体：{', '.join(objects_detected[:5])}"
                if len(objects_detected) > 5:
                    description += f"等{len(objects_detected)}个对象。"
                else:
                    description += "。"
            else:
                description += f"场景类型可能是{scene_type}。"
                
            recognition_result["description"] = description
            
            return recognition_result
            
        except Exception as e:
            self.logger.error(f"识别图像内容时出错: {str(e)}", exc_info=True)
            return {"error": str(e), "objects": [], "scene_type": "未知", "method": "error"}
    
    def _detect_objects_with_yolo(self, image_path):
        """使用YOLO模型检测图像中的物体"""
        try:
            # 检查OpenCV是否可用
            import cv2
            import numpy as np
            
            # 加载图像
            image = cv2.imread(image_path)
            if image is None:
                return []
                
            # 检查模型文件是否存在
            model_dir = os.path.join(os.path.dirname(__file__), "models")
            weights_path = os.path.join(model_dir, "yolov3-tiny.weights")
            config_path = os.path.join(model_dir, "yolov3-tiny.cfg")
            names_path = os.path.join(model_dir, "coco.names")
            
            # 如果模型文件不存在，返回模拟结果
            if not (os.path.exists(weights_path) and os.path.exists(config_path) and os.path.exists(names_path)):
                self.logger.warning("YOLO模型文件不存在，使用模拟检测结果")
                # 模拟检测结果 - 根据图像类型猜测可能的内容
                with Image.open(image_path) as img:
                    avg_rgb = np.array(img.resize((1, 1))).mean()
                    objects = []
                    if avg_rgb < 80:  # 暗色图像
                        objects = ["夜景", "暗光环境"]
                    elif "person" in image_path.lower() or "people" in image_path.lower():
                        objects = ["人物", "人像"]
                    elif "landscape" in image_path.lower() or "scene" in image_path.lower():
                        objects = ["风景", "自然场景"]
                    else:
                        objects = ["物体"]
                return objects
                
            # 加载COCO类别名称
            with open(names_path, "r") as f:
                classes = [line.strip() for line in f.readlines()]
                
            # 加载YOLO模型
            net = cv2.dnn.readNetFromDarknet(config_path, weights_path)
            
            # 获取输出层名称
            layer_names = net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
            
            # 准备输入图像
            height, width, _ = image.shape
            blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
            
            # 设置输入并前向传播
            net.setInput(blob)
            outs = net.forward(output_layers)
            
            # 处理检测结果
            class_ids = []
            confidences = []
            boxes = []
            
            for out in outs:
                for detection in out:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > 0.5:  # 置信度阈值
                        # 目标坐标
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # 边界框坐标
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        
                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
            
            # 非极大值抑制，移除重叠框
            indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
            
            # 整理检测结果
            detected_objects = []
            for i in range(len(boxes)):
                if i in indexes:
                    class_name = classes[class_ids[i]]
                    if class_name not in detected_objects:
                        detected_objects.append(class_name)
            
            # 将英文类别名称翻译成中文
            translation = {
                "person": "人物", "bicycle": "自行车", "car": "汽车", "motorcycle": "摩托车",
                "airplane": "飞机", "bus": "公交车", "train": "火车", "truck": "卡车",
                "boat": "船", "traffic light": "交通灯", "fire hydrant": "消防栓",
                "stop sign": "停止标志", "parking meter": "停车计时器", "bench": "长凳",
                "bird": "鸟", "cat": "猫", "dog": "狗", "horse": "马", "sheep": "羊",
                "cow": "牛", "elephant": "大象", "bear": "熊", "zebra": "斑马",
                "giraffe": "长颈鹿", "backpack": "背包", "umbrella": "雨伞",
                "handbag": "手提包", "tie": "领带", "suitcase": "手提箱",
                "frisbee": "飞盘", "skis": "滑雪板", "snowboard": "滑雪板",
                "sports ball": "运动球", "kite": "风筝", "baseball bat": "棒球棒",
                "baseball glove": "棒球手套", "skateboard": "滑板",
                "surfboard": "冲浪板", "tennis racket": "网球拍",
                "bottle": "瓶子", "wine glass": "酒杯", "cup": "杯子",
                "fork": "叉子", "knife": "刀", "spoon": "勺子", "bowl": "碗",
                "banana": "香蕉", "apple": "苹果", "sandwich": "三明治",
                "orange": "橙子", "broccoli": "西兰花", "carrot": "胡萝卜",
                "hot dog": "热狗", "pizza": "披萨", "donut": "甜甜圈",
                "cake": "蛋糕", "chair": "椅子", "couch": "沙发",
                "potted plant": "盆栽", "bed": "床", "dining table": "餐桌",
                "toilet": "马桶", "tv": "电视", "laptop": "笔记本电脑",
                "mouse": "鼠标", "remote": "遥控器", "keyboard": "键盘",
                "cell phone": "手机", "microwave": "微波炉", "oven": "烤箱",
                "toaster": "烤面包机", "sink": "水槽", "refrigerator": "冰箱",
                "book": "书", "clock": "时钟", "vase": "花瓶",
                "scissors": "剪刀", "teddy bear": "泰迪熊", "hair drier": "吹风机",
                "toothbrush": "牙刷"
            }
            
            translated_objects = []
            for obj in detected_objects:
                translated_objects.append(translation.get(obj, obj))
                
            return translated_objects
            
        except ImportError:
            self.logger.warning("OpenCV未安装，无法使用YOLO进行物体检测")
            return ["未安装物体检测模块"]
        except Exception as e:
            self.logger.error(f"YOLO物体检测错误: {str(e)}")
            return []
    
    def _classify_scene(self, image_path):
        """简单场景分类"""
        try:
            with Image.open(image_path) as img:
                # 缩小图像以加速处理
                img_small = img.resize((100, 100))
                
                # 转换为RGB模式
                if img.mode != "RGB":
                    img_small = img_small.convert("RGB")
                    
                # 计算颜色分布
                pixels = list(img_small.getdata())
                r_vals = [p[0] for p in pixels]
                g_vals = [p[1] for p in pixels]
                b_vals = [p[2] for p in pixels]
                
                r_mean = sum(r_vals) / len(r_vals)
                g_mean = sum(g_vals) / len(g_vals)
                b_mean = sum(b_vals) / len(b_vals)
                
                # 计算颜色方差（复杂度）
                r_var = sum((r - r_mean) ** 2 for r in r_vals) / len(r_vals)
                g_var = sum((g - g_mean) ** 2 for g in g_vals) / len(g_vals)
                b_var = sum((b - b_mean) ** 2 for b in b_vals) / len(b_vals)
                
                color_variance = (r_var + g_var + b_var) / 3
                
                # 基于颜色分布简单分类场景
                if g_mean > r_mean and g_mean > b_mean:
                    if g_mean > 150:
                        return "自然场景"
                    else:
                        return "森林或草地"
                elif b_mean > r_mean and b_mean > g_mean:
                    if b_mean > 150:
                        return "天空或水域"
                    else:
                        return "夜景或海洋"
                elif r_mean > 150 and g_mean > 150 and b_mean > 150:
                    return "明亮场景"
                elif r_mean < 60 and g_mean < 60 and b_mean < 60:
                    return "暗色场景"
                elif color_variance > 1500:
                    return "复杂场景"
                else:
                    return "一般场景"
        
        except Exception as e:
            self.logger.error(f"场景分类错误: {str(e)}")
            return "未知场景"
    
    def _detect_image_text(self, image_path):
        """检测图片中的文本 (OCR)"""
        try:
            # 1. 尝试使用Tesseract OCR
            ocr_text = self._extract_text_with_tesseract(image_path)
            
            # 构建结果
            ocr_result = {
                "detected_text": ocr_text if ocr_text else "(未检测到文本)",
                "text_detected": bool(ocr_text),
                "text_length": len(ocr_text) if ocr_text else 0
            }
            
            # 添加描述
            if ocr_text:
                ocr_result["description"] = f"图像中检测到约{len(ocr_text)}个字符的文本。"
                # 文本前100个字符作为预览
                ocr_result["preview"] = ocr_text[:100] + ("..." if len(ocr_text) > 100 else "")
            else:
                ocr_result["description"] = "图像中未检测到明显文本内容。"
            
            return ocr_result
            
        except Exception as e:
            self.logger.error(f"OCR文本检测错误: {str(e)}")
            return {"error": str(e), "detected_text": "", "text_detected": False}
    
    def _extract_text_with_tesseract(self, image_path):
        """使用Tesseract OCR提取图像中的文本"""
        try:
            # 检查pytesseract是否已安装
            try:
                import pytesseract
                from PIL import Image
            except ImportError as e:
                self.logger.warning(f"OCR依赖未安装: {str(e)}")
                return """【注意：要使用OCR功能，请安装以下依赖：
1. 安装Tesseract OCR引擎:
   - Windows: 下载安装包 https://github.com/UB-Mannheim/tesseract/wiki
   - Linux: sudo apt-get install tesseract-ocr
   - macOS: brew install tesseract
   
2. 安装Python包:
   pip install pytesseract Pillow

3. 确保Tesseract已添加到系统PATH】"""
            
            # 检查Tesseract是否可用
            try:
                pytesseract.get_tesseract_version()
            except Exception as e:
                self.logger.warning(f"Tesseract OCR未正确配置: {str(e)}")
                return """【Tesseract OCR未正确配置。请检查：
1. Tesseract是否已正确安装
2. Tesseract是否已添加到系统PATH
3. 如果使用Windows，可能需要手动设置:
   pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'】"""
            
            # 加载图像并预处理
            image = Image.open(image_path)
            
            # 尝试识别文本
            try:
                # 首先尝试自动检测语言
                text = pytesseract.image_to_string(image)
                
                if not text.strip():
                    # 如果没有识别出文本，尝试使用中文识别
                    text = pytesseract.image_to_string(image, lang='chi_sim')
                    
                    if not text.strip():
                        # 如果仍然没有识别出文本，尝试只识别数字
                        text = pytesseract.image_to_string(image, config='--psm 6 digits')
                
                return text.strip() if text.strip() else "【未能识别出任何文本】"
                
            except Exception as e:
                self.logger.error(f"OCR识别过程出错: {str(e)}")
                return f"【OCR识别失败: {str(e)}】"
            
        except Exception as e:
            self.logger.error(f"OCR处理过程出错: {str(e)}")
            return f"【OCR处理失败: {str(e)}】"
    
    def _analyze_image_colors(self, img):
        """分析图片的色彩特征"""
        try:
            # 转换为RGB模式以便分析颜色
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # 缩小图片以加速处理
            img_small = img.resize((100, 100))
            pixels = list(img_small.getdata())
            
            # 计算平均颜色
            avg_r = sum(p[0] for p in pixels) // len(pixels)
            avg_g = sum(p[1] for p in pixels) // len(pixels)
            avg_b = sum(p[2] for p in pixels) // len(pixels)
            
            # 计算亮度
            brightness = (0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b)
            
            # 找出主要颜色 (简化版)
            colors = {}
            for pixel in pixels:
                # 简化颜色值，将相近的颜色归为一组
                simple_pixel = (pixel[0]//32*32, pixel[1]//32*32, pixel[2]//32*32)
                if simple_pixel in colors:
                    colors[simple_pixel] += 1
                else:
                    colors[simple_pixel] = 1
                    
            # 获取出现次数最多的颜色
            main_color = max(colors.items(), key=lambda x: x[1])[0]
            main_color_hex = "#{:02x}{:02x}{:02x}".format(main_color[0], main_color[1], main_color[2])
            
            # 计算饱和度 (简化计算)
            r, g, b = avg_r/255, avg_g/255, avg_b/255
            max_rgb = max(r, g, b)
            min_rgb = min(r, g, b)
            if max_rgb == 0:
                saturation = 0
            else:
                saturation = (max_rgb - min_rgb) / max_rgb
                
            return {
                "avg_color": {
                    "r": avg_r,
                    "g": avg_g,
                    "b": avg_b,
                    "hex": "#{:02x}{:02x}{:02x}".format(avg_r, avg_g, avg_b)
                },
                "main_color": main_color_hex,
                "brightness": int(brightness),
                "saturation": round(saturation, 2)
            }
            
        except Exception as e:
            self.logger.error(f"分析图片颜色时出错: {str(e)}")
            return {"error": f"分析图片颜色时出错: {str(e)}"}
    
    def _analyze_image_content(self, img):
        """分析图片的内容特征"""
        try:
            # 转换为灰度图以便进行边缘检测
            if img.mode != "L":
                img_gray = img.convert("L")
            else:
                img_gray = img
                
            # 缩小图片以加速处理
            img_small = img_gray.resize((200, int(200 * img.height / img.width)))
            
            # 简单的边缘检测 (使用简化的Sobel算子)
            width, height = img_small.size
            edge_count = 0
            
            # 使用numpy进行更高效的边缘检测
            import numpy as np
            from scipy import ndimage
            
            # 转换为numpy数组
            img_array = np.array(img_small)
            
            # 应用Sobel算子
            sobel_x = ndimage.sobel(img_array, axis=0)
            sobel_y = ndimage.sobel(img_array, axis=1)
            
            # 计算梯度幅值
            magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            
            # 计算超过阈值的边缘点数量
            threshold = np.mean(magnitude) * 1.5
            edge_count = np.sum(magnitude > threshold)
            
            # 计算复杂度 (边缘点占比)
            complexity = edge_count / (width * height)
            
            # 根据复杂度分级
            if complexity < 0.05:
                complexity_level = "低"
            elif complexity < 0.15:
                complexity_level = "中"
            else:
                complexity_level = "高"
            
            return {
                "complexity": complexity_level,
                "complexity_value": round(complexity, 3),
                "edge_count": int(edge_count),
                "threshold": float(threshold)
            }
            
        except Exception as e:
            self.logger.error(f"分析图片内容时出错: {str(e)}")
            return {"error": f"分析图片内容时出错: {str(e)}"}
    
    def _analyze_video(self, video_path):
        """分析视频，提取元数据和内容特征"""
        try:
            # 使用ffprobe提取视频元数据
            command = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            
            try:
                # 使用二进制模式读取输出，解决编码问题
                result = subprocess.run(command, capture_output=True, check=True)
                # 使用utf-8解码，忽略错误
                output_text = result.stdout.decode('utf-8', errors='ignore')
                if output_text.strip():
                    metadata = json.loads(output_text)
                else:
                    self.logger.error("ffprobe输出为空")
                    metadata = {"format": {}, "streams": []}
            except (subprocess.SubprocessError, json.JSONDecodeError) as e:
                self.logger.error(f"提取视频元数据时出错: {str(e)}")
                # 如果ffprobe失败，回退到基本信息
                return {"message": "无法提取视频详细信息，请确保安装了ffmpeg"}
            
            # 提取关键信息
            video_info = {"streams": []}
            
            # 格式信息
            if "format" in metadata:
                format_info = metadata["format"]
                duration = float(format_info.get("duration", 0))
                
                video_info.update({
                    "duration": duration,
                    "duration_formatted": self._format_duration(duration),
                    "bit_rate": int(format_info.get("bit_rate", 0)),
                    "size": int(format_info.get("size", 0)),
                    "format_name": format_info.get("format_name", "unknown")
                })
            
            # 提取视频和音频流信息
            video_stream = None
            audio_stream = None
            
            if "streams" in metadata:
                for stream in metadata["streams"]:
                    codec_type = stream.get("codec_type")
                    stream_info = {
                        "codec_type": codec_type,
                        "codec_name": stream.get("codec_name"),
                        "codec_long_name": stream.get("codec_long_name")
                    }
                    
                    if codec_type == "video" and not video_stream:
                        video_stream = stream
                        stream_info.update({
                            "width": stream.get("width"),
                            "height": stream.get("height"),
                            "display_aspect_ratio": stream.get("display_aspect_ratio", "N/A"),
                            "pix_fmt": stream.get("pix_fmt"),
                            "r_frame_rate": stream.get("r_frame_rate", "N/A")
                        })
                        
                        # 计算帧率
                        fps = stream.get("r_frame_rate", "")
                        if fps and "/" in fps:
                            num, den = map(int, fps.split("/"))
                            if den > 0:
                                stream_info["frame_rate"] = round(num / den, 2)
                    
                    elif codec_type == "audio" and not audio_stream:
                        audio_stream = stream
                        stream_info.update({
                            "sample_rate": stream.get("sample_rate"),
                            "channels": stream.get("channels"),
                            "channel_layout": stream.get("channel_layout", "N/A"),
                            "bit_rate": stream.get("bit_rate", "N/A")
                        })
                    
                    video_info["streams"].append(stream_info)
            
            # 提取视频主流信息到顶层
            if video_stream:
                video_info.update({
                    "width": video_stream.get("width"),
                    "height": video_stream.get("height"),
                    "codec": video_stream.get("codec_name")
                })
                # 安全地计算帧率
                try:
                    frame_rate_str = video_stream.get("r_frame_rate", "25/1")
                    if "/" in frame_rate_str:
                        num, den = map(int, frame_rate_str.split("/"))
                        if den > 0:
                            video_info["frame_rate"] = round(num / den, 2)
                    else:
                        video_info["frame_rate"] = float(frame_rate_str)
                except:
                    video_info["frame_rate"] = 25.0  # 默认值
            
            # 生成视频缩略图和提取关键帧
            try:
                # 提取多个关键帧进行分析
                frame_info = self._extract_video_frames(video_path, duration)
                if frame_info:
                    video_info["frames"] = frame_info
            except Exception as e:
                self.logger.error(f"提取视频帧时出错: {str(e)}")
            
            # 提取视频内容描述
            try:
                content_description = self._analyze_video_content(video_path)
                if content_description:
                    video_info["content_description"] = content_description
            except Exception as e:
                self.logger.error(f"分析视频内容时出错: {str(e)}")
            
            # 提取音频内容（如果有）
            if audio_stream:
                try:
                    audio_text = self._extract_video_audio(video_path)
                    if audio_text:
                        video_info["audio_transcription"] = audio_text
                except Exception as e:
                    self.logger.error(f"提取视频音频内容时出错: {str(e)}")
            
            return video_info
            
        except Exception as e:
            self.logger.error(f"分析视频时出错: {str(e)}")
            return {"error": f"分析视频时出错: {str(e)}"}
    
    def _extract_video_frames(self, video_path, duration):
        """提取视频的多个关键帧并分析"""
        frames_info = []
        
        try:
            # 确定要提取的帧的时间点（视频开始、25%、50%、75%和结束前）
            timestamps = [
                1,  # 开始（略过真正的开始防止黑屏）
                max(1, int(duration * 0.25)),
                max(1, int(duration * 0.5)),
                max(1, int(duration * 0.75)),
                max(1, int(duration - 1))  # 结束前1秒
            ]
            
            for i, timestamp in enumerate(timestamps):
                # 创建临时文件名
                frame_path = os.path.join(
                    tempfile.gettempdir(),
                    f"frame_{i}_{os.path.basename(video_path)}.jpg"
                )
                
                # 使用ffmpeg提取指定时间的帧
                command = [
                    "ffmpeg",
                    "-i", video_path,
                    "-ss", str(timestamp),
                    "-frames:v", "1",
                    "-q:v", "2",
                    "-y",
                    frame_path
                ]
                
                subprocess.run(command, capture_output=True, check=True)
                
                if os.path.exists(frame_path):
                    # 分析帧图像
                    frame_analysis = self._analyze_image(frame_path)
                    frame_analysis["timestamp"] = timestamp
                    frame_analysis["timestamp_formatted"] = self._format_duration(timestamp)
                    frames_info.append(frame_analysis)
                    
                    # 保留文件路径以便后续显示
                    frame_analysis["path"] = frame_path
            
            return frames_info
        
        except Exception as e:
            self.logger.error(f"提取视频帧时出错: {str(e)}")
            return None
    
    def _analyze_video_content(self, video_path):
        """分析视频内容，使用大模型API进行关键帧分析"""
        try:
            # 提取视频帧
            video_info = self._analyze_video(video_path)
            duration = video_info.get('duration', 0)
            
            # 提取关键帧（开始、中间、结束）
            frames = self._extract_video_frames(video_path, duration)
            
            if not frames:
                return {"error": "无法提取视频帧", "content_type": "video"}
            
            # 分析关键帧内容
            frame_analyses = []
            
            for i, frame_path in enumerate(frames):
                if os.path.exists(frame_path):
                    # 使用图像内容识别功能分析帧
                    frame_analysis = self._recognize_image_content(frame_path)
                    frame_analysis["frame_position"] = ["开始", "中间", "结束"][min(i, 2)]
                    frame_analysis["frame_path"] = frame_path
                    frame_analyses.append(frame_analysis)
            
            # 提取音频并分析（使用本地Whisper）
            audio_analysis = {}
            try:
                audio_path = self._extract_video_audio(video_path)
                if audio_path and os.path.exists(audio_path):
                    # 使用Whisper进行音频转文本
                    transcription = self._transcribe_audio(audio_path)
                    if transcription:
                        audio_analysis = {
                            "has_speech": True,
                            "transcription": transcription,
                            "language": self._detect_language(transcription)
                        }
                    else:
                        audio_analysis = {"has_speech": False}
            except Exception as e:
                self.logger.error(f"分析视频音频时出错: {str(e)}")
                audio_analysis = {"error": str(e)}
            
            # 生成缩略图
            thumbnail_path = self._generate_video_thumbnail(video_path)
            
            # 整合分析结果
            content_analysis = {
                "frames": frame_analyses,
                "audio": audio_analysis,
                "thumbnail": thumbnail_path
            }
            
            # 生成总体描述
            main_objects = set()
            scene_types = set()
            
            for frame in frame_analyses:
                if "objects" in frame:
                    main_objects.update(frame.get("objects", [])[:3])
                if "scene_type" in frame:
                    scene_types.add(frame.get("scene_type", ""))
            
            # 构建描述
            main_objects_list = list(main_objects)[:5]  # 最多取5个主要对象
            scene_types_list = list(scene_types)
            
            description = f"这是一个{video_info.get('duration_formatted', '未知时长')}的视频，"
            
            if main_objects_list:
                description += f"内容包含：{', '.join(main_objects_list)}。"
            
            if scene_types_list:
                description += f"场景类型：{', '.join(scene_types_list)}。"
            
            if audio_analysis.get("has_speech", False):
                description += f"包含{audio_analysis.get('language', '未知语言')}语音内容。"
            
            content_analysis["description"] = description
            
            return content_analysis
        
        except Exception as e:
            self.logger.error(f"分析视频内容时出错: {str(e)}", exc_info=True)
            return {"error": str(e), "content_type": "video"}
    
    def _extract_video_audio(self, video_path):
        """从视频中提取音频并转录"""
        try:
            # 创建临时音频文件
            temp_audio = os.path.join(
                tempfile.gettempdir(),
                f"audio_{os.path.basename(video_path)}.wav"
            )
            
            # 提取音频轨道
            extract_cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # 不要视频
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                temp_audio
            ]
            
            subprocess.run(extract_cmd, capture_output=True, check=True)
            
            # 模拟音频转文字结果
            # 注意：实际应用中，应调用语音识别API
            transcription = "此处为视频中音频内容的文字记录。实际应用中，应当调用语音识别API进行转写。"
            
            # 清理临时文件
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
                
            return transcription
            
        except Exception as e:
            self.logger.error(f"提取视频音频内容时出错: {str(e)}")
            return None
    
    def _generate_video_thumbnail(self, video_path):
        """从视频中提取缩略图"""
        try:
            # 创建临时文件名
            thumbnail_path = os.path.join(
                tempfile.gettempdir(),
                f"video_thumb_{os.path.basename(video_path)}.jpg"
            )
            
            # 使用ffmpeg截取视频第5秒的帧作为缩略图
            command = [
                "ffmpeg",
                "-i", video_path,
                "-ss", "00:00:05",
                "-frames:v", "1",
                "-q:v", "2",
                "-vf", "scale=320:-1",
                thumbnail_path
            ]
            
            subprocess.run(command, capture_output=True, check=True)
            
            if os.path.exists(thumbnail_path):
                return thumbnail_path
                
        except Exception as e:
            self.logger.error(f"生成视频缩略图时出错: {str(e)}")
            
        return None
    
    def _analyze_audio(self, audio_path):
        """分析音频文件"""
        try:
            # 获取文件信息
            file_info = self._get_file_info(audio_path)
            
            # 使用ffmpeg获取音频信息
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-f', 'null', '-'
            ]
            
            # 使用utf-8编码处理输出
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace'
            )
            
            _, stderr = process.communicate()
            
            # 解析音频信息
            duration = 0
            format_info = {}
            
            # 从stderr中提取信息
            for line in stderr.split('\n'):
                if 'Duration:' in line:
                    time_str = line.split('Duration:')[1].split(',')[0].strip()
                    h, m, s = map(float, time_str.split(':'))
                    duration = h * 3600 + m * 60 + s
                elif 'Stream' in line and 'Audio:' in line:
                    format_info = {
                        'codec': line.split('Audio:')[1].split()[0] if 'Audio:' in line else 'unknown',
                        'sample_rate': line.split('Hz')[0].split()[-1] if 'Hz' in line else 'unknown',
                        'channels': line.split('channels')[0].split()[-1] if 'channels' in line else 'unknown'
                    }
            
            # 使用whisper进行语音转文字
            try:
                import whisper
                logger.info("使用Whisper模型进行语音识别...")
                
                # 加载模型
                model = whisper.load_model("base")
                
                # 转录音频
                transcription_result = model.transcribe(audio_path)
                transcription = transcription_result["text"]
                detected_language = transcription_result.get("language", "unknown")
                
                logger.info(f"语音识别完成，检测到语言: {detected_language}")
                logger.info(f"转录文本: {transcription}")
                
                # 使用AI服务分析转录文本
                ai_service = AIService()
                if ai_service._check_api_available():
                    logger.info("使用AI服务分析音频内容...")
                    ai_analysis = ai_service.analyze_text(transcription)
                else:
                    logger.warning("AI服务不可用，跳过内容分析")
                    ai_analysis = None
                
            except ImportError:
                logger.warning("Whisper未安装，无法进行语音识别")
                transcription = "【需要安装whisper才能进行语音识别。请使用 'pip install openai-whisper' 安装】"
                detected_language = "unknown"
                ai_analysis = None
            except Exception as e:
                logger.error(f"语音识别过程中出错: {str(e)}")
                transcription = f"【语音识别失败: {str(e)}】"
                detected_language = "unknown"
                ai_analysis = None
            
            # 获取音频波形数据
            waveform_data = self._get_audio_waveform(audio_path)
            
            # 获取音频频谱数据
            spectrogram_data = self._get_audio_spectrogram(audio_path)
            
            # 构建分析结果
            result = {
                "content_type": "audio",
                "file_info": file_info,
                "audio_info": {
                    "duration": duration,
                    "duration_formatted": self._format_duration(duration),
                    "format": format_info.get('codec', 'unknown'),
                    "sample_rate": format_info.get('sample_rate', 'unknown'),
                    "channels": format_info.get('channels', 'unknown')
                },
                "transcription": {
                    "text": transcription,
                    "language": detected_language
                },
                "waveform": waveform_data,
                "spectrogram": spectrogram_data
            }
            
            # 添加AI分析结果（如果有）
            if ai_analysis:
                result["ai_analysis"] = ai_analysis
            
            return result
            
        except Exception as e:
            logger.error(f"分析音频内容时出错: {str(e)}")
            return {
                "error": f"分析失败: {str(e)}",
                "content_type": "audio",
                "file_info": self._get_file_info(audio_path) if os.path.exists(audio_path) else None
            }
            
    def _format_duration(self, seconds):
        """格式化持续时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _get_audio_waveform(self, audio_path):
        """获取音频波形数据"""
        try:
            # 使用ffmpeg提取音频数据
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-f', 'f32le',
                '-acodec', 'pcm_f32le',
                '-ar', '44100',
                '-ac', '1',
                '-'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace'
            )
            
            stdout, stderr = process.communicate()
            
            # 处理音频数据
            if stdout:
                # 将音频数据转换为波形数据
                audio_data = np.frombuffer(stdout.encode('utf-8'), dtype=np.float32)
                # 采样到1000个点
                waveform = np.interp(
                    np.linspace(0, len(audio_data)-1, 1000),
                    np.arange(len(audio_data)),
                    audio_data
                )
                return waveform.tolist()
            
            return None
            
        except Exception as e:
            logger.error(f"获取音频波形数据失败: {str(e)}")
            return None
            
    def _get_audio_spectrogram(self, audio_path):
        """获取音频频谱数据"""
        try:
            # 使用ffmpeg提取音频数据
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-f', 'f32le',
                '-acodec', 'pcm_f32le',
                '-ar', '44100',
                '-ac', '1',
                '-'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=None  # 使用二进制模式
            )
            
            stdout, stderr = process.communicate()
            
            # 处理音频数据
            if stdout:
                # 将音频数据转换为numpy数组
                audio_data = np.frombuffer(stdout, dtype=np.float32)
                
                # 计算需要多少个完整的块
                num_samples = len(audio_data)
                block_size = 1024
                num_blocks = num_samples // block_size
                
                if num_blocks == 0:
                    logger.warning("音频数据太短，无法生成频谱图")
                    return None
                
                # 只使用完整的块
                audio_data = audio_data[:num_blocks * block_size]
                
                # 重塑数组为二维形式
                audio_blocks = audio_data.reshape(-1, block_size)
                
                # 计算每个块的FFT
                spectrogram = np.abs(np.fft.fft(audio_blocks, axis=1))
                
                # 取对数来增强可视化效果
                spectrogram = np.log10(spectrogram + 1)
                
                # 如果频谱图太大，进行降采样
                if spectrogram.shape[0] > 100:
                    # 在时间轴上进行降采样
                    indices = np.linspace(0, spectrogram.shape[0]-1, 100, dtype=int)
                    spectrogram = spectrogram[indices]
                
                if spectrogram.shape[1] > 100:
                    # 在频率轴上进行降采样
                    indices = np.linspace(0, spectrogram.shape[1]-1, 100, dtype=int)
                    spectrogram = spectrogram[:, indices]
                
                # 标准化到0-1范围
                spectrogram = (spectrogram - spectrogram.min()) / (spectrogram.max() - spectrogram.min() + 1e-6)
                
                return spectrogram.tolist()
            
            return None
            
        except Exception as e:
            logger.error(f"获取音频频谱数据失败: {str(e)}")
            return None
    
    def _transcribe_audio(self, audio_path):
        """使用本地Whisper模型将音频转换为文本"""
        try:
            self.logger.info(f"使用本地Whisper模型转录音频: {audio_path}")
            
            # 检查文件是否存在
            if not os.path.exists(audio_path):
                self.logger.error(f"音频文件不存在: {audio_path}")
                return None
                
            # 确保whisper模块已安装
            try:
                import whisper
            except ImportError:
                self.logger.error("Whisper模块未安装，无法进行语音识别")
                # 返回提示信息
                return "【注意：需要安装whisper模块才能进行语音识别。请使用 'pip install openai-whisper' 安装】"
            
            # 尝试加载模型
            try:
                # 使用小模型以实现更快的转写速度，可选模型包括：
                # "tiny", "base", "small", "medium", "large"
                model_size = "base"
                
                # 检查是否存在环境变量指定模型大小
                env_model_size = os.getenv("WHISPER_MODEL_SIZE", "").lower()
                if env_model_size in ["tiny", "base", "small", "medium", "large"]:
                    model_size = env_model_size
                
                # 加载模型，首次运行会下载模型文件
                self.logger.info(f"加载Whisper {model_size}模型...")
                model = whisper.load_model(model_size)
                
                # 运行转录
                self.logger.info("正在转录音频...")
                result = model.transcribe(audio_path)
                
                transcription = result["text"]
                self.logger.info(f"音频转录成功，获取到{len(transcription)}字符的文本")
                
                # 返回转录结果
                return transcription
            except Exception as e:
                self.logger.error(f"加载Whisper模型或转录时出错: {str(e)}", exc_info=True)
                return f"【音频转录失败: {str(e)}】"
                
        except Exception as e:
            self.logger.error(f"音频转录过程中出错: {str(e)}", exc_info=True)
            return None

    def _detect_language(self, text):
        """检测文本语言，使用Whisper的语言检测功能"""
        if not text:
            return "未知"
            
        try:
            # 尝试使用whisper的语言检测
            try:
                import whisper
                
                # 加载小型模型进行语言检测
                model = whisper.load_model("tiny")
                
                # 使用whisper预处理音频并检测语言
                # 注意：这里我们尝试将文本转回语音，然后再检测，不是最优方法
                # 但whisper主要设计用于音频处理
                
                # 备选：使用语言检测库
                from langdetect import detect
                lang_code = detect(text)
                
                # 语言代码到中文名称的映射
                lang_map = {
                    'zh': '中文', 'en': '英语', 'ja': '日语', 'ko': '韩语',
                    'fr': '法语', 'de': '德语', 'es': '西班牙语', 'it': '意大利语',
                    'ru': '俄语', 'ar': '阿拉伯语', 'hi': '印地语', 'pt': '葡萄牙语',
                    'th': '泰语', 'vi': '越南语'
                }
                
                return lang_map.get(lang_code, f"其他({lang_code})")
                
            except (ImportError, Exception) as e:
                self.logger.warning(f"无法使用Whisper进行语言检测: {str(e)}")
                
                # 备选方法：使用langdetect库
                try:
                    from langdetect import detect
                    lang_code = detect(text)
                    
                    # 语言代码到中文名称的映射
                    lang_map = {
                        'zh-cn': '中文', 'zh-tw': '中文', 'zh': '中文', 
                        'en': '英语', 'ja': '日语', 'ko': '韩语',
                        'fr': '法语', 'de': '德语', 'es': '西班牙语', 'it': '意大利语',
                        'ru': '俄语', 'ar': '阿拉伯语', 'hi': '印地语', 'pt': '葡萄牙语',
                        'th': '泰语', 'vi': '越南语'
                    }
                    
                    return lang_map.get(lang_code, f"其他({lang_code})")
                except ImportError:
                    self.logger.warning("langdetect库未安装，无法进行语言检测")
                    
                    # 简单启发式方法
                    if any('\u4e00' <= char <= '\u9fff' for char in text):
                        return "中文"
                    elif all(ord(char) < 128 for char in text):
                        return "英语"
                    else:
                        return "其他语言"
                except Exception as e:
                    self.logger.error(f"语言检测失败: {str(e)}")
                    return "未知语言"
        except Exception as e:
            self.logger.error(f"语言检测过程中出错: {str(e)}")
            return "未知语言"

    def _format_size(self, size_bytes):
        """将字节大小转换为人类可读的格式"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"

    def _get_file_info(self, file_path):
        """获取文件基本信息"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return {
                    "error": "文件不存在",
                    "path": file_path
                }
            
            # 获取文件基本信息
            file_stats = os.stat(file_path)
            file_info = {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size": file_stats.st_size,
                "size_formatted": self._format_size(file_stats.st_size),
                "type": self._detect_type(file_path),
                "last_modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat()
            }
            
            return file_info
            
        except Exception as e:
            self.logger.error(f"获取文件信息时出错: {str(e)}")
            return {
                "error": f"获取文件信息失败: {str(e)}",
                "path": file_path
            }

class AIService:
    """AI服务处理类，负责与API交互或本地处理"""
    def __init__(self, api_key=None, api_base=None, model_name=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = api_base or os.getenv("OPENAI_API_BASE")
        self.model_name = model_name or os.getenv("OPENAI_MODEL_NAME")
        self.vision_model = os.getenv("OPENAI_VISION_MODEL")
        self.logger = logging.getLogger("ai_service")
        
        # 尝试导入openai库并设置配置
        try:
            import openai
            if self.api_key:
                openai.api_key = self.api_key
            if self.api_base:
                openai.base_url = self.api_base
            self.logger.info(f"OpenAI配置完成，API地址: {self.api_base}, 模型: {self.model_name}")
        except ImportError:
            self.logger.warning("无法导入openai库，请使用pip install openai安装")
    
    def _check_api_available(self):
        """检查API是否配置和可用"""
        if not self.api_key or self.api_key == "sk-example12345678":
            self.logger.warning("API密钥未配置或使用了示例密钥")
            return False
        return True   
       
    
    def analyze_text(self, text, analysis_type="general"):
        """分析文本内容，根据API可用性选择本地或API处理"""
        if self._check_api_available():
            return self._analyze_with_api(text, analysis_type)
        else:
            return self._analyze_locally(text, analysis_type)
            
    def analyze_image(self, image_path, prompt=None):
        """使用大模型分析图像内容"""
        try:
            if not os.path.exists(image_path):
                return {"error": "图像文件不存在", "success": False}
                
            # 检查API可用性
            if not self._check_api_available():
                return {"error": "API未配置或不可用", "success": False}
                
            # 默认提示词
            if not prompt:
                prompt = "分析这张图片中的内容，包括：1. 主要物体和对象；2. 场景类型；3. 图片主题。请用中文回答，格式为JSON，包含objects数组、scene_type字符串和description字符串字段。"
                
            # 使用openai库进行图像识别
            import openai
            import base64
            import json
            
            # 设置API密钥和基础URL
            openai.api_key = self.api_key
            if self.api_base:
                openai.base_url = self.api_base
            
            # 将图像转换为base64编码
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 使用vision模型
            self.logger.info(f"正在使用OpenAI Vision模型分析图像: {self.vision_model}")
            
            try:
                response = openai.chat.completions.create(
                    model=self.vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=500,
                    timeout=45  # 图像分析可能需要更长时间，设置45秒超时
                )
            except Exception as e:
                self.logger.error(f"使用OpenAI Vision模型分析图像时出错: {str(e)}", exc_info=True)
                return {"error": f"使用OpenAI Vision模型分析图像时出错: {str(e)}", "success": False}
            
            if response and hasattr(response, "choices") and len(response.choices) > 0:
                content = response.choices[0].message.content
                
                # 尝试解析JSON响应
                try:
                    # 提取JSON部分，处理可能的非JSON前缀或后缀
                    import re
                    json_match = re.search(r'({.*})', content, re.DOTALL)
                    if json_match:
                        content_json = json.loads(json_match.group(1))
                    else:
                        content_json = json.loads(content)
                        
                    # 返回解析结果
                    return {
                        "success": True,
                        "data": content_json,
                        "raw_response": content
                    }
                    
                except json.JSONDecodeError:
                    # 如果无法解析为JSON，返回原始文本
                    self.logger.warning(f"无法解析API响应为JSON: {content[:100]}...")
                    return {
                        "success": True,
                        "data": {"description": content},
                        "raw_response": content
                    }
            else:
                error_msg = f"API请求返回格式异常或为空"
                self.logger.error(error_msg)
                return {"error": error_msg, "success": False}
                
        except Exception as e:
            error_msg = f"分析图像时出错: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"error": error_msg, "success": False}

    def _analyze_with_api(self, text, analysis_type):
        """使用API分析文本内容"""
        try:
            # 设置API密钥和基础URL
            openai.api_key = self.api_key
            if self.api_base:
                openai.base_url = self.api_base
            
            # 清理和准备文本
            text_sample = text[:3000] if len(text) > 3000 else text
            
            # 根据分析类型构建提示
            if analysis_type == "summary":
                prompt = f"请对以下文本进行简要总结，提取关键信息和要点：\n\n{text_sample}"
            elif analysis_type == "keywords":
                prompt = f"请从以下文本中提取10个最重要的关键词或短语：\n\n{text_sample}"
            elif analysis_type == "sentiment":
                prompt = f"请分析以下文本的情感倾向(积极、消极或中性)并给出理由：\n\n{text_sample}"
            else:
                prompt = f"请分析以下文本并提供见解，包括主题、关键点、情感倾向；并指出不足之处，给出详细的改进建议：\n\n{text_sample}"
                
            # 记录API使用前提示
            self.logger.info(f"使用API分析文本，类型: {analysis_type}")
            
            # 使用openai库标准接口
            try:
                # 添加超时设置和重试机制
                response = openai.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一个专业的文本内容创作分析助手，擅长提取文本的关键信息、情感和主题，总是能准确的发现内容中的不足与缺陷，并给出改进，详细且恰当的建议。并且提供客观、详细的分析结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7,
                    timeout=60  # 设置30秒超时
                )
                self.logger.error(f"API分析结果: {response}")
                
                # 提取分析结果
                if response and hasattr(response, "choices") and len(response.choices) > 0:
                    # 获取消息内容，优先使用content，如果没有则使用reasoning_content
                    message = response.choices[0].message
                    analysis_text = message.content if message.content else message.reasoning_content
                    
                    if not analysis_text:
                        self.logger.warning("API返回的分析结果为空")
                        return {"error": "API返回的分析结果为空", "analysis_type": analysis_type, "method": "api_error"}
                    
                    # 构建结构化返回
                    result = {
                        "analysis": analysis_text,
                        "analysis_type": analysis_type,
                        "method": "api",
                        "model": self.model_name,
                        "text_length": len(text),
                        "sample_used": len(text) > 3000  # 标记是否使用了样本
                    }
                    
                    # 尝试提取特定分析类型的结构化数据
                    if analysis_type == "keywords":
                        # 尝试从结果中提取关键词
                        keywords = []
                        for line in analysis_text.split("\n"):
                            # 清理行
                            line = line.strip()
                            if line and any(c.isalnum() for c in line):
                                # 移除可能的序号和标点
                                cleaned = re.sub(r'^[\d\-\.\,\。]+[\s\.\,\。]+', '', line)
                                # 移除引号
                                cleaned = re.sub(r'[\'\"\"\"]+', '', cleaned)
                                keywords.append(cleaned.strip())
                        
                        result["keywords"] = keywords
                    
                    elif analysis_type == "sentiment":
                        # 尝试从结果中提取情感
                        sentiment = "neutral"  # 默认中性
                        if re.search(r'积极|正面|乐观|喜悦|开心|满意', analysis_text, re.I):
                            sentiment = "positive"
                        elif re.search(r'消极|负面|悲观|悲伤|不满|愤怒', analysis_text, re.I):
                            sentiment = "negative"
                        
                        result["sentiment"] = sentiment
                    
                    self.logger.error(f"API分析提取的结果: {result}")
                    return result
                
                # 处理API错误
                error_msg = f"API请求返回格式异常或为空"
                self.logger.error(error_msg)
                return {"error": error_msg, "analysis_type": analysis_type, "method": "api_error"}
                
            except Exception as e:
                self.logger.error(f"API分析错误: {str(e)}")
                return {"error": f"API分析错误: {str(e)}", "analysis_type": analysis_type}
                
        except Exception as e:
            self.logger.error(f"API分析错误: {str(e)}")
            return {"error": f"API分析错误: {str(e)}", "analysis_type": analysis_type}
    
    def _analyze_locally(self, text, analysis_type):
        """本地文本分析，不依赖API"""
        result = {
            "analysis_type": analysis_type,
            "method": "local"
        }
        
        try:
            # 根据分析类型进行不同的处理
            if analysis_type == "keywords":
                # 提取关键词
                keywords = self._extract_keywords(text)
                result["keywords"] = keywords
                result["analysis"] = f"从文本中提取了{len(keywords)}个关键词：" + "，".join(keywords[:10])
                
            elif analysis_type == "sentiment":
                # 情感分析
                sentiment, score = self._analyze_sentiment(text)
                result["sentiment"] = self._normalize_sentiment(sentiment)
                result["sentiment_score"] = score
                result["analysis"] = f"文本情感倾向: {sentiment}，置信度: {score:.2f}"
                
            else:
                # 通用分析
                # 提取关键词
                keywords = self._extract_keywords(text)
                result["keywords"] = keywords
                
                # 情感分析
                sentiment, score = self._analyze_sentiment(text)
                result["sentiment"] = self._normalize_sentiment(sentiment)
                result["sentiment_score"] = score
                
                # 生成综合分析
                result["analysis"] = f"文本长度: {len(text)} 字符\n"
                result["analysis"] += f"关键词: {', '.join(keywords[:5])}\n"
                result["analysis"] += f"情感倾向: {sentiment}\n"
                
                # 添加简单摘要
                summary = text[:200] + ("..." if len(text) > 200 else "")
                result["summary"] = summary
            
            return result
            
        except Exception as e:
            self.logger.error(f"本地分析错误: {str(e)}")
            return {"error": f"本地分析错误: {str(e)}", "analysis_type": analysis_type, "method": "local_error"}
    
    def _extract_keywords(self, text):
        """提取文本中的关键词"""
        try:
            # 尝试导入中文分词库
            try:
                import jieba
                import jieba.analyse
                
                # 使用jieba提取关键词
                keywords = jieba.analyse.extract_tags(text, topK=10)
                if keywords:
                    return keywords
            except ImportError:
                self.logger.warning("jieba库未安装，使用备选方法提取关键词")
            
            # 备选方法：简单词频统计
            # 清理文本
            clean_text = re.sub(r'[^\w\s]', '', text.lower())
            
            # 分词
            words = clean_text.split()
            
            # 移除常见停用词
            stop_words = set([
                'the', 'and', 'is', 'in', 'it', 'to', 'of', 'for', 'with', 'on', 'at', 'from',
                'by', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between',
                'out', 'against', 'during', 'without', 'before', 'under', 'around', 'among',
                '的', '了', '和', '是', '在', '我', '有', '你', '他', '她', '它', '们',
                '这', '那', '就', '都', '而', '及', '与', '或', '一', '不'
            ])
            
            filtered_words = [word for word in words if word not in stop_words and len(word) > 1]
            
            # 计算词频
            word_freq = {}
            for word in filtered_words:
                if word in word_freq:
                    word_freq[word] += 1
                else:
                    word_freq[word] = 1
            
            # 排序并返回前10个关键词
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, freq in sorted_words[:10]]
            
        except Exception as e:
            self.logger.error(f"提取关键词错误: {str(e)}")
            return ["分析失败"]
    
    def _analyze_sentiment(self, text):
        """分析文本情感倾向"""
        try:
            # 尝试使用NLTK的VADER进行情感分析
            try:
                from nltk.sentiment.vader import SentimentIntensityAnalyzer
                
                # 尝试初始化VADER分析器
                try:
                    sid = SentimentIntensityAnalyzer()
                    scores = sid.polarity_scores(text)
                    
                    # 根据compound分数确定情感
                    sentiment, score = None, None
                    if scores['compound'] >= 0.05:
                        sentiment, score = "积极", scores['compound']
                    elif scores['compound'] <= -0.05:
                        sentiment, score = "消极", abs(scores['compound'])
                    else:
                        sentiment, score = "中性", 0.5
                        
                    # 返回标准化结果
                    return self._normalize_sentiment(sentiment)
                        
                except Exception as e:
                    self.logger.warning(f"VADER情感分析失败: {str(e)}")
                    # 优雅地回退到简单情感分析
            except ImportError:
                self.logger.warning("NLTK VADER未安装，使用简单情感分析")
            
            # 简单的情感分析，通过计算积极和消极词的数量
            # 积极和消极词汇列表（简化版）
            positive_words = ['好', '喜欢', '棒', '赞', '优秀', '美', '爱', '开心', '快乐', '高兴', '精彩',
                             'good', 'great', 'excellent', 'like', 'love', 'happy', 'best', 'amazing']
            negative_words = ['差', '不好', '糟', '坏', '讨厌', '失望', '难过', '伤心', '痛苦', '恨', '烂',
                             'bad', 'worse', 'worst', 'hate', 'dislike', 'terrible', 'poor', 'awful']
            
            # 计算出现次数
            positive_count = sum(1 for word in positive_words if word in text.lower())
            negative_count = sum(1 for word in negative_words if word in text.lower())
            
            # 确定情感
            sentiment = None
            if positive_count > negative_count:
                sentiment = "积极"
            elif negative_count > positive_count:
                sentiment = "消极"
            else:
                sentiment = "中性"
                
            # 返回标准化结果
            return self._normalize_sentiment(sentiment)
                
        except Exception as e:
            self.logger.error(f"情感分析错误: {str(e)}")
            return 'unknown'
            
    def _normalize_sentiment(self, sentiment):
        """标准化情感结果"""
        # 映射中文情感标签到英文
        sentiment_map = {
            "积极": "positive",
            "消极": "negative",
            "中性": "neutral",
            "未知": "unknown"
        }
        
        return sentiment_map.get(sentiment, 'unknown')

    def get_suggestions(self, content_info, context=None):
        """根据内容分析结果提供相关建议"""
        if not content_info:
            return {"error": "未提供内容信息"}
            
        try:
            # 如果API可用，使用AI提供建议
            if self._check_api_available():
                return self._get_suggestions_with_api(content_info, context)
            else:
                # API不可用，使用本地处理
                self.logger.info("使用本地方法生成建议")
                return self._get_mock_suggestions(content_info)
                
        except Exception as e:
            self.logger.error(f"生成建议时出错: {str(e)}")
            return {"error": f"生成建议时出错: {str(e)}"}
    
    def _get_suggestions_with_api(self, content_info, context=None):
        """使用API生成内容建议"""
        try:
            import openai
            import json
            
            # 设置API密钥和基础URL
            openai.api_key = self.api_key
            if self.api_base != "https://api.openai.com/v1":
                openai.base_url = self.api_base
            
            # 构建基于内容信息的提示
            content_type = content_info.get("content_type", "unknown")
            prompt = f"基于以下{content_type}分析信息，提供3-5条改进或利用该内容的建议:\n\n"
            
            # 添加内容基本信息到提示
            if content_type == "text":
                if "keywords" in content_info:
                    prompt += f"关键词: {', '.join(content_info['keywords'])}\n"
                if "sentiment" in content_info:
                    prompt += f"情感倾向: {content_info['sentiment']}\n"
                if "language" in content_info:
                    prompt += f"语言: {content_info['language']}\n"
                if "summary" in content_info:
                    prompt += f"摘要: {content_info['summary']}\n"
            
            elif content_type == "image":
                if "content" in content_info and "objects" in content_info["content"]:
                    prompt += f"图像中的对象: {', '.join(content_info['content']['objects'])}\n"
                if "content" in content_info and "scene_type" in content_info["content"]:
                    prompt += f"场景类型: {content_info['content']['scene_type']}\n"
            
            elif content_type in ["audio", "video"]:
                if "transcription" in content_info:
                    prompt += f"语音内容: {content_info['transcription'][:500]}...\n"
            
            # 添加特定上下文
            if context:
                prompt += f"\n特定上下文或目标: {context}\n"
            
            self.logger.info(f"使用API生成{content_type}内容建议")
            
            # 调用API发送请求
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个内容分析专家，可以针对不同类型的内容提供具体、个性化的建议。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7,
                timeout=40  # 建议生成可能需要更长时间
            )
            
            # 处理响应结果
            if response and hasattr(response, "choices") and len(response.choices) > 0:
                suggestions_text = response.choices[0].message.content.strip()
                
                # 提取建议
                suggestions_list = []
                for line in suggestions_text.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("建议"):
                        # 清理格式
                        cleaned = re.sub(r'^[\d\-\.\*]+[\s\.\,\。]+', '', line)
                        if cleaned:
                            suggestions_list.append(cleaned)
                
                # 返回结果
                return {
                    "success": True,
                    "suggestions": suggestions_list,
                    "raw_response": suggestions_text,
                    "source": "api",
                    "content_type": content_type
                }
            else:
                self.logger.warning(f"API请求返回格式异常或为空")
                return self._get_mock_suggestions(content_info)
                
        except Exception as e:
            self.logger.error(f"API生成建议错误: {str(e)}")
            return self._get_mock_suggestions(content_info)
    
    def _get_mock_suggestions(self, content_info):
        """生成模拟的内容建议"""
        try:
            # 根据内容类型生成不同的建议
            content_type = content_info.get("content_type", "unknown")
            
            suggestions = {
                "method": "local",
                "quality_score": 7.5,  # 模拟质量评分
            }
            
            if content_type == "text":
                # 文本内容建议
                suggestions["suggestions"] = """
内容质量评估：
- 文本内容整体质量良好
- 文本结构清晰，便于阅读理解

改进建议：
- 考虑添加小标题或分段，提高可读性
- 可以添加一些相关的图表或图像，使内容更加生动
- 检查是否有拼写或语法错误

相关主题或资源推荐：
- 基于内容主题，可以扩展阅读相关学术论文或书籍
- 考虑使用更多的例子来支持论点
                """
                
            elif content_type == "image":
                # 图像内容建议
                suggestions["suggestions"] = """
内容质量评估：
- 图像质量尚可，清晰度适中
- 主体内容表现明确

改进建议：
- 考虑调整图像亮度和对比度，使主体更加突出
- 可以尝试不同的裁剪比例，强调关键元素
- 添加适当的文字说明或标注，增强信息传递

相关主题或资源推荐：
- 考虑使用专业图像编辑工具进行后期处理
- 探索相似主题的其他视觉表现形式
                """
                
            elif content_type == "audio":
                # 音频内容建议
                suggestions["suggestions"] = """
内容质量评估：
- 音频质量一般，可能存在背景噪音
- 内容表达清晰度有待提高

改进建议：
- 考虑使用降噪处理，提高音频质量
- 适当调整音量平衡，使声音更加清晰
- 可以添加字幕或文字记录，增强可访问性

相关主题或资源推荐：
- 探索专业录音设备或环境，提高原始音频质量
- 考虑使用专业音频编辑软件进行后期处理
                """
                
            elif content_type == "video":
                # 视频内容建议
                suggestions["suggestions"] = """
内容质量评估：
- 视频整体质量适中，内容表现明确
- 画面稳定性和清晰度有提升空间

改进建议：
- 考虑提高视频分辨率，增强画面清晰度
- 改善光线条件，使画面更加明亮和清晰
- 添加字幕或文字说明，增强内容表达
- 考虑使用专业的转场效果和视觉特效

相关主题或资源推荐：
- 探索专业视频剪辑软件，提升后期制作质量
- 学习基本的摄影和构图技巧，提高原始素材质量
                """
                
            else:
                # 未知类型的通用建议
                suggestions["suggestions"] = """
内容质量评估：
- 内容完整性良好，主题表达清晰
- 整体质量适中，有提升空间

改进建议：
- 考虑明确内容的目标受众，使表达更加针对性
- 适当添加视觉元素或多媒体内容，增强表现力
- 保持内容简洁明了，避免不必要的冗长

相关主题或资源推荐：
- 探索相关领域的专业资源和工具
- 学习行业最佳实践，提升内容整体质量
                """
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"生成模拟建议错误: {str(e)}")
            return {
                "error": f"生成建议时出错: {str(e)}",
                "method": "local",
                "suggestions": "无法生成建议。请检查内容信息是否完整。"
            }

class ContentProcessor:
    """内容处理器，负责处理不同类型的内容分析"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        初始化内容处理器
        
        Args:
            temp_dir: 临时文件目录
        """
        self.temp_dir = temp_dir or os.environ.get("TEMP_FILE_DIR") or tempfile.gettempdir()
        self.text_analyzer = TextAnalyzer()
        self.media_processor = MediaProcessor()
        
        # 确保临时目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"内容处理器初始化完成，临时目录: {self.temp_dir}")
    
    def process_content(self, content_path: Union[str, Path]) -> Dict[str, Any]:
        """
        处理内容，自动检测类型并进行分析
        
        Args:
            content_path: 内容路径，可以是文件路径或URL
            
        Returns:
            分析结果字典
        """
        logger.info(f"处理内容: {content_path}")
        
        try:
            # 检查是否是文件路径
            if os.path.exists(content_path):
                # 使用MediaProcessor分析文件
                content_type = self.media_processor._detect_type(content_path)
                
                # 根据类型处理
                if content_type.startswith("image/"):
                    # 图像处理
                    return self.media_processor.analyze(content_path)
                    
                elif content_type.startswith("video/"):
                    # 视频处理
                    return self.media_processor.analyze(content_path)
                    
                elif content_type.startswith("audio/"):
                    # 音频处理
                    return self.media_processor.analyze(content_path)
                    
                elif content_type == "text" or content_type.startswith("text/"):
                    # 文本处理
                    file_analysis = self.media_processor.analyze(content_path)
                    
                    # 如果MediaProcessor处理成功，添加TextAnalyzer的结果
                    if "text_info" in file_analysis and "preview" in file_analysis["text_info"]:
                        text_content = file_analysis["text_info"]["preview"]
                        text_analysis = self.text_analyzer.analyze(text_content=text_content)
                        file_analysis["analysis"] = text_analysis
                    
                    return file_analysis
                    
                else:
                    # 其他类型，使用MediaProcessor的基本分析
                    return self.media_processor.analyze(content_path)
            
            # 检查是否是URL
            elif content_path.startswith(('http://', 'https://')):
                # URL处理逻辑
                return {"error": "URL处理尚未实现"}
            
            else:
                # 不支持的内容类型
                return {"error": "不支持的内容类型或路径不存在"}
                
        except Exception as e:
            logger.error(f"处理内容时出错: {str(e)}")
            return {"error": f"处理内容时出错: {str(e)}", "content_type": "未知"}
    
    def process_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        处理单个文件，返回分析结果
        
        Args:
            file_path: 文件路径
            
        Returns:
            分析结果字典
        """
        logger.info(f"处理内容: {file_path}")
        
        try:
            # 检查文件是否存在
            if not os.path.isfile(file_path):
                logger.error(f"文件不存在: {file_path}")
                return {"error": "文件不存在"}
            
            # 使用MediaProcessor分析文件
            file_analysis = self.media_processor.analyze(file_path)
            
            # 处理特定文件类型的内容
            file_type = file_analysis.get("file_info", {}).get("type", "")
            
            if file_type == "text" or (file_type.startswith("text/") and "text_info" in file_analysis):
                # 文本文件 - 使用TextAnalyzer进行分析
                text_content = file_analysis.get("text_info", {}).get("preview", "")
                text_analysis = self.text_analyzer.analyze(text_content=text_content)
                file_analysis["analysis"] = text_analysis
                
            elif file_type.startswith("image/"):
                # 图像内容分析已在MediaProcessor中完成
                pass
                
            elif file_type.startswith("audio/"):
                # 音频内容已在MediaProcessor中完成
                pass
                
            elif file_type.startswith("video/"):
                # 视频内容已在MediaProcessor中完成
                pass
                
            # 返回最终分析结果
            return file_analysis
            
        except Exception as e:
            logger.error(f"处理文件时发生错误: {str(e)}")
            return {"error": f"处理文件时出错: {str(e)}"}
    
    def export_results(self, results: Dict[str, Any], output_format: str = 'json') -> str:
        """
        导出处理结果
        
        Args:
            results: 处理结果
            output_format: 输出格式 (json, html, text)
            
        Returns:
            导出文件路径
        """
        logger.info(f"导出结果为 {output_format} 格式")
        
        try:
            # 创建导出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"analysis_results_{timestamp}.{output_format}"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            # 根据输出格式导出结果
            if output_format == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                    
            elif output_format == 'html':
                # 简单HTML报告
                html_content = f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>内容分析报告</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        h1 {{ color: #2c3e50; }}
                        .section {{ margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; }}
                        .key {{ font-weight: bold; color: #16a085; }}
                    </style>
                </head>
                <body>
                    <h1>内容分析报告</h1>
                    <div class="section">
                        <pre>{json.dumps(results, ensure_ascii=False, indent=2)}</pre>
                    </div>
                </body>
                </html>"""
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                    
            elif output_format == 'text':
                # 简单文本报告
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("内容分析报告\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # 递归函数用于展平复杂字典
                    def write_dict(d, prefix=''):
                        for k, v in d.items():
                            if isinstance(v, dict):
                                f.write(f"{prefix}{k}:\n")
                                write_dict(v, prefix + '  ')
                            elif isinstance(v, list):
                                f.write(f"{prefix}{k}: {', '.join(map(str, v))}\n")
                            else:
                                f.write(f"{prefix}{k}: {v}\n")
                    
                    write_dict(results)
            else:
                logger.warning(f"不支持的输出格式: {output_format}")
                output_path = None
                
            return output_path
            
        except Exception as e:
            logger.error(f"导出结果时出错: {str(e)}", exc_info=True)
            return None
    
    def generate_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成分析报告
        
        Args:
            results: 处理结果列表
            
        Returns:
            报告字典
        """
        logger.info(f"生成处理结果报告，包含 {len(results)} 项")
        
        try:
            # 统计内容类型分布
            content_types = {}
            for r in results:
                content_type = r.get('content_type', 'unknown')
                content_types[content_type] = content_types.get(content_type, 0) + 1
            
            # 简单统计
            report = {
                "total_items": len(results),
                "content_type_distribution": content_types,
                "generated_at": datetime.now().isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"生成报告时出错: {str(e)}", exc_info=True)
            return {"error": str(e)}

class MultimodalAssistant:
    """多模态内容助手主类,整合内容处理和AI服务"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        初始化多模态内容助手
        
        Args:
            temp_dir: 临时文件目录
        """
        self.temp_dir = temp_dir or os.environ.get("TEMP_FILE_DIR") or tempfile.gettempdir()
        self.content_processor = ContentProcessor(self.temp_dir)
        self.ai_service = AIService(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 确保临时目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"多模态内容助手初始化完成，临时目录: {self.temp_dir}")
    
    def process_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            处理结果字典
        """
        logger.info(f"处理文件: {file_path}")
        
        try:
            content_analysis = self.content_processor.process_file(file_path)
            
            # 根据文件类型使用AI服务生成建议
            file_type = content_analysis.get("file_info", {}).get("type", "")
            
            try:
                if file_type.startswith("image/"):
                    # 图像文件，使用图像分析
                    ai_analysis = self.ai_service.analyze_image(file_path)
                    content_analysis["ai_analysis"] = ai_analysis
                elif "text_info" in content_analysis:
                    # 文本文件，使用文本分析
                    if "analysis" in content_analysis:
                        # 提取文本内容
                        text_content = content_analysis.get("text_info", {}).get("preview", "")
                        if text_content:
                            ai_analysis = self.ai_service.analyze_text(text_content)
                            content_analysis["ai_analysis"] = ai_analysis
            
            except Exception as e:
                logger.error(f"AI处理文件时出错: {str(e)}")
                content_analysis["ai_error"] = str(e)
            
            # 添加时间戳
            content_analysis["processing_time"] = datetime.now().isoformat()
            
            return content_analysis
            
        except Exception as e:
            logger.error(f"处理文件时出错: {str(e)}")
            return {"error": str(e)}
    
    def process_text(self, text: str, purpose: str = "general") -> Dict[str, Any]:
        """
        处理文本内容
        
        Args:
            text: 要处理的文本
            purpose: 分析目的
            
        Returns:
            处理结果字典
        """
        logger.info(f"处理文本内容 (目的: {purpose})")
        
        try:
            # 检查文本内容是否为空
            if not text or len(text.strip()) == 0:
                return {"error": "提供的文本内容为空"}
                
            # 使用文本分析器直接分析文本内容 - 明确传递text_content参数
            text_analysis = self.content_processor.text_analyzer.analyze(text_content=text)
            
            # 尝试使用AI服务进行深度分析
            try:
                ai_analysis = self.ai_service.analyze_text(text, purpose)
            except Exception as e:
                logger.error(f"AI分析文本时出错: {str(e)}")
                ai_analysis = {"error": f"AI分析失败: {str(e)}"}
            
            # 合并结果
            content_analysis = {
                "content_type": "text",
                "text_analysis": text_analysis,
                "ai_analysis": ai_analysis,
                "processing_time": datetime.now().isoformat()
            }
            
            return content_analysis
            
        except Exception as e:
            logger.error(f"处理文本内容时出错: {str(e)}")
            return {"error": str(e)}
    
    def generate_content(self, prompt: str, references: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成多模态内容
        
        Args:
            prompt: 生成提示
            references: 参考内容列表
            
        Returns:
            生成结果字典
        """
        logger.info(f"生成内容: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")
        
        try:
            # 使用AI服务生成内容
            generated_content = self.ai_service.generate_multimodal_content(prompt, references)
            
            if "error" in generated_content:
                return generated_content
            
            # 使用内容处理器分析生成的内容
            if "content" in generated_content:
                content_text = generated_content["content"]
                content_analysis = self.content_processor.process_content(content_text)
                generated_content["analysis"] = content_analysis
            
            # 添加时间戳
            generated_content["generation_time"] = datetime.now().isoformat()
            
            return generated_content
            
        except Exception as e:
            logger.error(f"生成内容时出错: {str(e)}")
            return {"error": str(e)}
    
    def export_results(self, results: Dict[str, Any], output_format: str = 'json') -> str:
        """
        导出处理结果
        
        Args:
            results: 处理结果
            output_format: 输出格式
            
        Returns:
            导出文件路径
        """
        logger.info(f"导出结果为 {output_format} 格式")
        return self.content_processor.export_results(results, output_format)
    
    def process_batch(self, file_paths: List[Union[str, Path]]) -> Dict[str, Any]:
        """
        批量处理文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            批处理结果
        """
        logger.info(f"批量处理 {len(file_paths)} 个文件")
        
        results = []
        errors = []
        
        for file_path in file_paths:
            try:
                result = self.process_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
                errors.append({"file": str(file_path), "error": str(e)})
        
        # 生成汇总报告
        summary = {
            "total_files": len(file_paths),
            "successful": len(results),
            "failed": len(errors),
            "processing_time": datetime.now().isoformat()
        }
        
        if results:
            # 生成综合报告
            report = self.content_processor.generate_report(results)
            summary["report"] = report
        
        return {
            "summary": summary,
            "results": results,
            "errors": errors
        }

# Flask Web应用
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)  # 允许跨域请求

# 配置上传文件夹
upload_folder = os.path.join(tempfile.gettempdir(), 'multimodal_assistant_uploads')
os.makedirs(upload_folder, exist_ok=True)
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

# 创建全局实例
api_key = os.getenv("OPENAI_API_KEY", "")
api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
ai_service = AIService(api_key=api_key, api_base=api_base)

# 全局内容助手实例
assistant = None

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_compat():
    """兼容性路由 - 重定向到api/analyze-file"""
    global assistant
    if not assistant:
        assistant = MultimodalAssistant()
    
    if 'file' not in request.files:
        return jsonify({"error": "没有文件上传"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400
    
    if file:
        # 保存上传的文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        # 处理文件
        result = assistant.process_file(file_path)
        
        return jsonify(result)

@app.route('/analyze-text', methods=['POST'])
def analyze_text_compat():
    """兼容性路由 - 重定向到api/analyze-text"""
    global assistant
    if not assistant:
        assistant = MultimodalAssistant()
    
    try:
        # 获取请求中的文本内容和分析类型
        text_content = request.form.get('text')
        if not text_content:
            # 如果form中没有，尝试从JSON中获取
            if request.is_json:
                json_data = request.get_json()
                text_content = json_data.get('text', '')
        
        analysis_type = request.form.get('type', 'general')
        if not analysis_type and request.is_json:
            json_data = request.get_json()
            analysis_type = json_data.get('type', 'general')
        
        # 验证文本内容
        if not text_content or len(text_content.strip()) == 0:
            return jsonify({"error": "未提供有效的文本内容"}), 400
            
        # 对文本内容进行分析
        analysis_result = assistant.process_text(text_content, analysis_type)
        
        return jsonify(analysis_result)
        
    except Exception as e:
        logger.error(f"处理文本分析请求时出错: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-file', methods=['POST'])
def analyze_file():
    """处理文件分析请求"""
    if 'file' not in request.files:
        return jsonify({"error": "没有文件上传"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400
    
    if file:
        # 保存上传的文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        # 处理文件
        assistant = MultimodalAssistant(app.config['UPLOAD_FOLDER'])
        result = assistant.process_file(file_path)
        
        return jsonify(result)

@app.route('/api/generate-content', methods=['POST'])
def generate_content():
    """生成内容"""
    data = request.json
    if not data or 'prompt' not in data:
        return jsonify({"error": "没有提供生成提示"}), 400
    
    prompt = data['prompt']
    references = data.get('references', [])
    
    # 生成内容
    assistant = MultimodalAssistant(app.config['UPLOAD_FOLDER'])
    result = assistant.generate_content(prompt, references)
    
    return jsonify(result)

@app.route('/api/export', methods=['POST'])
def export_results():
    """导出分析结果"""
    data = request.json
    if not data or 'results' not in data:
        return jsonify({"error": "没有提供结果数据"}), 400
    
    results = data['results']
    output_format = data.get('format', 'json')
    
    # 导出结果
    assistant = MultimodalAssistant(app.config['UPLOAD_FOLDER'])
    output_path = assistant.export_results(results, output_format)
    
    return jsonify({"output_path": output_path})

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """下载生成的文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

def open_browser():
    """在默认浏览器中打开应用"""
    webbrowser.open('http://127.0.0.1:5000/')

def run_web_app(debug=False, port=5000):
    """启动Web应用"""
    global assistant
    
    print("\n" + "="*80)
    print("多模态内容助手应用启动指南".center(76))
    print("="*80)
    
    # 检查依赖项
    try:
        import openai
        print("✓ OpenAI库已安装")
    except ImportError:
        print("✗ OpenAI库未安装，将无法使用API功能")
        print("  请使用命令安装: pip install openai")
    
    print("\n1. 确保当前目录正确：")
    print("   当前运行目录: " + os.getcwd())
    print("   如果路径不是'...\\模块一_Python零基础入门\\1.12\\csdn\\codes'")
    print("   - Windows CMD: cd notes\\模块一_Python零基础入门\\1.12\\csdn\\codes")
    print("   - Windows PowerShell: cd .\\notes\\模块一_Python零基础入门\\1.12\\csdn\\codes")
    print("   - Unix/Linux/MacOS: cd notes/模块一_Python零基础入门/1.12/csdn/codes")
    print("\n2. 启动应用命令：")
    print("   - Windows CMD: python app.py web --port 5000")
    print("   - Windows PowerShell: python .\\app.py web --port 5000")
    print("   - Unix/Linux/MacOS: python app.py web --port 5000")
    print("\n3. 功能说明:")
    print("   - 文本分析: 支持文本情感分析、关键词提取、主题识别")
    print("   - 图像分析: 支持使用OpenAI Vision模型识别图像内容")
    print("   - 音频分析: 使用本地Whisper模型进行语音识别")
    print("   - 视频分析: 提取关键帧使用Vision模型分析，音频使用Whisper识别")
    print("\n4. API配置:")
    print("   - 设置OPENAI_API_KEY环境变量以使用图像识别功能")
    print("     Windows PowerShell: $env:OPENAI_API_KEY=\"your-api-key\"")
    print("     Windows CMD: set OPENAI_API_KEY=your-api-key")
    print("     Unix/Linux/MacOS: export OPENAI_API_KEY=your-api-key")
    print("\n5. 依赖安装:")
    print("   - 安装OpenAI: pip install openai")
    print("   - 安装Whisper: pip install openai-whisper")
    print("   - 安装NLTK: pip install nltk")
    print("   - 安装依赖: pip install -r requirements.txt (如果存在)")
    print("\n6. 访问应用:")
    print(f"   浏览器打开: http://127.0.0.1:{port}")
    print("="*80 + "\n")
    
    if not assistant:
        assistant = MultimodalAssistant()
    
    # 设置FLASK_DEBUG环境变量
    if debug:
        os.environ['FLASK_DEBUG'] = '1'
    
    # 启动浏览器
    if not debug:
        Timer(1.5, open_browser).start()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=port, debug=debug)

def run_cli_app():
    """运行命令行应用"""
    parser = argparse.ArgumentParser(description='多模态内容助手 - 基于Python标准库和AI技术')
    
    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest='command', help='要执行的命令')
    
    # 文件分析命令
    file_parser = subparsers.add_parser('analyze-file', help='分析文件')
    file_parser.add_argument('file_path', help='要分析的文件路径')
    file_parser.add_argument('--output', '-o', help='输出格式 (json, csv, txt)', default='json')
    
    # 文本分析命令
    text_parser = subparsers.add_parser('analyze-text', help='分析文本')
    text_parser.add_argument('text', help='要分析的文本')
    text_parser.add_argument('--purpose', '-p', help='分析目的 (general, academic, social_media, marketing)', default='general')
    text_parser.add_argument('--output', '-o', help='输出格式 (json, csv, txt)', default='json')
    
    # 内容生成命令
    generate_parser = subparsers.add_parser('generate', help='生成内容')
    generate_parser.add_argument('prompt', help='生成提示')
    generate_parser.add_argument('--references', '-r', help='参考内容文件（每行一个）')
    generate_parser.add_argument('--output', '-o', help='输出格式 (json, txt)', default='txt')
    
    # 批处理命令
    batch_parser = subparsers.add_parser('batch', help='批量处理文件')
    batch_parser.add_argument('file_list', help='包含文件路径的文本文件，每行一个')
    batch_parser.add_argument('--output', '-o', help='输出格式 (json, txt)', default='txt')
    
    # Web应用命令
    web_parser = subparsers.add_parser('web', help='启动Web应用')
    web_parser.add_argument('--port', '-p', help='服务器端口', type=int, default=5000)
    web_parser.add_argument('--debug', '-d', help='启用调试模式', action='store_true')
    
    # 解析参数
    args = parser.parse_args()
    
    # 初始化助手
    assistant = MultimodalAssistant()
    
    # 执行命令
    if args.command == 'analyze-file':
        result = assistant.process_file(args.file_path)
        output_path = assistant.export_results(result, args.output)
        print(f"分析结果已保存到: {output_path}")
    
    elif args.command == 'analyze-text':
        result = assistant.process_text(args.text, args.purpose)
        output_path = assistant.export_results(result, args.output)
        print(f"分析结果已保存到: {output_path}")
    
    elif args.command == 'generate':
        references = []
        if args.references:
            try:
                with open(args.references, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            references.append({"type": "text", "content": line})
            except Exception as e:
                print(f"读取参考内容时出错: {str(e)}")
                sys.exit(1)
        
        result = assistant.generate_content(args.prompt, references)
        
        if args.output == 'json':
            output_path = assistant.export_results(result, 'json')
            print(f"生成结果已保存到: {output_path}")
        else:
            if "content" in result:
                print("\n" + "="*30)
                print("生成内容:")
                print("="*30)
                print(result["content"])
            else:
                print(f"生成内容时出错: {result.get('error', '未知错误')}")
    
    elif args.command == 'batch':
        try:
            with open(args.file_list, 'r', encoding='utf-8') as f:
                file_paths = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"读取文件列表时出错: {str(e)}")
            sys.exit(1)
        
        result = assistant.process_batch(file_paths)
        
        if args.output == 'json':
            output_path = assistant.export_results(result, 'json')
            print(f"批处理结果已保存到: {output_path}")
        else:
            print("\n" + "="*30)
            print(f"批处理摘要 (共{result['summary']['total_files']}个文件):")
            print(f"- 成功: {result['summary']['successful']}")
            print(f"- 失败: {result['summary']['failed']}")
            print("="*30)
            
            if "report" in result["summary"]:
                print("\n" + result["summary"]["report"])
    
    elif args.command == 'web':
        print(f"启动Web应用，端口: {args.port}")
        run_web_app(debug=args.debug, port=args.port)
    
    else:
        # 如果没有指定命令，显示帮助
        parser.print_help()

@app.route('/api/analyze-text', methods=['POST'])
def analyze_text_legacy():
    """处理文本分析请求 - 旧版本，保持兼容性"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        generate_suggestions = data.get('generate_suggestions', True)
        
        if not text:
            return jsonify({"error": "文本内容不能为空"}), 400
            
        # 使用AIService进行分析
        ai_service = AIService()
        analysis_result = ai_service.analyze_text(text)
        
        # 如果需要生成建议
        suggestions = None
        if generate_suggestions:
            suggestions = ai_service.get_suggestions({
                "content_type": "text",
                "text_length": len(text),
                "keywords": analysis_result.get("keywords", []),
                "sentiment": analysis_result.get("sentiment"),
                "analysis": str(analysis_result.get("analysis", ""))  # 确保是字符串
            })
        
        # 构建返回结果
        result = {
            "content_type": "text",
            "text_length": len(text),
            "analysis": str(analysis_result.get("analysis", "")),  # 确保是字符串
            "keywords": analysis_result.get("keywords", []),
            "sentiment": analysis_result.get("sentiment"),
            "suggestions": suggestions.get("suggestions", []) if suggestions else None,
            "method": analysis_result.get("method", "local")
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"文本分析错误: {str(e)}")
        return jsonify({"error": f"文本分析错误: {str(e)}"}), 500

@app.route('/api/analyze/text', methods=['POST'])
def analyze_text():
    """文本分析接口"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        generate_suggestions = data.get('generate_suggestions', False)
        
        if not text:
            return jsonify({
                'error': '文本内容不能为空'
            }), 400
            
        # 使用AIService进行分析
        ai_service = AIService()
        analysis_result = ai_service.analyze_text(text, generate_suggestions)
        
        # 确保返回的数据格式正确
        result = {
            'content_type': 'text',
            'text_length': len(text),
            'analysis': str(analysis_result.get('analysis', '')),
            'keywords': [str(k) for k in analysis_result.get('keywords', [])],
            'sentiment': str(analysis_result.get('sentiment', 'neutral')),
            'suggestions': [str(s) for s in analysis_result.get('suggestions', [])] if generate_suggestions else []
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"文本分析失败: {str(e)}")
        return jsonify({
            'error': f'分析失败: {str(e)}'
        }), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多模态内容助手")
    
    # 命令行参数
    subparsers = parser.add_subparsers(dest="command", help="运行模式")
    
    # Web模式
    web_parser = subparsers.add_parser("web", help="以Web应用模式运行")
    web_parser.add_argument("--port", type=int, default=5000, help="Web服务端口 (默认: 5000)")
    web_parser.add_argument("--debug", action="store_true", help="是否开启调试模式")
    
    # CLI模式
    cli_parser = subparsers.add_parser("cli", help="以命令行模式运行")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析文件")
    analyze_parser.add_argument("file", help="要分析的文件路径")
    
    # 解析命令行参数
    try:
        args = parser.parse_args()
    except SystemExit:
        # 如果命令解析错误，提供更详细的帮助信息
        print("\n" + "="*80)
        print("多模态内容助手 - 启动指南".center(76))
        print("="*80)
        print("\n【Windows PowerShell用户】")
        print("使用PowerShell时请使用以下命令格式:")
        print("1. 切换到正确目录:")
        print("   cd .\\notes\\模块一_Python零基础入门\\1.12\\csdn\\codes")
        print("\n2. 运行应用:")
        print("   python .\\app.py web --port 5000")
        print("\n【其他常见问题】")
        print("1. 找不到app.py文件:")
        print("   请先确保您在正确的目录中: .../模块一_Python零基础入门/1.12/csdn/codes")
        print("\n2. 依赖问题:")
        print("   pip install nltk openai-whisper pillow flask flask-cors")
        print("="*80)
        sys.exit(1)
    
    # 检查当前工作目录
    current_dir = os.path.basename(os.getcwd())
    if current_dir != "codes":
        print("\n⚠️ 警告: 应用可能未在正确的目录中运行")
        print(f"当前目录: {os.getcwd()}")
        print("推荐目录结构应为: .../模块一_Python零基础入门/1.12/csdn/codes/")
        print("\n【Windows命令提示符】")
        print("cd notes\\模块一_Python零基础入门\\1.12\\csdn\\codes")
        print("\n【Windows PowerShell】")
        print("cd .\\notes\\模块一_Python零基础入门\\1.12\\csdn\\codes")
        print("\n【Unix/Linux/MacOS】")
        print("cd notes/模块一_Python零基础入门/1.12/csdn/codes\n")
    
    # 执行对应命令
    if args.command == "web":
        run_web_app(debug=args.debug, port=args.port)
    elif args.command == "cli":
        run_cli_app()
    elif args.command == "analyze":
        if not os.path.exists(args.file):
            print(f"错误: 文件不存在 - {args.file}")
            sys.exit(1)
        
        # 创建内容助手并分析文件
        assistant = MultimodalAssistant()
        result = assistant.process_file(args.file)
        
        # 输出分析结果
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 如果没有提供命令参数，显示帮助信息
        parser.print_help()
        print("\n推荐使用方式:")
        print("  【Windows PowerShell】")
        print("  python .\\app.py web --port 5000  # 以Web应用模式运行")
        print("  python .\\app.py cli              # 以命令行模式运行")
        print("  python .\\app.py analyze 文件路径  # 分析指定文件")
        print("\n  【Windows命令提示符】")
        print("  python app.py web --port 5000     # 以Web应用模式运行")
        print("  python app.py cli                 # 以命令行模式运行")
        print("  python app.py analyze 文件路径     # 分析指定文件")