# 实例1：打印爱心
def print_heart():
    """打印爱心图案"""
    print("\n".join([''.join([('Love'[(x-y) % 4] if ((x*0.05)**2+(y*0.1)**2-1)**3-(x*0.05)**2*(y*0.1)**3 <= 0 else ' ') for x in range(-30, 30)]) for y in range(15, -15, -1)]))

# 实例2：打印乘法表
def print_multiplication_table():
    """打印九九乘法表"""
    # 外层循环控制行
    for i in range(1, 10):
        # 内层循环控制列
        for j in range(1, i + 1):
            # 打印乘法表达式，使用格式化保持对齐
            # \t是制表符，保持输出整齐
            print(f"{j} × {i} = {i*j}", end="\t")
        # 每行结束后换行
        print()

# 打印更美观的乘法表
def print_pretty_multiplication_table():
    """打印格式更美观的九九乘法表"""
    print("九九乘法表：")
    print("-" * 60)
    # 外层循环控制行
    for i in range(1, 10):
        row = ""
        # 内层循环控制列
        for j in range(1, i + 1):
            # 使用固定宽度格式化输出
            row += f"{j}×{i}={i*j:<4}"
        print(row)
    print("-" * 60)

# 调用函数打印图案
print_heart()
print("\n\n")
print_multiplication_table()
print("\n\n")
print_pretty_multiplication_table()


def bubble_sort(arr):
    """
    冒泡排序函数
    参数:
        arr: 要排序的列表
    返回:
        排序后的列表
    """
    n = len(arr)
    # 外层循环控制排序轮数
    for i in range(n):
        # 内层循环控制每轮比较次数
        # 每轮排序后，最大的元素已经到位，因此比较次数减少
        for j in range(0, n-i-1):
            # 如果当前元素大于下一个元素，交换它们
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

# 测试冒泡排序
numbers = [64, 34, 25, 12, 22, 11, 90]
sorted_numbers = bubble_sort(numbers.copy())
print(f"原始数组: {numbers}")
print(f"排序后数组: {sorted_numbers}")