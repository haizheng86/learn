#!/usr/bin/env python3
# collections_demo.py - collections模块功能演示

from collections import Counter, defaultdict, namedtuple, deque, OrderedDict
import time
import random

def counter_demo():
    """演示Counter类的功能和效率"""
    print("\n==== Counter类演示 ====")
    
    # 创建一个大型文本样例
    sample_text = """
    Python标准库是Python编程语言的核心组件，提供了丰富的功能模块。
    使用这些模块可以大大提高开发效率，避免重复造轮子。
    collections模块提供了多种专用容器数据类型，是对内置类型dict、list、set和tuple的补充。
    Counter类是一个计数器工具，可用于统计可哈希对象的出现次数。
    """
    
    words = sample_text.lower().split()
    
    print("样例文本词频统计:")
    
    # 使用Counter
    start_time = time.time()
    counter = Counter(words)
    counter_time = time.time() - start_time
    print(f"使用Counter耗时: {counter_time:.6f}秒")
    print("词频前5:")
    for word, count in counter.most_common(5):
        print(f"  {word}: {count}")
    
    # 使用普通字典实现
    start_time = time.time()
    word_dict = {}
    for word in words:
        if word in word_dict:
            word_dict[word] += 1
        else:
            word_dict[word] = 1
    dict_time = time.time() - start_time
    print(f"使用普通字典耗时: {dict_time:.6f}秒")
    
    # 效率对比
    print(f"Counter比普通字典快 {dict_time/counter_time:.2f} 倍")
    
    # Counter其他操作
    print("\nCounter其他操作:")
    c1 = Counter(a=3, b=1)
    c2 = Counter(a=1, b=2)
    print(f"c1: {c1}")
    print(f"c2: {c2}")
    print(f"c1 + c2: {c1 + c2}")  # 相加
    print(f"c1 - c2: {c1 - c2}")  # 相减，负数被移除

def defaultdict_demo():
    """演示defaultdict的功能和应用场景"""
    print("\n==== defaultdict类演示 ====")
    
    # 普通字典处理多值映射
    print("普通字典处理多值映射:")
    normal_dict = {}
    data = [("A", 1), ("B", 2), ("A", 3), ("C", 4), ("B", 5)]
    
    # 常规写法
    for k, v in data:
        if k in normal_dict:
            normal_dict[k].append(v)
        else:
            normal_dict[k] = [v]
    print(normal_dict)
    
    # 使用defaultdict
    print("\ndefaultdict处理多值映射:")
    dd = defaultdict(list)
    for k, v in data:
        dd[k].append(v)
    print(dict(dd))  # 转为普通字典显示
    
    # 字符串分组示例
    words = ["apple", "bat", "car", "door", "apple", "cat", "dog", "atom", "book"]
    by_letter = defaultdict(list)
    for word in words:
        by_letter[word[0]].append(word)
    
    print("\n按首字母分组:")
    for letter, words in sorted(by_letter.items()):
        print(f"  {letter}: {words}")
    
    # 统计频率示例
    print("\n自动计数:")
    s = "mississippi"
    d = defaultdict(int)
    for k in s:
        d[k] += 1
    print(d)

def namedtuple_demo():
    """演示namedtuple的功能和用法"""
    print("\n==== namedtuple类演示 ====")
    
    # 定义一个点类
    Point = namedtuple('Point', ['x', 'y'])
    
    p = Point(1, 2)
    print(f"点坐标: {p}")
    print(f"x坐标: {p.x}")
    print(f"y坐标: {p.y}")
    print(f"索引访问: {p[0]}, {p[1]}")
    
    # 转换为字典
    print(f"转换为字典: {p._asdict()}")
    
    # 创建新实例
    p2 = p._replace(x=3)
    print(f"创建新实例: {p2}")
    
    # 实际应用 - 处理CSV数据
    print("\n使用namedtuple处理结构化数据:")
    
    # 模拟CSV数据
    csv_data = [
        "2023-01-01,100,Success",
        "2023-01-02,200,Error",
        "2023-01-03,150,Success"
    ]
    
    # 定义记录类型
    Record = namedtuple('Record', ['date', 'value', 'status'])
    
    # 解析数据
    records = []
    for line in csv_data:
        date, value, status = line.split(',')
        records.append(Record(date, int(value), status))
    
    # 处理数据
    for record in records:
        print(f"  {record.date}: {record.value} ({record.status})")
    
    # 计算成功记录的平均值
    success_avg = sum(r.value for r in records if r.status == 'Success') / sum(1 for r in records if r.status == 'Success')
    print(f"成功记录的平均值: {success_avg}")

def deque_demo():
    """演示deque类的功能和性能优势"""
    print("\n==== deque类演示 ====")
    
    # 创建deque
    d = deque("abcdef")
    print(f"初始deque: {d}")
    
    # 添加元素
    d.append("g")
    print(f"右侧添加: {d}")
    
    d.appendleft("0")
    print(f"左侧添加: {d}")
    
    # 移除元素
    print(f"右侧移除: {d.pop()} -> {d}")
    print(f"左侧移除: {d.popleft()} -> {d}")
    
    # 旋转操作
    d.rotate(2)  # 向右旋转2步
    print(f"向右旋转2步: {d}")
    
    d.rotate(-2)  # 向左旋转2步，恢复原状
    print(f"向左旋转2步: {d}")
    
    # 性能对比：列表vs deque
    print("\n性能对比: 列表vs deque")
    
    # 列表左侧插入
    lst = list(range(10000))
    start_time = time.time()
    for i in range(100):
        lst.insert(0, i)
    list_time = time.time() - start_time
    print(f"列表左侧插入耗时: {list_time:.6f}秒")
    
    # deque左侧插入
    dq = deque(range(10000))
    start_time = time.time()
    for i in range(100):
        dq.appendleft(i)
    deque_time = time.time() - start_time
    print(f"deque左侧插入耗时: {deque_time:.6f}秒")
    
    print(f"deque比列表快 {list_time/deque_time:.2f} 倍")
    
    # 实际应用 - 最近N条历史记录
    print("\n保存最近N条历史记录:")
    
    history = deque(maxlen=3)  # 只保留最近3条
    actions = ["打开文件", "编辑内容", "保存文件", "关闭文件", "退出程序"]
    
    for action in actions:
        history.append(action)
        print(f"执行: {action} -> 历史记录: {list(history)}")

def orderdict_demo():
    """演示OrderedDict的功能"""
    print("\n==== OrderedDict类演示 ====")
    
    # 普通字典
    d = {}
    d['apple'] = 1
    d['banana'] = 2
    d['cherry'] = 3
    print("普通字典(Python 3.7+会保持顺序，但不是设计保证):")
    print(d)
    
    # OrderedDict
    od = OrderedDict()
    od['apple'] = 1
    od['banana'] = 2
    od['cherry'] = 3
    print("\nOrderedDict:")
    print(od)
    
    # 移动到末尾
    od.move_to_end('apple')
    print("\n将'apple'移到末尾:")
    print(od)
    
    # 删除第一个元素
    od.popitem(last=False)
    print("\n删除第一个元素:")
    print(od)
    
    # 实际应用 - LRU缓存
    print("\n使用OrderedDict实现简单的LRU缓存:")
    
    class LRUCache:
        def __init__(self, capacity):
            self.cache = OrderedDict()
            self.capacity = capacity
            
        def get(self, key):
            if key not in self.cache:
                return -1
            # 访问后移到末尾（最近使用）
            self.cache.move_to_end(key)
            return self.cache[key]
            
        def put(self, key, value):
            # 已存在则更新并移到末尾
            if key in self.cache:
                self.cache.move_to_end(key)
            # 缓存满则删除最久未使用项（队首）
            elif len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
            # 插入新项
            self.cache[key] = value
            
        def __str__(self):
            return str(self.cache)
    
    # LRU缓存测试
    lru = LRUCache(3)
    lru.put("A", 1)
    lru.put("B", 2)
    lru.put("C", 3)
    print(f"初始缓存: {lru}")
    
    lru.get("A")  # 访问A
    print(f"访问A后缓存: {lru}")
    
    lru.put("D", 4)  # 超过容量，最久未使用的(B)被删除
    print(f"添加D后缓存: {lru}")

def main():
    """主函数"""
    counter_demo()
    defaultdict_demo()
    namedtuple_demo()
    deque_demo()
    orderdict_demo()

if __name__ == "__main__":
    main() 