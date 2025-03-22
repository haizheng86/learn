import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap

# 确保图片目录存在
script_dir = Path(__file__).resolve().parent
root_dir = script_dir.parent.parent
images_dir = root_dir / "notes" / "images"
images_dir.mkdir(exist_ok=True, parents=True)

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 创建自定义颜色映射
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD', '#D4A5A5']
n_bins = 256
custom_cmap = LinearSegmentedColormap.from_list('custom', colors, N=n_bins)

# 创建图表
fig = plt.figure(figsize=(15, 10))
fig.patch.set_facecolor('#FFFFFF')

# 创建子图
gs = plt.GridSpec(2, 1, height_ratios=[3, 2], hspace=0.4)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])

# 设置背景样式
for ax in [ax1, ax2]:
    ax.set_facecolor('#FFFFFF')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#E0E0E0')
    ax.spines['bottom'].set_color('#E0E0E0')
    ax.grid(True, linestyle='--', alpha=0.3)

# 定义数据
categories = ['Python', 'Java', 'C++', 'JavaScript']
metrics = ['性能', '易用性', '生态系统', '就业机会', '学习曲线']

# 创建数据矩阵
data = np.array([
    [4.5, 3.8, 4.2, 4.0],  # 性能
    [4.8, 3.5, 3.2, 4.0],  # 易用性
    [4.7, 4.0, 3.8, 4.5],  # 生态系统
    [4.9, 4.2, 3.9, 4.3],  # 就业机会
    [4.6, 3.7, 3.5, 4.1],  # 学习曲线
])

# 绘制雷达图
angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False)
angles = np.concatenate((angles, [angles[0]]))  # 闭合雷达图

# 绘制雷达图
for i, category in enumerate(categories):
    values = np.concatenate((data[:, i], [data[0, i]]))
    ax1.plot(angles, values, 'o-', linewidth=2, label=category, alpha=0.8)
    ax1.fill(angles, values, alpha=0.25)

# 设置雷达图属性
ax1.set_xticks(angles[:-1])
ax1.set_xticklabels(metrics, fontsize=10, fontweight='bold')
ax1.set_ylim(0, 5)
ax1.set_title('编程语言特性对比分析', fontsize=16, fontweight='bold', pad=20)

# 添加图例
legend = ax1.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
legend.get_frame().set_facecolor('#FFFFFF')
legend.get_frame().set_alpha(0.8)

# 添加代码示例表格
code_examples = [
    ['语言', '代码示例', '特点'],
    ['Python', 'def greet(name):\n    return f"Hello, {name}"', '简洁优雅'],
    ['Java', 'public String greet(String name) {\n    return "Hello, " + name;\n}', '强类型'],
    ['C++', 'string greet(string name) {\n    return "Hello, " + name;\n}', '高性能'],
    ['JavaScript', 'const greet = name => `Hello, ${name}`', '灵活多变']
]

# 创建表格
ax2.axis('tight')
ax2.axis('off')
table = ax2.table(cellText=[row for row in code_examples], 
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
        cell.set_facecolor('#4ECDC4')  # 使用主题色
    elif j == 0:  # 第一列
        cell.set_text_props(fontweight='bold')
        cell.set_facecolor('#F7F7F7')
    
    # 设置单元格边框
    cell.set_edgecolor('#E0E0E0')
    
    # 设置行高
    if i > 0:
        cell._height = 0.15

# 添加说明文本
fig.text(0.5, 0.02, 
         "说明：评分基于1-5分制，5分表示最优。\n"
         "结论：Python在易用性和就业机会方面表现突出，适合初学者入门。",
         ha='center', fontsize=10, style='italic', 
         bbox=dict(boxstyle='round,pad=0.5', facecolor='#F7F7F7', alpha=0.8,
                  edgecolor='#E0E0E0'))

# 调整布局
plt.tight_layout(rect=[0, 0.05, 1, 0.95])

# 保存图片
output_file = images_dir / "modern_programming_languages_comparison.png"
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
print(f"图表已保存到: {output_file}")

# 同时创建一个目录图片作为备份
alt_output_file = script_dir / "modern_programming_languages_comparison.png"
plt.savefig(alt_output_file, dpi=300, bbox_inches='tight', facecolor='white')
print(f"备份图表已保存到: {alt_output_file}")

plt.close()

print("""
要在Markdown中显示此图表，请使用以下代码：

![现代编程语言对比分析](./images/modern_programming_languages_comparison.png)

如果您在将此图像添加到文档中遇到问题，可以尝试使用绝对路径。
""") 