# PDF智能分析助手
# 一个使用Python和大模型API实现的文档分析工具
import os
import re
import fitz  # PyMuPDF
import requests
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# 加载环境变量
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

class PDFIntelligentAnalyzer:
    """PDF智能分析助手,可以提取文本、分析内容并生成摘要"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or API_KEY
        if not self.api_key:
            raise ValueError("需要提供API密钥")
        self.extracted_text = ""
        self.analysis_results = {}
    
    def extract_text_from_pdf(self, pdf_path):
        """从PDF文件中提取文本内容"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")
            
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_content.append(page.get_text())
            
            self.extracted_text = "\n".join(text_content)
            print(f"成功从{pdf_path}提取了{len(self.extracted_text)}个字符")
            return self.extracted_text
        except Exception as e:
            print(f"提取PDF文本时出错: {e}")
            return None
    
    def _call_llm_api(self, prompt, max_tokens=500):
        """调用大模型API获取回复"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"API请求失败: {response.status_code}, {response.text}")
            return None
    
    def analyze_text(self, text=None, analysis_types=None):
        """分析文本内容，提取关键信息"""
        if text is None:
            text = self.extracted_text
        
        if not text:
            print("没有要分析的文本")
            return None
        
        # 默认分析类型
        if analysis_types is None:
            analysis_types = ["summary", "key_points", "topics", "entities"]
        
        analysis_prompts = {
            "summary": "请对以下文本生成一个简短的摘要(200字以内):\n\n",
            "key_points": "请从以下文本中提取5-7个关键点:\n\n",
            "topics": "请从以下文本中识别主要主题或类别，并以JSON格式返回:\n\n",
            "entities": "请从以下文本中提取重要的实体(人名、地点、组织等)，并以JSON格式返回:\n\n",
            "sentiment": "请分析以下文本的情感倾向(积极、消极或中性)，并给出0-1的得分，以JSON格式返回:\n\n"
        }
        
        # 如果文本太长，截取前10000个字符进行分析
        if len(text) > 10000:
            analysis_text = text[:10000] + "...(内容已截断)"
        else:
            analysis_text = text
        
        results = {}
        
        # 使用线程池并行处理多个分析请求
        with ThreadPoolExecutor(max_workers=min(len(analysis_types), 3)) as executor:
            futures = {}
            
            for analysis_type in analysis_types:
                if analysis_type in analysis_prompts:
                    prompt = analysis_prompts[analysis_type] + analysis_text
                    futures[executor.submit(self._call_llm_api, prompt)] = analysis_type
            
            for future in tqdm(futures, desc="分析进度"):
                analysis_type = futures[future]
                try:
                    result = future.result()
                    if result:
                        results[analysis_type] = result
                except Exception as e:
                    print(f"处理{analysis_type}分析时出错: {e}")
        
        self.analysis_results = results
        return results
    
    def generate_report(self, output_path="report.html"):
        """生成分析报告"""
        if not self.analysis_results:
            print("没有可用的分析结果")
            return False
        
        # 创建HTML报告
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>文档分析报告</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 10px; }
                h2 { color: #3498db; margin-top: 30px; }
                .card { background: #f9f9f9; border-radius: 5px; padding: 15px; margin: 15px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                pre { background: #f1f1f1; padding: 10px; border-radius: 3px; overflow-x: auto; }
            </style>
        </head>
        <body>
            <h1>文档分析报告</h1>
        """
        
        # 添加摘要
        if "summary" in self.analysis_results:
            html_content += f"""
            <div class="card">
                <h2>文档摘要</h2>
                <p>{self.analysis_results["summary"]}</p>
            </div>
            """
        
        # 添加关键点
        if "key_points" in self.analysis_results:
            html_content += f"""
            <div class="card">
                <h2>关键点</h2>
                <div>{self.analysis_results["key_points"]}</div>
            </div>
            """
        
        # 添加主题和实体
        for section in ["topics", "entities", "sentiment"]:
            if section in self.analysis_results:
                html_content += f"""
                <div class="card">
                    <h2>{"主题分类" if section == "topics" else "重要实体" if section == "entities" else "情感分析"}</h2>
                    <pre>{self.analysis_results[section]}</pre>
                </div>
                """
        
        html_content += """
        <footer style="margin-top: 50px; color: #7f8c8d; text-align: center; font-size: 0.8em;">
            <p>由PDF智能分析助手生成 &copy; 2025</p>
        </footer>
        </body>
        </html>
        """
        
        # 保存HTML报告
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"分析报告已保存至: {output_path}")
            return True
        except Exception as e:
            print(f"保存报告时出错: {e}")
            return False

# 使用示例
if __name__ == "__main__":
    # 检查命令行参数
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = input("请输入PDF文件路径: ")
    
    # 创建分析器实例
    analyzer = PDFIntelligentAnalyzer()
    
    # 提取文本
    text = analyzer.extract_text_from_pdf(pdf_path)
    
    if text:
        # 进行分析
        results = analyzer.analyze_text()
        
        # 生成报告
        if results:
            analyzer.generate_report()
            print("分析完成，报告已生成!")
        else:
            print("分析失败，未能生成报告") 