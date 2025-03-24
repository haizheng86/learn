#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Python多领域综合应用实战案例：
从数据分析到机器学习预测的新闻情感分析系统

本案例展示了Python在以下领域的应用:
1. 数据获取和处理（Web开发和爬虫）
2. 数据分析和可视化（数据科学）
3. 机器学习模型训练（AI开发）
4. Web界面展示（Web开发）


"""

import os
import re
import json
import time
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import jieba
import jieba.analyse
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import requests
from flask import Flask, render_template, request, jsonify

# 设置中文字体，解决matplotlib中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 设置随机种子，确保结果可重现
np.random.seed(42)

# -----------------------------------------------------------------------------
# 第1部分：数据获取与处理
# -----------------------------------------------------------------------------

def fetch_news_data(keywords, pages=2):
    """
    模拟从新闻API获取数据
    
    参数:
        keywords (list): 搜索关键词列表
        pages (int): 每个关键词获取的页数
    
    返回:
        pd.DataFrame: 包含新闻数据的DataFrame
    """
    print("正在获取新闻数据...")
    
    # 这里使用模拟数据，实际应用中可替换为真实API调用
    news_data = []
    sentiments = ['正面', '负面', '中性']
    weights = [0.5, 0.3, 0.2]  # 各情感的权重，使正面新闻多一些
    
    # 新闻主题和相关词汇
    topics = {
        "科技": ["人工智能", "5G", "区块链", "元宇宙", "数字经济", "芯片", "新能源"],
        "财经": ["股市", "债券", "投资", "金融", "经济", "贸易", "通货膨胀"],
        "教育": ["高考", "教育改革", "在线学习", "学校", "考试", "培训", "留学"],
        "健康": ["医疗", "疫情", "健康", "医院", "疾病", "养生", "医保"]
    }
    
    # 各主题的情感倾向（为模拟数据设置一些规则）
    topic_sentiment_bias = {
        "科技": {"正面": 0.6, "负面": 0.2, "中性": 0.2},
        "财经": {"正面": 0.4, "负面": 0.4, "中性": 0.2},
        "教育": {"正面": 0.5, "负面": 0.3, "中性": 0.2},
        "健康": {"正面": 0.3, "负面": 0.5, "中性": 0.2}
    }
    
    for topic, related_words in topics.items():
        for keyword in keywords:
            if keyword in related_words or keyword == topic:
                for page in range(pages):
                    # 根据主题生成特定情感分布的新闻
                    for _ in range(10):  # 每页10条新闻
                        # 使用主题特定的情感偏好
                        sentiment = np.random.choice(sentiments, p=list(topic_sentiment_bias[topic].values()))
                        
                        # 生成模拟的新闻标题和内容
                        title_length = np.random.randint(10, 20)
                        content_length = np.random.randint(50, 200)
                        
                        # 标题根据情感添加一些特定词汇
                        sentiment_words = {
                            "正面": ["成功", "突破", "利好", "增长", "优秀", "创新"],
                            "负面": ["困难", "下滑", "风险", "问题", "挑战", "危机"],
                            "中性": ["分析", "观察", "报道", "解读", "介绍", "调查"]
                        }
                        
                        # 随机选择情感词
                        sentiment_word = np.random.choice(sentiment_words[sentiment])
                        title = f"{topic}{np.random.choice(related_words)}{sentiment_word}相关报道" + str(np.random.randint(1, 100))
                        
                        # 生成发布时间和更新时间
                        days_ago = np.random.randint(0, 30)
                        hours_ago = np.random.randint(0, 24)
                        publish_time = (datetime.datetime.now() - 
                                       datetime.timedelta(days=days_ago, hours=hours_ago))
                        
                        news_data.append({
                            "id": len(news_data) + 1,
                            "title": title,
                            "content": f"{title}的详细内容，包含{keyword}的相关信息..." * (content_length // 20),
                            "source": np.random.choice(["新华网", "人民日报", "中国日报", "环球时报", "经济观察报"]),
                            "publish_time": publish_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "category": topic,
                            "sentiment": sentiment,
                            "keywords": [keyword] + np.random.choice(related_words, 2).tolist()
                        })
    
    # 转换为DataFrame并返回
    df = pd.DataFrame(news_data)
    print(f"成功获取{len(df)}条新闻数据")
    return df

def preprocess_text(text):
    """
    文本预处理函数
    
    参数:
        text (str): 输入文本
    
    返回:
        str: 处理后的文本
    """
    # 去除HTML标签
    text = re.sub(r'<.*?>', '', text)
    # 去除URL
    text = re.sub(r'http\S+', '', text)
    # 去除数字
    text = re.sub(r'\d+', '', text)
    # 去除标点符号
    text = re.sub(r'[^\w\s]', '', text)
    # 去除多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_features(df):
    """
    从文本中提取特征
    
    参数:
        df (pd.DataFrame): 包含新闻数据的DataFrame
    
    返回:
        pd.DataFrame: 增加了特征的DataFrame
    """
    print("正在提取文本特征...")
    
    # 添加处理后的文本列
    df['processed_title'] = df['title'].apply(preprocess_text)
    df['processed_content'] = df['content'].apply(preprocess_text)
    
    # 合并标题和内容
    df['full_text'] = df['processed_title'] + ' ' + df['processed_content']
    
    # 使用jieba分词
    df['words'] = df['full_text'].apply(lambda x: ' '.join(jieba.cut(x)))
    
    # 提取关键词（TF-IDF）
    df['extracted_keywords'] = df['full_text'].apply(
        lambda x: ' '.join(jieba.analyse.extract_tags(x, topK=5)))
    
    # 计算文本长度
    df['title_length'] = df['title'].apply(len)
    df['content_length'] = df['content'].apply(len)
    
    # 将发布时间转换为datetime对象
    df['publish_datetime'] = pd.to_datetime(df['publish_time'])
    
    # 提取发布时间的小时
    df['publish_hour'] = df['publish_datetime'].dt.hour
    
    # 是否工作日发布
    df['is_weekend'] = df['publish_datetime'].dt.weekday >= 5
    
    print("特征提取完成！")
    return df

# -----------------------------------------------------------------------------
# 第2部分：数据分析与可视化
# -----------------------------------------------------------------------------

def analyze_news_data(df):
    """
    分析新闻数据并生成可视化
    
    参数:
        df (pd.DataFrame): 包含新闻数据的DataFrame
    """
    print("开始数据分析与可视化...")
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 1. 各情感类别的新闻数量
    plt.figure(figsize=(10, 6))
    sentiment_counts = df['sentiment'].value_counts()
    sentiment_counts.plot(kind='bar', color=['green', 'red', 'blue'])
    plt.title('新闻情感分布')
    plt.xlabel('情感类别')
    plt.ylabel('新闻数量')
    plt.tight_layout()
    plt.savefig('output/sentiment_distribution.png')
    
    # 2. 各类别新闻的情感分布
    plt.figure(figsize=(12, 8))
    category_sentiment = pd.crosstab(df['category'], df['sentiment'], normalize='index')
    category_sentiment.plot(kind='bar', stacked=True, colormap='viridis')
    plt.title('各类别新闻的情感分布')
    plt.xlabel('新闻类别')
    plt.ylabel('比例')
    plt.legend(title='情感')
    plt.tight_layout()
    plt.savefig('output/category_sentiment.png')
    
    # 3. 发布时间分析
    plt.figure(figsize=(10, 6))
    df['publish_datetime'].dt.date.value_counts().sort_index().plot(kind='line')
    plt.title('新闻发布日期分布')
    plt.xlabel('日期')
    plt.ylabel('新闻数量')
    plt.tight_layout()
    plt.savefig('output/publish_date_distribution.png')
    
    # 4. 发布小时分析
    plt.figure(figsize=(10, 6))
    df['publish_hour'].value_counts().sort_index().plot(kind='bar')
    plt.title('新闻发布小时分布')
    plt.xlabel('小时')
    plt.ylabel('新闻数量')
    plt.xticks(range(0, 24))
    plt.tight_layout()
    plt.savefig('output/publish_hour_distribution.png')
    
    # 5. 词云分析 (这里简化为关键词频率分析)
    words = ' '.join(df['extracted_keywords']).split()
    word_freq = Counter(words)
    common_words = word_freq.most_common(20)
    
    plt.figure(figsize=(12, 6))
    plt.bar([word for word, count in common_words], [count for word, count in common_words])
    plt.title('新闻关键词频率分析(Top 20)')
    plt.xlabel('关键词')
    plt.ylabel('频率')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig('output/keyword_frequency.png')
    
    # 6. 情感与文本长度的关系
    plt.figure(figsize=(10, 6))
    sentiment_length = df.groupby('sentiment')['content_length'].mean().sort_values()
    sentiment_length.plot(kind='bar', color=['red', 'blue', 'green'])
    plt.title('各情感类别的平均内容长度')
    plt.xlabel('情感类别')
    plt.ylabel('平均长度(字符)')
    plt.tight_layout()
    plt.savefig('output/sentiment_length_relationship.png')
    
    print("数据分析与可视化完成，结果保存在output目录")

# -----------------------------------------------------------------------------
# 第3部分：机器学习模型训练
# -----------------------------------------------------------------------------

def train_sentiment_model(df):
    """
    训练情感分析模型
    
    参数:
        df (pd.DataFrame): 包含新闻数据的DataFrame
    
    返回:
        dict: 包含模型和向量化器的字典
    """
    print("开始训练情感分析模型...")
    
    # 准备训练数据
    X = df['words']  # 分词后的文本
    y = df['sentiment']  # 情感标签
    
    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    
    # 使用TF-IDF向量化
    tfidf_vectorizer = TfidfVectorizer(max_features=5000)
    X_train_tfidf = tfidf_vectorizer.fit_transform(X_train)
    X_test_tfidf = tfidf_vectorizer.transform(X_test)
    
    # 训练逻辑回归模型
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train_tfidf, y_train)
    
    # 评估模型
    y_pred = model.predict(X_test_tfidf)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"模型训练完成，准确率: {accuracy:.4f}")
    print("分类报告:")
    print(classification_report(y_test, y_pred))
    
    # 返回模型和向量化器
    return {
        'model': model,
        'vectorizer': tfidf_vectorizer,
        'accuracy': accuracy,
        'classes': model.classes_
    }

def predict_sentiment(text, model_data):
    """
    预测给定文本的情感
    
    参数:
        text (str): 输入文本
        model_data (dict): 包含模型和向量化器的字典
    
    返回:
        dict: 预测结果和概率
    """
    # 预处理文本
    processed_text = preprocess_text(text)
    words = ' '.join(jieba.cut(processed_text))
    
    # 向量化
    text_tfidf = model_data['vectorizer'].transform([words])
    
    # 预测
    sentiment = model_data['model'].predict(text_tfidf)[0]
    
    # 预测概率
    proba = model_data['model'].predict_proba(text_tfidf)[0]
    probabilities = {cls: float(prob) for cls, prob in zip(model_data['classes'], proba)}
    
    return {
        'sentiment': sentiment,
        'probabilities': probabilities
    }

# -----------------------------------------------------------------------------
# 第4部分：Web应用开发 (Flask)
# -----------------------------------------------------------------------------

def create_web_app(model_data):
    """
    创建Flask Web应用
    
    参数:
        model_data (dict): 包含模型和向量化器的字典
    
    返回:
        Flask: Flask应用实例
    """
    app = Flask(__name__)
    
    # 创建模板目录
    os.makedirs('templates', exist_ok=True)
    
    # 创建简单的HTML模板文件
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>新闻情感分析系统</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }
                .container { max-width: 800px; margin: 0 auto; }
                h1 { color: #333; }
                textarea { width: 100%; height: 150px; padding: 10px; margin-bottom: 10px; }
                button { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; cursor: pointer; }
                button:hover { background-color: #45a049; }
                #result { margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px; display: none; }
                .positive { color: green; }
                .negative { color: red; }
                .neutral { color: blue; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>新闻情感分析系统</h1>
                <p>输入新闻文本，分析其情感倾向（正面、负面或中性）。</p>
                
                <textarea id="news-text" placeholder="请输入新闻文本..."></textarea>
                <button onclick="analyzeText()">分析情感</button>
                
                <div id="result">
                    <h2>分析结果</h2>
                    <p>情感倾向: <span id="sentiment"></span></p>
                    <p>置信度:</p>
                    <ul>
                        <li>正面: <span id="positive"></span></li>
                        <li>负面: <span id="negative"></span></li>
                        <li>中性: <span id="neutral"></span></li>
                    </ul>
                    <p>关键词: <span id="keywords"></span></p>
                </div>
            </div>
            
            <script>
                function analyzeText() {
                    const text = document.getElementById('news-text').value;
                    if (!text) {
                        alert('请输入文本');
                        return;
                    }
                    
                    fetch('/analyze', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ text }),
                    })
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('result').style.display = 'block';
                        
                        let sentimentEl = document.getElementById('sentiment');
                        sentimentEl.textContent = data.sentiment;
                        
                        // 添加颜色样式
                        sentimentEl.className = '';
                        if (data.sentiment === '正面') {
                            sentimentEl.classList.add('positive');
                        } else if (data.sentiment === '负面') {
                            sentimentEl.classList.add('negative');
                        } else {
                            sentimentEl.classList.add('neutral');
                        }
                        
                        // 显示概率
                        document.getElementById('positive').textContent = 
                            (data.probabilities['正面'] * 100).toFixed(2) + '%';
                        document.getElementById('negative').textContent = 
                            (data.probabilities['负面'] * 100).toFixed(2) + '%';
                        document.getElementById('neutral').textContent = 
                            (data.probabilities['中性'] * 100).toFixed(2) + '%';
                        
                        // 显示关键词
                        document.getElementById('keywords').textContent = data.keywords.join(', ');
                    })
                    .catch(error => {
                        console.error('分析出错:', error);
                        alert('分析失败，请稍后重试');
                    });
                }
            </script>
        </body>
        </html>
        ''')
    
    with open('templates/stats.html', 'w', encoding='utf-8') as f:
        f.write('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>情感分析统计</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }
                .container { max-width: 800px; margin: 0 auto; }
                h1 { color: #333; }
                .chart-container { margin: 20px 0; }
                img { max-width: 100%; border: 1px solid #ddd; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>情感分析统计</h1>
                <p>以下是系统分析的情感分布和趋势图表。</p>
                
                <div class="chart-container">
                    <h2>情感分布</h2>
                    <img src="/static/sentiment_distribution.png" alt="情感分布">
                </div>
                
                <div class="chart-container">
                    <h2>类别情感分布</h2>
                    <img src="/static/category_sentiment.png" alt="类别情感分布">
                </div>
                
                <div class="chart-container">
                    <h2>发布时间分析</h2>
                    <img src="/static/publish_date_distribution.png" alt="发布日期分布">
                </div>
                
                <div class="chart-container">
                    <h2>关键词频率</h2>
                    <img src="/static/keyword_frequency.png" alt="关键词频率">
                </div>
                
                <p><a href="/">返回首页</a></p>
            </div>
        </body>
        </html>
        ''')
    
    # 创建静态文件目录
    os.makedirs('static', exist_ok=True)
    
    # 将输出图片复制到静态目录
    if os.path.exists('output'):
        for filename in os.listdir('output'):
            if filename.endswith('.png'):
                # 创建符号链接或复制文件
                src = os.path.join('output', filename)
                dst = os.path.join('static', filename)
                try:
                    os.symlink(os.path.abspath(src), dst)
                except:
                    # 如果符号链接失败，直接复制文件
                    import shutil
                    shutil.copy2(src, dst)
    
    @app.route('/')
    def index():
        """首页"""
        return render_template('index.html')
    
    @app.route('/analyze', methods=['POST'])
    def analyze_text():
        """分析文本情感"""
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': '文本不能为空'}), 400
        
        result = predict_sentiment(text, model_data)
        
        # 提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=5)
        
        response = {
            'sentiment': result['sentiment'],
            'probabilities': result['probabilities'],
            'keywords': keywords
        }
        
        return jsonify(response)
    
    @app.route('/stats')
    def stats():
        """统计页面"""
        return render_template('stats.html')
    
    return app

# -----------------------------------------------------------------------------
# 综合实战：完整流程
# -----------------------------------------------------------------------------

def main():
    """主函数，运行完整应用流程"""
    print("=" * 60)
    print("新闻情感分析系统 - Python多领域应用实战案例")
    print("=" * 60)
    
    # 1. 获取数据
    keywords = ["人工智能", "经济", "教育", "健康"]
    news_df = fetch_news_data(keywords, pages=3)
    
    # 2. 数据处理与特征提取
    processed_df = extract_features(news_df)
    
    # 3. 数据分析与可视化
    analyze_news_data(processed_df)
    
    # 4. 训练机器学习模型
    model_data = train_sentiment_model(processed_df)
    
    # 5. 测试模型
    test_texts = [
        "人工智能技术取得重大突破，将为经济发展注入新动力",
        "市场低迷导致经济下滑，多家企业面临倒闭风险",
        "教育改革政策出台，专家进行了分析和解读"
    ]
    
    print("\n模型测试:")
    for text in test_texts:
        result = predict_sentiment(text, model_data)
        print(f"文本: {text}")
        print(f"预测情感: {result['sentiment']}")
        print(f"概率分布: {result['probabilities']}")
        print("-" * 40)
    
    # 6. 创建Web应用
    app = create_web_app(model_data)
    
    print("\n完整流程演示完毕!")
    print("要启动Web应用，请取消注释以下代码并运行:")
    print("app.run(debug=True, host='0.0.0.0', port=5000)")
    
    # 运行Web应用（取消注释即可启动）
    # app.run(debug=True, host='0.0.0.0', port=5000)
    
    return app  # 返回app对象以便外部使用

if __name__ == "__main__":
    app = main()
    
    # 取消以下注释以启动Web应用
    # app.run(debug=True, host='0.0.0.0', port=5000) 