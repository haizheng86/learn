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

# 定义数据结构和操作
data_structures = ['列表(List)', '元组(Tuple)', '字典(Dict)', '集合(Set)']
operations = [
    '查找元素',
    '插入元素',
    '删除元素',
    '修改元素',
    '遍历操作',
    '内存占用'
]

# 创建性能评分矩阵 (1-5分，5分表示最优)
performance_data = np.array([
    [3, 4, 5, 5],  # 查找元素
    [4, 1, 4, 4],  # 插入元素
    [3, 1, 4, 4],  # 删除元素
    [4, 1, 4, 1],  # 修改元素
    [4, 4, 3, 4],  # 遍历操作
    [3, 2, 4, 3],  # 内存占用
])

# 绘制热力图
ax = axes[0]
im = ax.imshow(performance_data, cmap='RdYlGn', aspect='auto', alpha=0.8)

# 设置刻度标签
ax.set_xticks(np.arange(len(data_structures)))
ax.set_yticks(np.arange(len(operations)))
ax.set_xticklabels(data_structures, fontsize=10)
ax.set_yticklabels(operations, fontsize=10)

# 设置标题
ax.set_title('Python主要数据结构性能对比', fontsize=16, fontweight='bold', pad=20)

# 添加数值标签
for i in range(len(operations)):
    for j in range(len(data_structures)):
        text = ax.text(j, i, f"{performance_data[i, j]}",
                      ha="center", va="center", color="black",
                      fontweight='bold')

# 添加颜色条
cbar = fig.colorbar(im, ax=ax, orientation='vertical', shrink=0.6)
cbar.set_ticks([0, 1, 2, 3, 4, 5])
cbar.set_ticklabels(['最差', '', '', '', '', '最优'])

# 添加代码示例表格
code_examples = [
    ['数据结构', '创建示例', '适用场景'],
    ['列表', 'fruits = ["苹果", "香蕉"]\nfruits.append("橙子")', '有序数据、频繁修改'],
    ['元组', 'coordinates = (10, 20)\nx, y = coordinates', '不可变数据、坐标点'],
    ['字典', 'student = {"name": "小明",\n"age": 15}', '键值对数据、配置信息'],
    ['集合', 'numbers = {1, 2, 3}\nnumbers.add(4)', '去重、集合运算']
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
         "说明：性能评分基于1-5分制，5分表示最优。\n"
         "结论：列表适合频繁修改的有序数据，字典适合键值对数据，集合适合去重和集合运算。",
         ha='center', fontsize=10, style='italic', 
         bbox=dict(boxstyle='round,pad=0.5', facecolor='#F2F2F2', alpha=0.5))

# 调整布局
plt.tight_layout(rect=[0, 0.05, 1, 0.95])
plt.subplots_adjust(hspace=0.4)

# 保存图片
output_file = images_dir / "python_data_structures_comparison.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"图表已保存到: {output_file}")

# 同时创建一个目录图片作为备份
alt_output_file = script_dir / "python_data_structures_comparison.png"
plt.savefig(alt_output_file, dpi=150, bbox_inches='tight')
print(f"备份图表已保存到: {alt_output_file}")

plt.close()

print("""
要在Markdown中显示此图表，请使用以下代码：

![Python主要数据结构性能对比](./images/python_data_structures_comparison.png)

如果您在将此图像添加到文档中遇到问题，可以尝试使用绝对路径。
""") 