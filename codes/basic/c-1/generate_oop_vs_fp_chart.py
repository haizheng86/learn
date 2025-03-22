import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 确保图片目录存在
script_dir = Path(__file__).resolve().parent
root_dir = script_dir.parent.parent
images_dir = root_dir / "notes" / "images"
images_dir.mkdir(exist_ok=True, parents=True)

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']  # 用来正常显示中文
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 创建一个Figure和Axes对象
fig, axes = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 2]})
fig.patch.set_facecolor('#f8f9fa')  # 设置背景颜色

# 定义编程范式对比数据
paradigms = ['面向对象编程(OOP)', '函数式编程(FP)']
features = [
    '代码组织',
    '状态管理',
    '并发处理',
    '代码复用',
    '可维护性',
    '学习曲线'
]

# 创建评分矩阵 (1-5分)
scores = np.array([
    [5, 3],  # 代码组织
    [4, 5],  # 状态管理
    [3, 5],  # 并发处理
    [4, 4],  # 代码复用
    [4, 3],  # 可维护性
    [3, 4],  # 学习曲线
])

# 绘制雷达图
ax = axes[0]
angles = np.linspace(0, 2*np.pi, len(features), endpoint=False)
angles = np.concatenate((angles, [angles[0]]))  # 闭合雷达图

# 绘制雷达图
for i, paradigm in enumerate(paradigms):
    values = np.concatenate((scores[:, i], [scores[0, i]]))  # 闭合数据
    ax.plot(angles, values, 'o-', linewidth=2, label=paradigm, alpha=0.8)
    ax.fill(angles, values, alpha=0.25)

# 设置雷达图属性
ax.set_xticks(angles[:-1])
ax.set_xticklabels(features, fontsize=10)
ax.set_ylim(0, 5)
ax.set_title('面向对象编程vs函数式编程对比分析', fontsize=16, fontweight='bold', pad=20)

# 添加图例
ax.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))

# 添加代码示例表格
code_examples = [
    ['编程范式', '代码示例', '特点'],
    ['面向对象编程', 'class Student:\n    def __init__(self, name):\n        self.name = name\n    def greet(self):\n        return f"Hello, {self.name}"', '封装、继承、多态'],
    ['函数式编程', 'def greet(name):\n    return lambda: f"Hello, {name}"\n\nstudent = greet("Alice")\nprint(student())', '纯函数、不可变性、高阶函数']
]

# 创建表格
ax = axes[1]
ax.axis('tight')
ax.axis('off')
table = ax.table(cellText=[row for row in code_examples], 
                 colWidths=[0.15, 0.45, 0.4],
                 cellLoc='left',
                 loc='center')

# 设置表格样式
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 1.8)

# 为表头设置样式
for (i, j), cell in table.get_celld().items():
    if i == 0:  # 表头行
        cell.set_text_props(fontweight='bold', color='white')
        cell.set_facecolor('#4472C4')
    elif j == 0:  # 第一列
        cell.set_text_props(fontweight='bold')
        cell.set_facecolor('#E9EDF4')
    
    # 设置单元格边框
    cell.set_edgecolor('white')
    
    # 设置行高
    if i > 0:
        cell._height = 0.15

# 添加说明文本
fig.text(0.5, 0.02, 
         "说明：评分基于1-5分制，5分表示最优。\n"
         "结论：OOP适合大型项目和组织复杂系统，FP适合并发处理和数据处理。",
         ha='center', fontsize=10, style='italic', 
         bbox=dict(boxstyle='round,pad=0.5', facecolor='#F2F2F2', alpha=0.5))

# 调整布局
plt.tight_layout(rect=[0, 0.05, 1, 0.95])
plt.subplots_adjust(hspace=0.4)

# 保存图片
output_file = images_dir / "oop_vs_fp_comparison.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"图表已保存到: {output_file}")

# 同时创建一个目录图片作为备份
alt_output_file = script_dir / "oop_vs_fp_comparison.png"
plt.savefig(alt_output_file, dpi=150, bbox_inches='tight')
print(f"备份图表已保存到: {alt_output_file}")

plt.close()

print("""
要在Markdown中显示此图表，请使用以下代码：

![面向对象编程vs函数式编程](./images/oop_vs_fp_comparison.png)

如果您在将此图像添加到文档中遇到问题，可以尝试使用绝对路径。
""") 