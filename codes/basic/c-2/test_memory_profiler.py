"""
内存分析工具示例

此脚本演示如何使用memory_profiler分析Python代码的内存使用情况。
要运行此脚本，需要先安装memory_profiler:
pip install memory_profiler

运行方式:
python -m memory_profiler test_memory_profiler.py
"""

from memory_profiler import profile
import numpy as np
import time
import gc

# 强制垃圾回收，确保测试前内存状态一致
gc.collect()


@profile
def create_list(n_elements):
    """创建一个包含n_elements个整数的列表"""
    result = []
    for i in range(n_elements):
        result.append(i)
    return result


@profile
def create_numpy_array(n_elements):
    """创建一个包含n_elements个整数的NumPy数组"""
    return np.arange(n_elements)


@profile
def process_with_intermediate_lists(data, iterations):
    """处理数据，每次迭代都创建新的中间列表"""
    for _ in range(iterations):
        # 创建中间列表
        temp = [x * 2 for x in data]
        # 再创建一个中间列表
        result = [x + 1 for x in temp]
    return result


@profile
def process_with_inplace_operation(data, iterations):
    """处理数据，避免创建中间列表"""
    result = list(data)  # 复制输入数据
    for _ in range(iterations):
        # 直接修改结果列表
        for i in range(len(result)):
            result[i] = result[i] * 2 + 1
    return result


@profile
def leak_simulation():
    """模拟一个内存泄漏场景"""
    # 这个对象在全局范围内持有引用，不会被垃圾回收
    global cache
    cache = {}
    
    for i in range(100):
        # 每次迭代都向缓存中添加一个大对象
        key = f"key_{i}"
        # 创建一个1MB的数组
        cache[key] = np.ones((256, 1024), dtype=np.float64)
        # 小延迟使内存增长在分析器中更明显
        time.sleep(0.01)
    
    return cache


@profile
def memory_efficient_processing(file_path, chunk_size=1000):
    """
    以内存高效的方式处理大文件
    模拟分块读取和处理一个大文件的场景
    """
    # 模拟大文件的总行数
    total_lines = 1_000_000
    processed_count = 0
    result_sum = 0
    
    # 模拟分块读取和处理文件
    for chunk_start in range(0, total_lines, chunk_size):
        # 模拟读取一个数据块
        chunk_end = min(chunk_start + chunk_size, total_lines)
        chunk = list(range(chunk_start, chunk_end))
        
        # 处理这个数据块
        for value in chunk:
            result_sum += value
            processed_count += 1
        
        # 模拟一些I/O延迟
        if chunk_start % 10000 == 0:
            time.sleep(0.01)
            print(f"已处理 {processed_count}/{total_lines} 行")
    
    return result_sum


@profile
def compare_string_methods(n_iterations=100000):
    """比较不同字符串操作方法的内存使用情况"""
    # 使用+连接字符串
    def concat_with_plus():
        result = ""
        for i in range(100):
            result = result + str(i) + "_"
        return result
    
    # 使用join连接字符串
    def concat_with_join():
        parts = []
        for i in range(100):
            parts.append(str(i))
            parts.append("_")
        return "".join(parts)
    
    # 使用列表推导式和join
    def concat_with_comprehension():
        return "".join(f"{i}_" for i in range(100))
    
    # 运行每个方法多次
    for _ in range(n_iterations // 1000):
        concat_with_plus()
        concat_with_join()
        concat_with_comprehension()
    
    return "完成字符串方法比较"


@profile
def main():
    """主函数运行所有测试"""
    print("\n1. 比较列表和NumPy数组")
    n_elements = 1_000_000
    
    print("创建Python列表...")
    python_list = create_list(n_elements)
    
    print("创建NumPy数组...")
    numpy_array = create_numpy_array(n_elements)
    
    print("\n2. 比较处理方式")
    small_data = list(range(10000))
    iterations = 100
    
    print("使用中间列表处理...")
    result1 = process_with_intermediate_lists(small_data, iterations)
    
    print("使用就地操作处理...")
    result2 = process_with_inplace_operation(small_data, iterations)
    
    print("\n3. 模拟内存泄漏")
    print("运行泄漏模拟...")
    leak_simulation()
    
    print("\n4. 使用内存高效的方式处理数据")
    memory_efficient_processing("模拟文件路径.txt", chunk_size=10000)
    
    print("\n5. 比较字符串方法")
    compare_string_methods(n_iterations=10000)
    
    print("\n分析完成!")
    
    # 清理全局缓存，释放内存
    global cache
    if 'cache' in globals():
        del cache
    
    # 执行垃圾回收
    gc.collect()


if __name__ == "__main__":
    main() 