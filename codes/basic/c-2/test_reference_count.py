import sys
import gc

# 关闭自动垃圾回收，以便仅观察引用计数机制
gc.disable()
print("自动垃圾回收已关闭")

# 定义一个测试类，用于观察引用计数
class ReferenceTest:
    def __init__(self, name):
        self.name = name
        print(f"创建对象: {self.name}")
    
    def __del__(self):
        print(f"销毁对象: {self.name}")


def show_ref_count(obj, name):
    """显示对象的引用计数"""
    # 减去1是因为将对象传递给getrefcount函数会临时增加一个引用
    count = sys.getrefcount(obj) - 1
    print(f"{name} 的引用计数: {count}")


print("\n=== 基本引用计数测试 ===")
# 创建对象
obj = ReferenceTest("测试对象")
show_ref_count(obj, "obj")

# 创建第二个引用
obj2 = obj
show_ref_count(obj, "obj (在创建obj2后)")

# 创建第三个引用
obj_list = [obj]
show_ref_count(obj, "obj (在添加到列表后)")

# 移除一个引用
del obj2
show_ref_count(obj, "obj (在删除obj2后)")

# 移除列表中的引用
obj_list.clear()
show_ref_count(obj, "obj (在清空列表后)")


print("\n=== 函数参数和临时引用 ===")
def test_function(param):
    print("函数内部:")
    show_ref_count(param, "参数")
    # 函数返回时，param引用计数减少

# 调用函数，传递对象
test_function(obj)
print("函数外部:")
show_ref_count(obj, "obj (函数调用后)")


print("\n=== 循环引用测试 ===")
class Node:
    def __init__(self, name):
        self.name = name
        self.next = None
        print(f"创建节点: {self.name}")
    
    def __del__(self):
        print(f"销毁节点: {self.name}")

# 创建循环引用的节点
node_a = Node("A")
node_b = Node("B")

# 显示初始引用计数
show_ref_count(node_a, "node_a (初始)")
show_ref_count(node_b, "node_b (初始)")

# 创建循环引用
node_a.next = node_b
node_b.next = node_a

# 显示循环引用后的引用计数
show_ref_count(node_a, "node_a (循环引用后)")
show_ref_count(node_b, "node_b (循环引用后)")

# 删除外部引用
print("\n删除外部引用:")
del node_a
del node_b

print("由于循环引用，节点A和B不会被销毁")

# 重新启用垃圾回收并收集循环引用
print("\n启用垃圾回收并手动触发:")
gc.enable()
collected = gc.collect()
print(f"垃圾回收器回收了 {collected} 个对象")


print("\n=== 容器类型的引用计数 ===")
# 创建不同类型的容器并测试引用计数
test_obj = ReferenceTest("容器测试对象")
show_ref_count(test_obj, "test_obj (初始)")

# 在字典中使用对象
dict_container = {"key": test_obj}
show_ref_count(test_obj, "test_obj (添加到字典后)")

# 在集合中使用对象
set_container = {test_obj}  # 需要对象是可哈希的
show_ref_count(test_obj, "test_obj (添加到集合后)")

# 在元组中使用对象
tuple_container = (test_obj,)
show_ref_count(test_obj, "test_obj (添加到元组后)")

# 清除容器
dict_container.clear()
set_container.clear()
tuple_container = ()

show_ref_count(test_obj, "test_obj (清除所有容器后)")

# 删除最后的引用
print("\n删除最后一个引用:")
del test_obj 