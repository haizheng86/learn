import weakref
import sys

class Example:
    pass

# 创建对象
obj = Example()
print(f"初始引用计数: {sys.getrefcount(obj)}")

# 创建强引用
strong_ref = obj
print(f"强引用后引用计数: {sys.getrefcount(obj)}")

# 创建弱引用
weak_ref = weakref.ref(obj)
print(f"弱引用后引用计数: {sys.getrefcount(obj)}")

# 访问弱引用指向的对象
print(f"通过弱引用访问对象: {weak_ref()}")

# 删除原始对象
del obj
del strong_ref
print(f"删除对象后通过弱引用访问: {weak_ref()}")
