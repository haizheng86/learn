#!/usr/bin/env python3
# text_analyzer.py - 多功能文本分析工具
# 这是一个基于Python标准库的文本分析工具，无需安装任何第三方库
# 适用于初学者学习如何使用标准库实现实用功能

import os               # 操作系统接口，用于文件路径处理
import sys              # 系统相关功能，用于程序退出等操作
import argparse         # 命令行参数解析库，简化命令行界面开发
import logging          # 日志记录库，提供灵活的日志功能
from collections import Counter, defaultdict  # 高效的计数器和默认字典
import re               # 正则表达式库，用于文本模式匹配
import json             # JSON数据处理库
from datetime import datetime  # 日期时间处理
import time             # 时间测量
import itertools        # 高效迭代器工具

# 配置日志系统
# 格式说明：
# %(asctime)s - 时间戳
# %(name)s - 日志记录器名称
# %(levelname)s - 日志级别
# %(message)s - 日志消息
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为INFO，忽略DEBUG级别的消息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # 日志输出到控制台
)
logger = logging.getLogger('TextAnalyzer')  # 创建一个名为'TextAnalyzer'的日志记录器

def setup_args():
    """
    设置命令行参数解析器
    
    创建一个参数解析器对象，定义程序需要的各种参数
    返回解析后的参数对象
    """
    # 创建解析器对象，并添加描述
    parser = argparse.ArgumentParser(description='文本分析工具')
    
    # 添加位置参数 - 文件路径是必需的
    parser.add_argument('file', help='要分析的文本文件路径')
    
    # 添加可选参数，使用短选项和长选项
    # action='store_true'表示该选项不需要值，存在即为True
    parser.add_argument('-w', '--word-count', action='store_true', 
                        help='统计词频')
    parser.add_argument('-s', '--sentence-stats', action='store_true', 
                        help='分析句子统计数据')
    parser.add_argument('-k', '--keywords', type=int, default=0, 
                        help='提取指定数量的关键词')
    parser.add_argument('-p', '--pattern', 
                        help='使用正则表达式搜索匹配项')
    parser.add_argument('-o', '--output', 
                        help='将结果输出到指定的JSON文件')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='显示详细信息')
    
    # 解析参数并返回
    return parser.parse_args()

def load_text(file_path):
    """
    加载和预处理文本文件
    
    参数:
        file_path: 文本文件的路径
        
    返回:
        文件内容字符串
    
    异常:
        如果文件不存在或无法读取，则退出程序
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        sys.exit(1)  # 以错误状态退出程序
        
    try:
        # 记录开始时间，用于性能测量
        start_time = time.time()
        
        # 尝试使用不同编码打开文件，提高兼容性
        # 常见的编码: utf-8(Unicode), gbk(中文), latin1(西欧)
        encodings = ['utf-8', 'gbk', 'latin1']
        text = None
        
        # 依次尝试每种编码
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                logger.info(f"使用 {encoding} 编码成功加载文件")
                break  # 找到有效编码后跳出循环
            except UnicodeDecodeError:
                # 编码不匹配，尝试下一个
                continue
                
        # 如果所有编码都失败，则报错退出
        if text is None:
            logger.error("无法识别文件编码")
            sys.exit(1)
            
        # 记录加载时间
        logger.info(f"文件加载完成，耗时: {time.time() - start_time:.2f}秒")
        return text
    except Exception as e:
        # 捕获其他可能的异常
        logger.error(f"加载文件时出错: {str(e)}")
        sys.exit(1)
        
def preprocess_text(text):
    """
    文本预处理：分词、去除标点符号等
    
    参数:
        text: 原始文本字符串
        
    返回:
        字典，包含处理后的文本、句子列表和单词列表
    """
    # 转换为小写，便于统一处理
    text = text.lower()
    
    # 分离句子 - 使用正则表达式按照句号、感叹号或问号分割
    sentences = re.split(r'[.!?]+', text)
    # 去除空白句子并清理两端空格
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # 分离单词并去除标点 - 只保留字母和数字
    word_pattern = re.compile(r'\w+')
    words = word_pattern.findall(text)
    
    # 返回处理结果字典
    return {
        'text': text,           # 小写化的原始文本
        'sentences': sentences,  # 句子列表
        'words': words           # 单词列表
    }

def analyze_text(processed_text, args):
    """
    分析文本并生成统计数据
    
    参数:
        processed_text: 预处理后的文本数据字典
        args: 命令行参数对象
        
    返回:
        包含分析结果的字典
    """
    # 创建结果字典，包含基本信息
    result = {
        'timestamp': datetime.now().isoformat(),  # ISO格式的当前时间
        'filename': os.path.basename(args.file),  # 文件名，不含路径
        'file_size': os.path.getsize(args.file),  # 文件大小（字节）
        'general_stats': {
            'character_count': len(processed_text['text']),  # 字符数
            'word_count': len(processed_text['words']),      # 单词数
            'sentence_count': len(processed_text['sentences']),  # 句子数
            'unique_words': len(set(processed_text['words'])),  # 不重复单词数
            # 平均单词长度，防止除零错误
            'average_word_length': sum(len(word) for word in processed_text['words']) / len(processed_text['words']) if processed_text['words'] else 0
        }
    }
    
    # 词频分析 - 如果开启了该选项
    if args.word_count:
        # 使用Counter高效统计词频
        word_counter = Counter(processed_text['words'])
        result['word_frequency'] = {
            'most_common': dict(word_counter.most_common(20)),  # 最常见的20个词
            # 最不常见的20个词（如果单词总数>20）
            'least_common': dict(word_counter.most_common()[:-21:-1]) if len(word_counter) > 20 else dict(word_counter)
        }
    
    # 句子统计 - 如果开启了该选项
    if args.sentence_stats:
        # 计算每个句子的单词数
        sentence_lengths = [len(s.split()) for s in processed_text['sentences']]
        result['sentence_stats'] = {
            # 最短句子长度（词数）
            'min_length': min(sentence_lengths) if sentence_lengths else 0,
            # 最长句子长度（词数）
            'max_length': max(sentence_lengths) if sentence_lengths else 0,
            # 平均句子长度（词数）
            'average_length': sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0,
            # 按长度分类句子数量
            'sentences_by_length': {
                'short (1-5)': sum(1 for l in sentence_lengths if 1 <= l <= 5),
                'medium (6-15)': sum(1 for l in sentence_lengths if 6 <= l <= 15),
                'long (16+)': sum(1 for l in sentence_lengths if l >= 16)
            }
        }
    
    # 关键词提取 - 如果指定了关键词数量
    if args.keywords > 0:
        word_counter = Counter(processed_text['words'])
        # 常见英文停用词列表 - 这些词通常不包含重要信息
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
                     'when', 'where', 'how', 'why', 'which', 'who', 'whom', 'this', 'that',
                     'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                     'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'to',
                     'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into',
                     'through', 'during', 'before', 'after', 'above', 'below', 'from',
                     'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
                     'further', 'then', 'once', 'here', 'there', 'all', 'any', 'both',
                     'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
                     'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very'}
        # 过滤掉停用词和短词，保留可能的关键词
        keywords = {word: count for word, count in word_counter.items() 
                   if word not in stop_words and len(word) > 2}
        # 取出出现频率最高的n个词作为关键词
        result['keywords'] = dict(sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:args.keywords])
    
    # 正则表达式模式匹配 - 如果指定了模式
    if args.pattern:
        try:
            # 编译正则表达式模式
            pattern = re.compile(args.pattern)
            # 在文本中查找所有匹配项
            matches = pattern.findall(processed_text['text'])
            result['pattern_matches'] = {
                'pattern': args.pattern,  # 使用的正则表达式
                'match_count': len(matches),  # 匹配数量
                'first_10_matches': matches[:10]  # 前10个匹配结果
            }
        except re.error as e:
            # 捕获正则表达式错误
            logger.error(f"正则表达式错误: {str(e)}")
            result['pattern_matches'] = {
                'error': f"无效的正则表达式: {str(e)}"
            }
    
    return result

def output_results(result, args):
    """
    输出分析结果
    
    参数:
        result: 分析结果字典
        args: 命令行参数对象
    """
    # 详细输出模式 - 打印所有详细信息
    if args.verbose:
        print("\n" + "="*50)
        print(f"文本分析结果: {args.file}")
        print("="*50)
        
        # 打印基本统计信息
        print(f"\n文件大小: {result['file_size']} 字节")
        print(f"字符数: {result['general_stats']['character_count']}")
        print(f"单词数: {result['general_stats']['word_count']}")
        print(f"句子数: {result['general_stats']['sentence_count']}")
        print(f"唯一单词数: {result['general_stats']['unique_words']}")
        print(f"平均单词长度: {result['general_stats']['average_word_length']:.2f} 字符")
        
        # 打印词频统计（如果有）
        if 'word_frequency' in result:
            print("\n词频统计 (前10个):")
            for word, count in list(result['word_frequency']['most_common'].items())[:10]:
                print(f"  {word}: {count}")
                
        # 打印句子统计（如果有）
        if 'sentence_stats' in result:
            print("\n句子统计:")
            print(f"  最短句子: {result['sentence_stats']['min_length']} 词")
            print(f"  最长句子: {result['sentence_stats']['max_length']} 词")
            print(f"  平均长度: {result['sentence_stats']['average_length']:.2f} 词")
            print("  句子长度分布:")
            for length_type, count in result['sentence_stats']['sentences_by_length'].items():
                print(f"    {length_type}: {count}")
                
        # 打印关键词（如果有）
        if 'keywords' in result:
            print("\n关键词:")
            for keyword, count in result['keywords'].items():
                print(f"  {keyword}: {count}")
                
        # 打印正则表达式匹配结果（如果有）
        if 'pattern_matches' in result:
            print("\n正则表达式匹配:")
            if 'error' in result['pattern_matches']:
                print(f"  错误: {result['pattern_matches']['error']}")
            else:
                print(f"  模式: {result['pattern_matches']['pattern']}")
                print(f"  匹配数: {result['pattern_matches']['match_count']}")
                if result['pattern_matches']['match_count'] > 0:
                    print("  前10个匹配:")
                    for match in result['pattern_matches']['first_10_matches']:
                        print(f"    - {match}")
    else:
        # 简洁输出模式 - 只打印摘要信息
        print(f"已分析 {args.file}:")
        print(f"  {result['general_stats']['character_count']} 字符, {result['general_stats']['word_count']} 单词, {result['general_stats']['sentence_count']} 句子")
    
    # 保存到JSON文件（如果指定了输出文件）
    if args.output:
        try:
            # 将结果字典保存为格式化的JSON文件
            with open(args.output, 'w', encoding='utf-8') as f:
                # ensure_ascii=False允许保存中文等非ASCII字符
                # indent=2使输出格式化，便于阅读
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n分析结果已保存至: {args.output}")
        except Exception as e:
            logger.error(f"保存结果时出错: {str(e)}")

def main():
    """主程序入口"""
    # 记录程序开始时间
    start_time = time.time()
    
    # 解析命令行参数
    args = setup_args()
    
    # 如果没有指定任何分析选项，默认执行全部分析
    # 这提供了更好的用户体验，用户可以直接运行而无需指定选项
    if not any([args.word_count, args.sentence_stats, args.keywords, args.pattern]):
        args.word_count = True
        args.sentence_stats = True
        args.keywords = 10
        logger.info("未指定分析选项，将执行默认分析")
    
    # 加载并预处理文本
    text = load_text(args.file)
    processed_text = preprocess_text(text)
    
    # 分析文本
    logger.info("正在分析文本...")
    result = analyze_text(processed_text, args)
    
    # 输出结果
    output_results(result, args)
    
    # 记录总耗时
    logger.info(f"分析完成，总耗时: {time.time() - start_time:.2f}秒")

# 当脚本直接运行（而非被导入）时执行main函数
if __name__ == '__main__':
    main() 