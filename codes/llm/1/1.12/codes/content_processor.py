import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Union, Optional, Any, Tuple
from datetime import datetime
import mimetypes
import csv
import tempfile

# 导入标准库模块
import textwrap
import string
import collections
import statistics
import base64

# 可选的第三方依赖，确保在requirements.txt中列出
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

# 配置日志
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("content_processor")

class TextAnalyzer:
    """文本分析器，用于处理和分析文本内容"""
    
    def __init__(self):
        """初始化文本分析器"""
        self.punctuation_translator = str.maketrans('', '', string.punctuation)
        
    def analyze(self, text: str) -> Dict[str, Any]:
        """
        分析文本内容，提取基础统计信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            包含分析结果的字典
        """
        if not text or text.isspace():
            return {"error": "文本为空或仅包含空白字符"}
        
        # 分析文本结构
        lines = text.split('\n')
        paragraphs = [p for p in text.split('\n\n') if p and not p.isspace()]
        
        # 分析单词
        words = re.findall(r'\b\w+\b', text.lower())
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        
        # 计算词频
        word_freq = collections.Counter(words)
        most_common_words = word_freq.most_common(10)
        
        # 计算句子长度
        sentences = re.split(r'[.!?。！？]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_lengths = [len(s) for s in sentences]
        
        # 计算阅读难度 (简化的Flesch-Kincaid阅读难度指数)
        avg_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else 0
        avg_word_length = statistics.mean([len(w) for w in words]) if words else 0
        reading_ease = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_word_length)
        
        # 提取潜在标题
        potential_titles = []
        for line in lines[:5]:  # 仅检查前5行
            line = line.strip()
            if line and not line.endswith(('.', '。', '!', '！', '?', '？')):
                if 3 < len(line) < 50:  # 合理的标题长度
                    potential_titles.append(line)
        
        # 分析是否包含代码块
        code_blocks = []
        in_code_block = False
        current_block = []
        
        for line in lines:
            if line.strip() == '```' or line.strip().startswith('```'):
                if in_code_block:
                    # 结束代码块
                    in_code_block = False
                    if current_block:
                        code_blocks.append('\n'.join(current_block))
                        current_block = []
                else:
                    # 开始代码块
                    in_code_block = True
            elif in_code_block:
                current_block.append(line)
        
        # 分析特殊格式
        has_bullet_points = any(line.strip().startswith(('- ', '* ', '• ')) for line in lines)
        has_numbered_list = bool(re.search(r'^\d+\.\s', text, re.MULTILINE))
        has_headings = bool(re.search(r'^#+\s', text, re.MULTILINE))
        
        return {
            "statistics": {
                "char_count": len(text),
                "word_count": len(words) + len(chinese_chars),
                "sentence_count": len(sentences),
                "paragraph_count": len(paragraphs),
                "line_count": len(lines),
                "avg_sentence_length": avg_sentence_length,
                "avg_word_length": avg_word_length,
                "reading_ease": reading_ease,
                "estimated_read_time_minutes": len(words) / 200  # 假设阅读速度为每分钟200字
            },
            "structure": {
                "potential_titles": potential_titles[:2],  # 最多返回2个
                "has_bullet_points": has_bullet_points,
                "has_numbered_list": has_numbered_list,
                "has_headings": has_headings,
                "has_code_blocks": bool(code_blocks),
                "code_block_count": len(code_blocks)
            },
            "content": {
                "top_words": most_common_words,
                "code_samples": code_blocks[:3]  # 最多返回3个代码样本
            },
            "meta": {
                "analysis_timestamp": datetime.now().isoformat(),
                "analyzer_version": "1.0.0"
            }
        }
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        从文本中提取关键词
        
        这是一个简单实现，使用TF-IDF思想但不需要语料库
        实际应用中可以使用更复杂的NLP技术
        
        Args:
            text: 要分析的文本
            max_keywords: 最大关键词数量
            
        Returns:
            关键词列表
        """
        if not text or text.isspace():
            return []
        
        # 清理文本，分割为单词
        words = re.findall(r'\b\w+\b', text.lower())
        words = [w for w in words if len(w) > 1]  # 过滤短词
        
        # 计算词频
        word_freq = collections.Counter(words)
        
        # 停用词过滤（简化版）
        stopwords = {'and', 'the', 'to', 'of', 'a', 'in', 'for', 'is', 'on', 'that', 'by', 
                    'this', 'with', 'i', 'you', 'it', 'not', 'or', 'be', 'are', 'from',
                    '的', '了', '和', '是', '在', '我', '有', '就', '不', '人', '都', '一', '一个',
                    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好'}
        
        # 过滤停用词并提取最常见词
        filtered_words = {word: freq for word, freq in word_freq.items() if word not in stopwords}
        
        # 根据频率排序并返回前N个
        keywords = [word for word, _ in sorted(filtered_words.items(), key=lambda x: x[1], reverse=True)[:max_keywords]]
        
        return keywords
    
    def summarize(self, text: str, max_sentences: int = 3) -> str:
        """
        简单的文本摘要生成器
        
        使用基于句子重要性评分的提取式摘要方法
        
        Args:
            text: 要摘要的文本
            max_sentences: 摘要中最大句子数
            
        Returns:
            文本摘要
        """
        if not text or text.isspace():
            return ""
        
        # 分割为句子
        sentences = re.split(r'[.!?。！？]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return ""
        
        if len(sentences) <= max_sentences:
            return " ".join(sentences)
        
        # 提取所有词（不包括停用词）
        all_words = []
        for sentence in sentences:
            words = re.findall(r'\b\w+\b', sentence.lower())
            all_words.extend([w for w in words if len(w) > 1])
        
        # 计算词频
        word_freq = collections.Counter(all_words)
        
        # 为每个句子计算分数
        sentence_scores = []
        for sentence in sentences:
            words = re.findall(r'\b\w+\b', sentence.lower())
            score = sum(word_freq[word] for word in words if len(word) > 1)
            # 归一化句子长度
            score = score / (len(words) + 1)  # 加1避免除零
            sentence_scores.append((sentence, score))
        
        # 选择分数最高的句子
        top_sentences = sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:max_sentences]
        
        # 按照原始顺序重新排列句子
        original_order = []
        for sentence, _ in top_sentences:
            index = sentences.index(sentence)
            original_order.append((index, sentence))
        
        original_order.sort()  # 按索引排序
        
        return " ".join(sentence for _, sentence in original_order)
    
    def extract_code_samples(self, text: str) -> List[Dict[str, str]]:
        """
        从文本中提取代码样本
        
        Args:
            text: 包含代码块的文本
            
        Returns:
            代码样本列表，每个样本为字典包含代码内容和可能的语言
        """
        code_samples = []
        lines = text.split('\n')
        
        in_code_block = False
        current_block = []
        current_language = None
        
        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    # 结束代码块
                    in_code_block = False
                    if current_block:
                        code_samples.append({
                            "code": '\n'.join(current_block),
                            "language": current_language
                        })
                        current_block = []
                        current_language = None
                else:
                    # 开始代码块
                    in_code_block = True
                    # 检查语言标识
                    language_marker = line.strip()[3:].strip()
                    if language_marker:
                        current_language = language_marker
            elif in_code_block:
                current_block.append(line)
        
        return code_samples
    
    def format_for_display(self, analysis: Dict[str, Any]) -> str:
        """
        将分析结果格式化为可读的文本
        
        Args:
            analysis: analyze()方法返回的分析结果
            
        Returns:
            格式化后的文本
        """
        if "error" in analysis:
            return f"分析错误: {analysis['error']}"
        
        stats = analysis["statistics"]
        structure = analysis["structure"]
        content = analysis["content"]
        
        formatted = []
        formatted.append("文本分析结果摘要")
        formatted.append("=" * 30)
        
        # 基本统计
        formatted.append("\n基本统计:")
        formatted.append(f"- 字符数: {stats['char_count']}")
        formatted.append(f"- 词数: {stats['word_count']}")
        formatted.append(f"- 句子数: {stats['sentence_count']}")
        formatted.append(f"- 段落数: {stats['paragraph_count']}")
        formatted.append(f"- 估计阅读时间: {stats['estimated_read_time_minutes']:.1f}分钟")
        
        # 内容结构
        formatted.append("\n内容结构:")
        if structure["potential_titles"]:
            formatted.append("- 可能的标题:")
            for title in structure["potential_titles"]:
                formatted.append(f"  * {title}")
                
        structure_elements = []
        if structure["has_bullet_points"]:
            structure_elements.append("项目符号列表")
        if structure["has_numbered_list"]:
            structure_elements.append("编号列表")
        if structure["has_headings"]:
            structure_elements.append("标题/小标题")
        if structure["has_code_blocks"]:
            structure_elements.append(f"代码块 ({structure['code_block_count']}个)")
            
        if structure_elements:
            formatted.append("- 包含元素: " + ", ".join(structure_elements))
        
        # 常用词
        formatted.append("\n最常用词:")
        for word, count in content["top_words"][:5]:  # 只显示前5个
            formatted.append(f"- {word}: {count}次")
        
        # 代码样本
        if content["code_samples"]:
            formatted.append("\n包含代码样本:")
            for i, sample in enumerate(content["code_samples"]):
                formatted.append(f"- 代码样本 #{i+1} ({len(sample.split())}行)")
        
        return "\n".join(formatted)


class MediaProcessor:
    """媒体文件处理器，用于处理图像、音频和视频文件"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        初始化媒体处理器
        
        Args:
            temp_dir: 临时文件目录，默认使用系统临时目录
        """
        self.temp_dir = temp_dir or os.environ.get("TEMP_FILE_DIR") or tempfile.gettempdir()
        self._ensure_temp_dir()
    
    def _ensure_temp_dir(self):
        """确保临时目录存在"""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
    
    def process_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        处理媒体文件，提取元数据和基本分析
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含分析结果的字典
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": f"文件不存在: {file_path}"}
        
        file_size = file_path.stat().st_size
        file_type = mimetypes.guess_type(file_path)[0]
        file_extension = file_path.suffix.lower()
        
        # 基本文件信息
        result = {
            "file_info": {
                "name": file_path.name,
                "path": str(file_path),
                "size": file_size,
                "size_formatted": self._format_size(file_size),
                "type": file_type,
                "extension": file_extension,
                "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            },
            "meta": {
                "analysis_timestamp": datetime.now().isoformat(),
                "processor_version": "1.0.0"
            }
        }
        
        # 根据文件类型提取特定元数据
        if file_type:
            if file_type.startswith('image/'):
                result.update(self._process_image(file_path))
            elif file_type.startswith('audio/'):
                result.update(self._process_audio(file_path))
            elif file_type.startswith('video/'):
                result.update(self._process_video(file_path))
            elif file_type.startswith('text/'):
                result.update(self._process_text(file_path))
            elif file_type == 'application/pdf':
                result.update(self._process_pdf(file_path))
            # 可以添加更多文件类型的处理...
        
        return result
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
    
    def _process_image(self, file_path: Path) -> Dict[str, Any]:
        """处理图像文件（仅使用标准库）"""
        # 这里仅返回基本信息，实际应用中可以使用第三方库提取更多信息
        return {
            "image_info": {
                "format": file_path.suffix.lstrip('.').upper(),
                # 注意：这些字段在没有专门的图像处理库时无法提取
                "dimensions": "需要图像处理库",
                "color_mode": "需要图像处理库"
            }
        }
    
    def _process_audio(self, file_path: Path) -> Dict[str, Any]:
        """处理音频文件（仅使用标准库）"""
        # 同样，这里只返回基本信息
        return {
            "audio_info": {
                "format": file_path.suffix.lstrip('.').upper(),
                "duration": "需要音频处理库"
            }
        }
    
    def _process_video(self, file_path: Path) -> Dict[str, Any]:
        """处理视频文件（仅使用标准库）"""
        # 同样，这里只返回基本信息
        return {
            "video_info": {
                "format": file_path.suffix.lstrip('.').upper(),
                "duration": "需要视频处理库"
            }
        }
    
    def _process_text(self, file_path: Path) -> Dict[str, Any]:
        """处理文本文件"""
        # 尝试读取文件内容进行分析
        encoding = self._detect_encoding(file_path)
        text_preview = ""
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                # 读取前1000字符作为预览
                text_preview = f.read(1000)
                
            # 使用TextAnalyzer进行分析
            analyzer = TextAnalyzer()
            text_stats = {
                "text_info": {
                    "encoding": encoding,
                    "preview": text_preview,
                    "line_count": sum(1 for _ in open(file_path, 'r', encoding=encoding))
                }
            }
            
            # 如果文件不太大，进行完整分析
            if file_path.stat().st_size < 1024 * 1024:  # 小于1MB
                with open(file_path, 'r', encoding=encoding) as f:
                    full_text = f.read()
                text_stats["analysis"] = analyzer.analyze(full_text)
            
            return text_stats
            
        except Exception as e:
            logger.error(f"处理文本文件时出错: {str(e)}")
            return {
                "text_info": {
                    "error": f"处理文本文件时出错: {str(e)}",
                    "encoding": encoding,
                    "preview": text_preview
                }
            }
    
    def _process_pdf(self, file_path: Path) -> Dict[str, Any]:
        """处理PDF文件（仅使用标准库）"""
        # 返回基本信息，PDF处理通常需要第三方库
        return {
            "pdf_info": {
                "format": "PDF",
                "page_count": "需要PDF处理库"
            }
        }
    
    def _detect_encoding(self, file_path: Path) -> str:
        """检测文件编码"""
        if HAS_CHARDET:
            # 使用chardet库检测编码
            with open(file_path, 'rb') as f:
                raw_data = f.read(1024)  # 读取前1024字节检测编码
                result = chardet.detect(raw_data)
                encoding = result['encoding']
                confidence = result.get('confidence', 0)
                
                # 如果置信度低，默认使用UTF-8
                if confidence < 0.7:
                    encoding = 'utf-8'
                
                return encoding
        else:
            # 没有chardet库，尝试常见编码
            for encoding in ['utf-8', 'latin-1', 'gbk', 'gb2312', 'utf-16']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        f.read(100)  # 尝试读取部分内容
                    return encoding
                except UnicodeDecodeError:
                    continue
            
            # 如果都失败，返回默认编码
            return 'utf-8'
    
    def export_results(self, analysis_results: Dict[str, Any], output_format: str = 'json', output_path: Optional[str] = None) -> str:
        """
        导出分析结果
        
        Args:
            analysis_results: 分析结果字典
            output_format: 输出格式，支持'json', 'csv', 'txt'
            output_path: 输出文件路径，如果不提供则使用临时目录
            
        Returns:
            输出文件的路径
        """
        if output_path:
            output_file = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = Path(self.temp_dir) / f"analysis_results_{timestamp}.{output_format}"
        
        try:
            if output_format == 'json':
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(analysis_results, f, ensure_ascii=False, indent=2)
            
            elif output_format == 'csv':
                # 将嵌套字典扁平化为CSV
                flat_data = self._flatten_dict(analysis_results)
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Key', 'Value'])  # 写入表头
                    for key, value in flat_data.items():
                        writer.writerow([key, value])
            
            elif output_format == 'txt':
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write("分析结果摘要\n")
                    f.write("=" * 30 + "\n\n")
                    
                    # 递归写入字典内容
                    self._write_dict_to_text(analysis_results, f)
            
            else:
                raise ValueError(f"不支持的输出格式: {output_format}")
            
            return str(output_file)
        
        except Exception as e:
            logger.error(f"导出分析结果时出错: {str(e)}")
            # 出错时创建错误日志文件
            error_file = Path(self.temp_dir) / f"analysis_export_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write(f"导出分析结果时出错: {str(e)}\n")
                f.write(f"原始数据: {str(analysis_results)[:1000]}...\n")
            
            return str(error_file)
    
    def _flatten_dict(self, nested_dict: Dict[str, Any], parent_key: str = '') -> Dict[str, str]:
        """将嵌套字典扁平化为单层字典，键使用点分隔"""
        flat_dict = {}
        for key, value in nested_dict.items():
            new_key = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, dict):
                flat_dict.update(self._flatten_dict(value, new_key))
            elif isinstance(value, list):
                # 对于列表，使用索引作为键
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        flat_dict.update(self._flatten_dict(item, f"{new_key}[{i}]"))
                    else:
                        flat_dict[f"{new_key}[{i}]"] = str(item)
            else:
                flat_dict[new_key] = str(value)
        
        return flat_dict
    
    def _write_dict_to_text(self, data: Dict[str, Any], file, indent: int = 0):
        """递归地将字典写入文本文件"""
        for key, value in data.items():
            if isinstance(value, dict):
                file.write("  " * indent + f"{key}:\n")
                self._write_dict_to_text(value, file, indent + 1)
            elif isinstance(value, list):
                file.write("  " * indent + f"{key}:\n")
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        file.write("  " * (indent + 1) + f"[{i}]:\n")
                        self._write_dict_to_text(item, file, indent + 2)
                    else:
                        file.write("  " * (indent + 1) + f"[{i}]: {item}\n")
            else:
                file.write("  " * indent + f"{key}: {value}\n")


class ContentProcessor:
    """内容处理器，组合文本分析和媒体处理功能"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        初始化内容处理器
        
        Args:
            temp_dir: 临时文件目录
        """
        self.text_analyzer = TextAnalyzer()
        self.media_processor = MediaProcessor(temp_dir)
    
    def process_content(self, content: Union[str, Path], content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        处理内容，可以是文本字符串或文件路径
        
        Args:
            content: 要处理的内容
            content_type: 内容类型提示，可选
            
        Returns:
            处理结果字典
        """
        # 判断内容类型
        if isinstance(content, (str, Path)) and os.path.exists(str(content)):
            # 内容是文件路径
            return self.media_processor.process_file(content)
        elif isinstance(content, str):
            # 内容是文本
            return {
                "content_type": content_type or "text/plain",
                "analysis": self.text_analyzer.analyze(content),
                "summary": self.text_analyzer.summarize(content),
                "keywords": self.text_analyzer.extract_keywords(content),
                "code_samples": self.text_analyzer.extract_code_samples(content)
            }
        else:
            return {"error": "不支持的内容类型"}
    
    def export_results(self, analysis_results: Dict[str, Any], output_format: str = 'json', output_path: Optional[str] = None) -> str:
        """
        导出分析结果
        
        Args:
            analysis_results: 分析结果
            output_format: 输出格式
            output_path: 输出路径
            
        Returns:
            导出文件路径
        """
        return self.media_processor.export_results(analysis_results, output_format, output_path)
    
    def generate_report(self, content_analyses: List[Dict[str, Any]], title: str = "内容分析报告") -> str:
        """
        从多个内容分析结果生成综合报告
        
        Args:
            content_analyses: 内容分析结果列表
            title: 报告标题
            
        Returns:
            报告文本
        """
        report = []
        report.append(title)
        report.append("=" * len(title))
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"分析内容数量: {len(content_analyses)}")
        report.append("")
        
        for i, analysis in enumerate(content_analyses):
            report.append(f"内容 #{i+1}")
            report.append("-" * 30)
            
            if "error" in analysis:
                report.append(f"分析错误: {analysis['error']}")
                continue
            
            # 添加文件信息（如果有）
            if "file_info" in analysis:
                file_info = analysis["file_info"]
                report.append(f"文件名: {file_info.get('name', '未知')}")
                report.append(f"类型: {file_info.get('type', '未知')}")
                report.append(f"大小: {file_info.get('size_formatted', '未知')}")
                report.append("")
            
            # 添加文本分析（如果有）
            if "analysis" in analysis:
                text_analysis = analysis["analysis"]
                
                if "statistics" in text_analysis:
                    stats = text_analysis["statistics"]
                    report.append("文本统计:")
                    report.append(f"- 字符数: {stats.get('char_count', '未知')}")
                    report.append(f"- 词数: {stats.get('word_count', '未知')}")
                    report.append(f"- 估计阅读时间: {stats.get('estimated_read_time_minutes', 0):.1f}分钟")
                
                if "structure" in text_analysis:
                    struct = text_analysis["structure"]
                    report.append("内容结构:")
                    if struct.get("potential_titles"):
                        report.append(f"- 可能的标题: {', '.join(struct['potential_titles'])}")
                    
                    elements = []
                    if struct.get("has_bullet_points"):
                        elements.append("项目符号列表")
                    if struct.get("has_numbered_list"):
                        elements.append("编号列表")
                    if struct.get("has_headings"):
                        elements.append("标题/小标题")
                    if struct.get("has_code_blocks"):
                        elements.append(f"代码块 ({struct.get('code_block_count', 0)}个)")
                    
                    if elements:
                        report.append(f"- 格式元素: {', '.join(elements)}")
            
            # 添加摘要和关键词
            if "summary" in analysis:
                report.append("\n摘要:")
                report.append(textwrap.fill(analysis["summary"], width=70))
            
            if "keywords" in analysis:
                report.append("\n关键词:")
                report.append(", ".join(analysis["keywords"]))
            
            report.append("\n")
        
        return "\n".join(report)


# 测试代码
if __name__ == "__main__":
    # 测试文本分析
    text = """
    # Python标准库概览
    
    Python标准库包含了大量有用的模块，可用于各种任务。本文将简要介绍一些常用模块。
    
    ## 文件操作
    
    使用`os`和`pathlib`模块可以轻松处理文件和目录:
    
    ```python
    from pathlib import Path
    
    # 列出当前目录下的所有Python文件
    python_files = list(Path('.').glob('*.py'))
    print(f"Found {len(python_files)} Python files")
    ```
    
    ## 数据处理
    
    `json`模块用于JSON数据的编码和解码，非常实用:
    
    ```python
    import json
    
    # 将Python对象转换为JSON字符串
    data = {'name': 'Python', 'version': 3.9}
    json_string = json.dumps(data)
    print(json_string)
    ```
    """
    
    analyzer = TextAnalyzer()
    analysis = analyzer.analyze(text)
    
    print("文本分析结果:")
    print(analyzer.format_for_display(analysis))
    
    print("\n关键词:")
    print(analyzer.extract_keywords(text))
    
    print("\n摘要:")
    print(analyzer.summarize(text))
    
    print("\n代码样本:")
    code_samples = analyzer.extract_code_samples(text)
    for i, sample in enumerate(code_samples):
        print(f"样本 #{i+1} ({sample.get('language', '未知')})")
        print(sample["code"])
        print()
    
    # 测试内容处理器
    processor = ContentProcessor()
    result = processor.process_content(text)
    
    # 导出结果
    output_path = processor.export_results(result, 'json')
    print(f"\n结果已导出到: {output_path}") 