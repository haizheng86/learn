import matplotlib.pyplot as plt
import numpy as np
import os
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
fig, ax = plt.subplots(figsize=(12, 7))
fig.patch.set_facecolor('#f5f5f5')  # 设置背景颜色

# 定义数据
languages = ['Python', 'Java', 'C++', 'JavaScript']
features = [
    '动态类型',
    '类型声明',
    '自动内存管理',
    '变量可重新赋值不同类型',
    '大小写敏感'
]

# 创建特性矩阵 (1表示支持，0表示不支持或复杂)
data = np.array([
    [1, 0, 0, 1],  # 动态类型
    [0, 1, 1, 0],  # 类型声明
    [1, 1, 0, 1],  # 自动内存管理
    [1, 0, 0, 1],  # 变量可重新赋值不同类型
    [1, 1, 1, 1],  # 大小写敏感
])

# 定义颜色映射
cmap = plt.cm.RdYlGn
norm = plt.Normalize(0, 1)

# 创建热力图
im = ax.imshow(data, cmap=cmap, aspect='auto', alpha=0.8)

# 设置刻度标签
ax.set_xticks(np.arange(len(languages)))
ax.set_yticks(np.arange(len(features)))
ax.set_xticklabels(languages, fontsize=12, fontweight='bold')
ax.set_yticklabels(features, fontsize=12)

# 设置标题和标签
ax.set_title('Python变量与其他编程语言对比', fontsize=16, fontweight='bold', pad=20)

# 添加注释
for i in range(len(features)):
    for j in range(len(languages)):
        text = "✓" if data[i, j] else "✗"
        color = "black"
        ax.text(j, i, text, ha="center", va="center", color=color, fontsize=14, fontweight='bold')

# 添加代码示例
code_examples = [
    "# Python\nx = 42\nx = 'hello'  # 可以改变类型",
    "// Java\nint x = 42;\nString y = \"hello\";",
    "// C++\nint x = 42;\nstd::string y = \"hello\";",
    "// JavaScript\nlet x = 42;\nx = 'hello';  // 可以改变类型"
]

ax_height = 0.2
for i, code in enumerate(code_examples):
    ax_code = fig.add_axes([0.1 + i*0.22, 0.02, 0.2, ax_height])
    ax_code.text(0.5, 0.5, code, ha='center', va='center', fontsize=10, 
                 bbox=dict(boxstyle="round,pad=0.5", facecolor='white', alpha=0.8))
    ax_code.axis('off')

# 添加边框和网格
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['bottom'].set_linewidth(0.5)
ax.spines['left'].set_linewidth(0.5)

# 添加颜色条说明
cbar = fig.colorbar(im, ax=ax, orientation='vertical', shrink=0.6)
cbar.set_ticks([0, 1])
cbar.set_ticklabels(['不支持', '支持'])

# 优化布局
plt.tight_layout(rect=[0, 0.25, 1, 0.95])

# 保存图片
output_file = images_dir / "python_variables_comparison.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"图表已保存到: {output_file}")

# 同时创建一个目录图片作为备份
alt_output_file = script_dir / "python_variables_comparison.png"
plt.savefig(alt_output_file, dpi=150, bbox_inches='tight')
print(f"备份图表已保存到: {alt_output_file}")

plt.close()

print("""
要在Markdown中显示此图表，请使用以下代码：

![Python变量与其他语言对比图](./images/python_variables_comparison.png)

如果您在将此图像添加到文档中遇到问题，可以尝试使用绝对路径。
""") 