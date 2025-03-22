import gc
import time
import sys

# 开始时先禁用自动垃圾回收
gc.disable()

# 打印当前的垃圾回收阈值
print(f"垃圾回收阈值: {gc.get_threshold()}")  # 通常为(700, 10, 10)

# 查看各代对象数量
print(f"收集前各代对象数量: {gc.get_count()}")

# 创建一个能被跟踪的类（包含__del__方法便于观察回收）
class Node:
    def __init__(self, name):
        self.name = name
        self.ref = None
        print(f"创建 {self.name}")
    
    def __del__(self):
        print(f"销毁 {self.name}")

print("\n测试 1: 无循环引用")
# 创建不包含循环引用的对象
x = Node("X")
y = Node("Y")

# 删除引用
print("\n删除引用:")
del x
del y
print("引用删除完毕")

# 查看对象数量
print(f"删除引用后各代对象数量: {gc.get_count()}")

print("\n测试 2: 循环引用")
# 创建循环引用
a = Node("A")
b = Node("B")
a.ref = b
b.ref = a
print(f"创建了循环引用: A.ref -> B, B.ref -> A")

# 移除外部引用
print("\n删除外部引用:")
del a
del b
print("外部引用删除完毕")

# 查看未收集的对象
print(f"创建循环引用后各代对象数量: {gc.get_count()}")

# 检查未回收对象
unreachable = gc.get_objects()
print(f"跟踪的对象数量: {len(unreachable)}")

# 手动触发垃圾收集
print("\n执行垃圾回收:")
collected = gc.collect()
print(f"收集的对象数量: {collected}")
print(f"收集后各代对象数量: {gc.get_count()}")

print("\n测试 3: 性能测试")
# 创建大量对象并测试性能
def create_cycles(count):
    nodes = []
    for i in range(count):
        nodes.append((Node(f"Node-{i}a"), Node(f"Node-{i}b")))
    
    # 创建循环引用
    for a, b in nodes:
        a.ref = b
        b.ref = a
    
    return nodes

# 测试不同数量对象的垃圾回收性能
for count in [10, 100, 1000]:
    print(f"\n创建 {count} 个循环引用对:")
    nodes = create_cycles(count)
    
    # 删除引用
    del nodes
    
    # 计时回收
    start_time = time.time()
    collected = gc.collect()
    elapsed = time.time() - start_time
    
    print(f"回收 {collected} 个对象耗时: {elapsed:.6f} 秒")

# 重新启用自动垃圾回收
gc.enable()
print("\n垃圾回收测试完成，已重新启用自动回收") 