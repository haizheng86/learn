#!/usr/bin/env python3
# itertools_demo.py - itertools模块功能演示

import itertools
import operator
import time
import random
import sys

def infinite_iterators_demo():
    """演示无限迭代器"""
    print("\n==== 无限迭代器 ====")
    
    # count - 从n开始计数
    print("itertools.count():")
    for i in itertools.islice(itertools.count(10, 2), 5):
        print(i, end=' ')
    print()
    
    # cycle - 循环迭代元素
    print("\nitertools.cycle():")
    colors = ['红', '黄', '蓝']
    for color in itertools.islice(itertools.cycle(colors), 7):
        print(color, end=' ')
    print()
    
    # repeat - 重复元素
    print("\nitertools.repeat():")
    for x in itertools.repeat("Python", 5):
        print(x, end=' ')
    print()
    
    # 实际应用 - 创建序列号
    print("\n生成带前缀的序列号:")
    product_codes = map(lambda x: f"PROD-{x:04d}", itertools.count(1))
    for code in itertools.islice(product_codes, 5):
        print(code)

def terminating_iterators_demo():
    """演示终止迭代器"""
    print("\n==== 终止迭代器 ====")
    
    # accumulate - 累积计算
    print("itertools.accumulate():")
    data = [1, 2, 3, 4, 5]
    print(f"原始数据: {data}")
    print(f"累加: {list(itertools.accumulate(data))}")
    print(f"累乘: {list(itertools.accumulate(data, operator.mul))}")
    
    # 自定义累积函数 - 找最大值
    print(f"累积最大值: {list(itertools.accumulate(data, max))}")
    
    # chain - 连接多个迭代器
    print("\nitertools.chain():")
    list1 = ['a', 'b', 'c']
    list2 = [1, 2, 3]
    list3 = [True, False]
    print(f"链接列表: {list(itertools.chain(list1, list2, list3))}")
    
    # compress - 选择性过滤
    print("\nitertools.compress():")
    data = ['A', 'B', 'C', 'D', 'E']
    selectors = [1, 0, 1, 0, 1]
    print(f"数据: {data}")
    print(f"选择器: {selectors}")
    print(f"结果: {list(itertools.compress(data, selectors))}")
    
    # dropwhile & takewhile - 条件过滤
    print("\nitertools.dropwhile() & takewhile():")
    data = [1, 3, 5, 20, 2, 4, 6, 8]
    print(f"原始数据: {data}")
    print(f"丢弃小于10的元素直到条件失败: {list(itertools.dropwhile(lambda x: x < 10, data))}")
    print(f"获取小于10的元素直到条件失败: {list(itertools.takewhile(lambda x: x < 10, data))}")
    
    # 实际应用 - 解析日志文件中的错误记录
    print("\n解析日志文件:")
    log_lines = [
        "INFO: 程序启动",
        "DEBUG: 加载配置",
        "INFO: 用户登录",
        "ERROR: 数据库连接失败",
        "ERROR: 查询执行失败",
        "INFO: 重试连接",
        "INFO: 连接成功"
    ]
    
    # 找出所有ERROR日志
    error_logs = list(itertools.compress(
        log_lines,
        map(lambda x: x.startswith("ERROR:"), log_lines)
    ))
    
    print("错误日志:")
    for err in error_logs:
        print(f"  {err}")

def combinatoric_iterators_demo():
    """演示组合生成器"""
    print("\n==== 组合生成器 ====")
    
    # product - 笛卡尔积
    print("itertools.product():")
    print(f"两组元素的笛卡尔积: {list(itertools.product('AB', '12'))}")
    print(f"单组元素的重复笛卡尔积: {list(itertools.product('AB', repeat=2))}")
    
    # permutations - 排列
    print("\nitertools.permutations():")
    print(f"'ABC'的全排列: {list(itertools.permutations('ABC'))}")
    print(f"'ABC'中取2个元素的排列: {list(itertools.permutations('ABC', 2))}")
    
    # combinations - 组合
    print("\nitertools.combinations():")
    print(f"'ABC'中取2个元素的组合: {list(itertools.combinations('ABC', 2))}")
    
    # combinations_with_replacement - 带重复的组合
    print("\nitertools.combinations_with_replacement():")
    print(f"'ABC'中取2个元素的组合(可重复): {list(itertools.combinations_with_replacement('ABC', 2))}")
    
    # 实际应用 - 生成测试方案
    print("\n生成测试方案:")
    
    platforms = ['Windows', 'Linux', 'macOS']
    browsers = ['Chrome', 'Firefox', 'Safari']
    resolutions = ['1080p', '4K']
    
    # 生成测试组合
    test_scenarios = list(itertools.product(platforms, browsers, resolutions))
    
    print(f"总测试场景数: {len(test_scenarios)}")
    print("部分测试场景:")
    for i, scenario in enumerate(test_scenarios[:5], 1):
        platform, browser, resolution = scenario
        print(f"  场景{i}: {platform} + {browser} + {resolution}")
    
    # 另一个应用 - 密码生成
    print("\n生成所有可能的4位PIN码:")
    digits = '0123456789'
    count = 0
    # 只显示前5个，实际会有10000个
    for pin in itertools.islice(itertools.product(digits, repeat=4), 5):
        print(f"  {''.join(pin)}")
    print("  ... (共10000种可能)")

def memory_efficiency_demo():
    """演示迭代器的内存效率"""
    print("\n==== 内存效率对比 ====")
    
    try:
        from memory_profiler import memory_usage
        
        # 创建1到100万的序列
        range_size = 1000000
        
        # 普通列表
        def create_list():
            return list(range(range_size))
        
        # 迭代器
        def create_iterator():
            return range(range_size)  # range是迭代器
        
        # 使用itertools的方式
        def use_itertools():
            return itertools.islice(itertools.count(), range_size)
        
        # 列表推导和生成器表达式
        def list_comp():
            return [x for x in range(range_size)]
        
        def gen_expr():
            return (x for x in range(range_size))
        
        # 内存使用测试
        print("创建100万个整数序列的内存使用:")
        
        list_mem = max(memory_usage((create_list, tuple()), max_iterations=1))
        iterator_mem = max(memory_usage((create_iterator, tuple()), max_iterations=1))
        itertools_mem = max(memory_usage((use_itertools, tuple()), max_iterations=1))
        list_comp_mem = max(memory_usage((list_comp, tuple()), max_iterations=1))
        gen_expr_mem = max(memory_usage((gen_expr, tuple()), max_iterations=1))
        
        print(f"列表方式   : {list_mem:.2f} MB")
        print(f"迭代器方式 : {iterator_mem:.2f} MB")
        print(f"itertools : {itertools_mem:.2f} MB")
        print(f"列表推导式 : {list_comp_mem:.2f} MB")
        print(f"生成器表达式: {gen_expr_mem:.2f} MB")
        
        # 对比
        print(f"\n列表比迭代器多用 {list_mem/iterator_mem:.1f} 倍内存")
        print(f"列表比生成器表达式多用 {list_mem/gen_expr_mem:.1f} 倍内存")
    
    except ImportError:
        print("提示: 要查看详细内存使用分析，请安装memory_profiler模块:")
        print("pip install memory-profiler")
        
        print("\n备选方案：简单内存对比演示:")
        # 不使用memory_profiler的简化版演示
        import sys
        
        # 检测对象大小
        list_size = sys.getsizeof(list(range(1000)))
        range_size = sys.getsizeof(range(1000))
        gen_size = sys.getsizeof((x for x in range(1000)))
        
        print(f"1000个元素的列表大小: {list_size} 字节")
        print(f"range(1000)对象大小: {range_size} 字节")
        print(f"1000个元素的生成器表达式大小: {gen_size} 字节")
        print(f"\n列表比range对象大约大 {list_size/range_size:.1f} 倍")
        print(f"列表比生成器表达式大约大 {list_size/gen_size:.1f} 倍")
        print("注意: 这只是对象本身的大小，不包括引用的元素")

def processing_large_data_demo():
    """演示处理大数据集的效率"""
    print("\n==== 处理大数据集的效率 ====")
    
    # 创建一个大数据集
    data_size = 10000000  # 一千万个元素
    
    print(f"处理{data_size}个元素:")
    
    # 使用普通循环
    def process_with_loop():
        result = 0
        for i in range(data_size):
            result += i
        return result
    
    # 使用itertools
    def process_with_itertools():
        return sum(itertools.islice(itertools.count(), data_size))
    
    # 时间对比
    start_time = time.time()
    loop_result = process_with_loop()
    loop_time = time.time() - start_time
    
    start_time = time.time()
    itertools_result = process_with_itertools()
    itertools_time = time.time() - start_time
    
    print(f"普通循环耗时   : {loop_time:.4f} 秒")
    print(f"itertools耗时 : {itertools_time:.4f} 秒")
    print(f"速度比         : {loop_time/itertools_time:.2f}x")
    
    # 验证结果一致性
    print(f"结果一致: {loop_result == itertools_result}")

def practical_applications():
    """实际应用示例"""
    print("\n==== 实际应用示例 ====")
    
    # 1. 数据分块处理
    print("1. 将数据分块处理:")
    data = list(range(10))
    chunk_size = 3
    
    # 使用itertools分组
    chunks = list(itertools.zip_longest(*[iter(data)] * chunk_size, fillvalue=None))
    
    print(f"原始数据: {data}")
    print(f"分块后  : {chunks}")
    
    # 2. 窗口滑动
    print("\n2. 滑动窗口处理:")
    
    def sliding_window(iterable, n):
        # 创建多个迭代器
        iterables = itertools.tee(iterable, n)
        
        # 将每个迭代器错开不同的偏移量
        for i, it in enumerate(iterables):
            for _ in range(i):
                next(it, None)
                
        # 将错开的迭代器"压缩"在一起
        return zip(*iterables)
    
    data = list(range(10))
    window_size = 3
    
    windows = list(sliding_window(data, window_size))
    
    print(f"原始数据: {data}")
    print(f"滑动窗口(大小={window_size}):")
    for w in windows:
        print(f"  {w}")
    
    # 3. 查找最长连续序列
    print("\n3. 查找最长连续序列:")
    
    def find_longest_streak(data, target):
        # 将数据转换为0/1序列
        binary = [1 if x == target else 0 for x in data]
        
        # 按照0分组
        groups = [(k, len(list(g))) for k, g in itertools.groupby(binary)]
        
        # 找出最长的1序列
        max_streak = max([length for key, length in groups if key == 1], default=0)
        return max_streak
    
    data = [1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1]
    target = 1
    
    streak = find_longest_streak(data, target)
    
    print(f"数据序列: {data}")
    print(f"最长连续{target}的长度: {streak}")
    
    # 4. 复杂条件过滤
    print("\n4. 复杂条件过滤:")
    
    people = [
        {'name': '张三', 'age': 25, 'city': '北京'},
        {'name': '李四', 'age': 30, 'city': '上海'},
        {'name': '王五', 'age': 22, 'city': '北京'},
        {'name': '赵六', 'age': 35, 'city': '广州'},
        {'name': '钱七', 'age': 28, 'city': '上海'},
    ]
    
    # 找出所有上海和北京的人
    target_cities = {'北京', '上海'}
    filtered = itertools.compress(
        people,
        map(lambda p: p['city'] in target_cities, people)
    )
    
    print("上海和北京的人:")
    for person in filtered:
        print(f"  {person['name']}, {person['age']}岁, {person['city']}")

def main():
    """主函数"""
    print("===== itertools模块演示 =====")
    print("Python版本:", sys.version)
    
    infinite_iterators_demo()
    terminating_iterators_demo()
    combinatoric_iterators_demo()
    
    try:
        # memory_profiler模块可能未安装
        memory_efficiency_demo()
    except ImportError:
        print("\n==== 内存效率对比 ====")
        print("需要安装memory_profiler模块: pip install memory_profiler")
    
    processing_large_data_demo()
    practical_applications()
    
    print("\n演示完成!")

if __name__ == "__main__":
    main() 