import sys
import weakref
import gc

class RefTracker:
    """跟踪对象引用计数变化的工具类"""
    
    def __init__(self):
        self.tracked_objects = {}
        self.snapshots = []
    
    def track(self, obj, name):
        """开始跟踪一个对象"""
        try:
            # 使用弱引用避免影响被跟踪对象的引用计数
            self.tracked_objects[name] = weakref.ref(obj)
        except TypeError:
            print(f"警告: 无法创建对 {type(obj).__name__} 类型的弱引用，将使用强引用")
            self.tracked_objects[name] = lambda o=obj: o
        self.snapshot()
    
    def snapshot(self):
        """记录当前所有被跟踪对象的引用计数"""
        snap = {}
        for name, ref_func in self.tracked_objects.items():
            obj = ref_func()
            if obj is not None:
                # 减1是为了排除getrefcount函数本身创建的临时引用
                snap[name] = sys.getrefcount(obj) - 1
            else:
                snap[name] = 0
        self.snapshots.append(snap)
        return snap
    
    def compare(self, index1=0, index2=-1):
        """比较两个快照之间的引用计数变化"""
        if not 0 <= index1 < len(self.snapshots) or not -len(self.snapshots) <= index2 < len(self.snapshots):
            raise IndexError("快照索引超出范围")
        
        snap1 = self.snapshots[index1]
        snap2 = self.snapshots[index2]
        
        result = {}
        all_keys = set(snap1.keys()) | set(snap2.keys())
        
        for key in all_keys:
            count1 = snap1.get(key, 0)
            count2 = snap2.get(key, 0)
            result[key] = count2 - count1
        
        return result
    
    def report(self):
        """生成所有被跟踪对象的引用计数报告"""
        latest = self.snapshot()
        print("当前引用计数状态:")
        for name, count in latest.items():
            obj = self.tracked_objects[name]()
            if obj is not None:
                obj_type = type(obj).__name__
                print(f"{name} ({obj_type}): {count}")
            else:
                print(f"{name} (已回收): {count}")

# 自定义类用于测试
class TestObject:
    def __init__(self, name):
        self.name = name
        self.data = []
    
    def __repr__(self):
        return f"TestObject({self.name})"

# 测试代码
if __name__ == "__main__":
    # 创建追踪器
    tracker = RefTracker()

    # 跟踪自定义对象
    my_obj = TestObject("test1")
    tracker.track(my_obj, "my_obj")

    # 添加引用
    another_ref = my_obj
    tracker.snapshot()

    # 在函数中使用
    def use_object(obj):
        print(f"使用对象: {obj}")
        tracker.snapshot()

    use_object(my_obj)

    # 删除引用
    del another_ref
    tracker.snapshot()

    # 报告引用计数变化
    print("\n引用计数变化:")
    print(tracker.compare())
    tracker.report()
    
    # 清除最后一个引用
    print("\n清除最后一个引用后:")
    del my_obj
    tracker.report()
    
    # 测试内置类型
    print("\n测试内置类型(list):")
    my_list = [1, 2, 3]
    tracker.track(my_list, "my_list")
    print("\n引用计数状态:")
    tracker.report() 