import weakref
import gc

# 测试弱引用字典(WeakValueDictionary)
print("=== 测试 WeakValueDictionary ===")

class ExpensiveObject:
    def __init__(self, value):
        self.value = value
        print(f"创建 ExpensiveObject({value})")
    
    def __del__(self):
        print(f"销毁 ExpensiveObject({self.value})")

# 创建一个缓存类
class Cache:
    def __init__(self):
        # 使用弱引用字典，当对象不再被使用时自动从缓存中移除
        self.cache = weakref.WeakValueDictionary()
    
    def get(self, key):
        return self.cache.get(key)
    
    def set(self, key, value):
        self.cache[key] = value
    
    def size(self):
        return len(self.cache)

# 使用缓存
cache = Cache()

# 创建并缓存对象
obj1 = ExpensiveObject(42)
cache.set("obj1", obj1)

obj2 = ExpensiveObject(100)
cache.set("obj2", obj2)

# 获取缓存对象
cached_obj = cache.get("obj1")
print(f"获取缓存对象: {cached_obj.value}")

print(f"当前缓存大小: {cache.size()}")

# 删除一个原始对象的引用
print("\n删除obj1的引用:")
del obj1

# 强制垃圾回收
gc.collect()

print(f"删除obj1后缓存大小: {cache.size()}")
print(f"尝试获取obj1: {cache.get('obj1')}")
print(f"尝试获取obj2: {cache.get('obj2').value}")

# 删除所有原始对象引用
print("\n删除obj2的引用:")
del obj2
gc.collect()

print(f"删除所有对象后缓存大小: {cache.size()}")

# 测试弱引用集合(WeakSet)
print("\n=== 测试 WeakSet ===")

class Listener:
    def __init__(self, name):
        self.name = name
        print(f"创建监听器 {name}")
    
    def __del__(self):
        print(f"销毁监听器 {self.name}")
    
    def on_event(self, event):
        print(f"{self.name} 收到事件: {event}")

class EventDispatcher:
    def __init__(self):
        # 使用弱引用集合存储监听器
        self.listeners = weakref.WeakSet()
    
    def add_listener(self, listener):
        self.listeners.add(listener)
    
    def dispatch_event(self, event):
        if not self.listeners:
            print("没有监听器")
            return
        
        print(f"向 {len(self.listeners)} 个监听器发送事件")
        # 向所有监听器发送事件
        for listener in self.listeners:
            listener.on_event(event)

# 创建调度器和监听器
dispatcher = EventDispatcher()

# 创建监听器
listener1 = Listener("监听器1")
listener2 = Listener("监听器2")

# 注册监听器
dispatcher.add_listener(listener1)
dispatcher.add_listener(listener2)

# 发送事件
print("\n发送第一个事件:")
dispatcher.dispatch_event("Hello")

# 删除一个监听器
print("\n删除监听器1:")
del listener1
gc.collect()

# 再次发送事件
print("\n发送第二个事件:")
dispatcher.dispatch_event("World")

# 删除最后一个监听器
print("\n删除所有监听器:")
del listener2
gc.collect()

# 发送最后一个事件
print("\n发送最后一个事件:")
dispatcher.dispatch_event("No one will receive this") 