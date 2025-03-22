class Node:
    def __init__(self, name):
        self.name = name
        self.neighbor = None
    def __del__(self):
        print(f"Node {self.name} 被销毁")
node1 = Node("A")
node2 = Node("B")
node1.neighbor = node2
node2.neighbor = node1
import sys
print(f"node1引用计数: {sys.getrefcount(node1) - 1}")
print(f"node2引用计数: {sys.getrefcount(node2) - 1}")
del node1
del node2
print("外部引用已删除，但对象未被回收（无__del__调用）")
import gc
gc.collect()
print("垃圾回收后")
