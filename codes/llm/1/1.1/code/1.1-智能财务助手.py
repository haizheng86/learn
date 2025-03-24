# finance_assistant.py
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
import os
import json
import requests
from dotenv import load_dotenv

# 加载环境变量（API密钥等）
load_dotenv()

class FinanceAssistant:
    def __init__(self, data_file=None):
        self.data_file = data_file
        self.transactions = None
        self.ai_api_key = os.getenv("OPENAI_API_KEY")
        
        # 如果提供了数据文件，立即加载
        if self.data_file and os.path.exists(self.data_file):
            self.load_data()
        else:
            # 创建示例数据用于演示
            self.create_sample_data()
    
    def create_sample_data(self):
        """创建示例财务数据用于演示"""
        # 生成随机日期和消费金额
        np.random.seed(42)  # 确保可重复性
        
        # 生成100条交易记录
        dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
        
        # 定义消费类别和商家
        categories = ['餐饮', '购物', '交通', '娱乐', '住房', '医疗', '教育']
        merchants = {
            '餐饮': ['麦当劳', '肯德基', '必胜客', '星巴克', '本地餐厅'],
            '购物': ['淘宝', '京东', '苏宁', '天猫', '线下商场'],
            '交通': ['滴滴', '地铁', '公交', '加油站', '高铁'],
            '娱乐': ['电影院', '游戏充值', '视频会员', '演唱会', 'KTV'],
            '住房': ['房租', '物业费', '水电费', '煤气费', '宽带费'],
            '医疗': ['医院', '药店', '保健品', '体检', '牙医'],
            '教育': ['线上课程', '培训机构', '书店', '学费', '文具']
        }
        
        # 生成交易数据
        transactions = []
        for date in dates:
            # 每天1-3笔交易
            for _ in range(np.random.randint(1, 4)):
                category = np.random.choice(categories)
                merchant = np.random.choice(merchants[category])
                amount = np.random.normal(loc=100, scale=50) if category in ['餐饮', '交通'] else np.random.normal(loc=300, scale=150)
                amount = max(10, round(amount, 2))  # 确保金额为正
                
                transactions.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'category': category,
                    'merchant': merchant,
                    'amount': amount,
                    'notes': f'{date.strftime("%Y-%m-%d")}在{merchant}消费'
                })
        
        self.transactions = pd.DataFrame(transactions)
        print(f"已创建{len(self.transactions)}条示例交易记录")
        
        # 保存示例数据
        self.transactions.to_csv('sample_finance_data.csv', index=False)
        self.data_file = 'sample_finance_data.csv'
    
    def load_data(self):
        """加载财务数据"""
        try:
            self.transactions = pd.read_csv(self.data_file)
            # 确保日期格式正确
            self.transactions['date'] = pd.to_datetime(self.transactions['date'])
            print(f"成功加载{len(self.transactions)}条交易记录")
        except Exception as e:
            print(f"加载数据失败: {e}")
            return False
        return True
    
    def analyze_spending(self):
        """分析消费模式"""
        if self.transactions is None or len(self.transactions) == 0:
            print("没有可分析的数据")
            return None
        
        # 转换日期列为日期格式
        if not pd.api.types.is_datetime64_dtype(self.transactions['date']):
            self.transactions['date'] = pd.to_datetime(self.transactions['date'])
        
        # 按类别汇总消费
        category_summary = self.transactions.groupby('category')['amount'].agg(['sum', 'count']).reset_index()
        category_summary.columns = ['类别', '总金额', '交易次数']
        category_summary['平均消费'] = category_summary['总金额'] / category_summary['交易次数']
        category_summary = category_summary.sort_values('总金额', ascending=False)
        
        # 按月份汇总消费
        self.transactions['月份'] = self.transactions['date'].dt.strftime('%Y-%m')
        monthly_summary = self.transactions.groupby(['月份', 'category'])['amount'].sum().reset_index()
        
        return {
            'category_summary': category_summary,
            'monthly_summary': monthly_summary
        }
    
    def visualize_spending(self):
        """可视化消费模式"""
        analysis = self.analyze_spending()
        if not analysis:
            return
        
        # 设置样式
        sns.set(style="whitegrid")
        
        # 创建图形
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. 消费类别饼图
        axes[0, 0].pie(
            analysis['category_summary']['总金额'],
            labels=analysis['category_summary']['类别'],
            autopct='%1.1f%%',
            startangle=90
        )
        axes[0, 0].set_title('各类别消费占比', fontsize=14)
        
        # 2. 类别消费条形图
        sns.barplot(
            data=analysis['category_summary'],
            x='类别',
            y='总金额',
            ax=axes[0, 1]
        )
        axes[0, 1].set_title('各类别消费总额', fontsize=14)
        axes[0, 1].set_xlabel('消费类别')
        axes[0, 1].set_ylabel('金额 (元)')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 3. 月度消费趋势
        monthly_total = self.transactions.groupby('月份')['amount'].sum().reset_index()
        sns.lineplot(
            data=monthly_total,
            x='月份',
            y='amount',
            marker='o',
            ax=axes[1, 0]
        )
        axes[1, 0].set_title('月度消费趋势', fontsize=14)
        axes[1, 0].set_xlabel('月份')
        axes[1, 0].set_ylabel('总消费 (元)')
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 4. 各类别月度消费热力图
        pivot_data = analysis['monthly_summary'].pivot(index='月份', columns='category', values='amount')
        sns.heatmap(
            pivot_data,
            annot=True,
            fmt='.0f',
            cmap='YlGnBu',
            ax=axes[1, 1]
        )
        axes[1, 1].set_title('各类别月度消费热力图', fontsize=14)
        
        plt.tight_layout()
        plt.savefig('finance_analysis.png')
        plt.show()
        
        return 'finance_analysis.png'
    
    def get_ai_insights(self):
        """使用AI大模型获取财务洞察"""
        if not self.ai_api_key:
            print("未设置AI API密钥，无法获取AI洞察")
            return "请配置API密钥以获取AI洞察"
        
        analysis = self.analyze_spending()
        if not analysis:
            return "没有足够的数据进行分析"
        
        # 准备数据摘要
        category_data = analysis['category_summary'].to_dict(orient='records')
        monthly_total = self.transactions.groupby('月份')['amount'].sum().to_dict()
        
        # 构建提示
        prompt = f"""
        作为一名财务顾问，请基于以下消费数据提供个性化的财务洞察和建议：
        
        消费类别摘要:
        {json.dumps(category_data, ensure_ascii=False, indent=2)}
        
        月度消费总额:
        {json.dumps(monthly_total, ensure_ascii=False, indent=2)}
        
        请提供以下内容:
        1. 主要消费领域分析
        2. 消费模式中的异常或需要注意的地方
        3. 具体的节省开支建议
        4. 智能预算分配方案
        5. 储蓄和投资建议
        """
        
        # 调用AI API
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.ai_api_key}"
                },
                json={
                    "model": "gpt-4-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                }
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                print(f"API调用失败: {response.status_code}")
                return f"API调用失败: {response.text}"
                
        except Exception as e:
            print(f"获取AI洞察时出错: {e}")
            return f"获取AI洞察时出错: {str(e)}"
    
    def generate_saving_plan(self, target_amount, months):
        """生成储蓄计划"""
        if self.transactions is None or len(self.transactions) == 0:
            return "没有足够的数据生成储蓄计划"
        
        # 计算月均支出
        monthly_expenses = self.transactions.groupby('月份')['amount'].sum().mean()
        
        # 分析可削减的开支
        analysis = self.analyze_spending()
        category_summary = analysis['category_summary']
        
        # 按重要性对消费类别进行分类
        essential_categories = ['住房', '医疗', '教育']
        flexible_categories = ['餐饮', '交通']
        discretionary_categories = ['购物', '娱乐']
        
        # 计算每类消费的总额
        essential_spending = category_summary[category_summary['类别'].isin(essential_categories)]['总金额'].sum()
        flexible_spending = category_summary[category_summary['类别'].isin(flexible_categories)]['总金额'].sum()
        discretionary_spending = category_summary[category_summary['类别'].isin(discretionary_categories)]['总金额'].sum()
        
        # 计算每月需要储蓄的金额
        monthly_saving_required = target_amount / months
        
        # 计算可以节省的金额
        potential_savings = {
            '固定开支优化': essential_spending * 0.05,  # 假设固定开支可优化5%
            '灵活开支优化': flexible_spending * 0.15,   # 灵活开支可优化15%
            '非必要开支优化': discretionary_spending * 0.30  # 非必要开支可优化30%
        }
        
        total_potential_savings = sum(potential_savings.values())
        
        # 转换为月度潜在节省
        monthly_potential_savings = total_potential_savings / len(self.transactions['月份'].unique())
        
        # 生成储蓄计划
        plan = {
            '目标金额': target_amount,
            '储蓄期限(月)': months,
            '月均支出': monthly_expenses,
            '每月需储蓄金额': monthly_saving_required,
            '每月可节省金额': monthly_potential_savings,
            '是否可行': monthly_potential_savings >= monthly_saving_required,
            '节省建议': potential_savings,
            '调整后月度预算': {}
        }
        
        # 如果节省额不足，计算需要的额外收入
        if plan['是否可行'] == False:
            plan['需额外收入'] = monthly_saving_required - monthly_potential_savings
        
        # 生成调整后的预算
        for category in category_summary['类别']:
            current_spending = category_summary[category_summary['类别'] == category]['总金额'].values[0]
            reduction_rate = 0
            
            if category in essential_categories:
                reduction_rate = 0.05
            elif category in flexible_categories:
                reduction_rate = 0.15
            elif category in discretionary_categories:
                reduction_rate = 0.30
            
            plan['调整后月度预算'][category] = current_spending * (1 - reduction_rate) / len(self.transactions['月份'].unique())
        
        return plan

# 使用示例
if __name__ == "__main__":
    assistant = FinanceAssistant()
    
    # 分析并可视化消费
    print("正在分析消费数据...")
    assistant.visualize_spending()
    
    # 获取AI洞察
    print("\n获取AI财务洞察...")
    insights = assistant.get_ai_insights()
    print(insights)
    
    # 生成储蓄计划
    print("\n生成储蓄计划...")
    saving_plan = assistant.generate_saving_plan(target_amount=10000, months=6)
    print(json.dumps(saving_plan, ensure_ascii=False, indent=2)) 