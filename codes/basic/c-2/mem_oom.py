def memory_leak_visualization_demo():
    """演示内存泄漏检测和可视化"""
    from memory_leak_detector import MemoryLeakDetector
    import gc
    
    # 初始化检测器
    detector = MemoryLeakDetector()
    
    # 记录初始状态
    detector.take_snapshot("开始")
    
    # 创建一些正常对象
    normal_objects = []
    for i in range(1000):
        obj = {"id": i, "data": list(range(10))}
        normal_objects.append(obj)
    
    detector.take_snapshot("创建正常对象后")
    
    # 创建一些循环引用
    leaky_objects = []
    for i in range(100):
        a = {"id": f"a{i}"}
        b = {"id": f"b{i}"}
        a["ref"] = b
        b["ref"] = a
        
        # 只保留对其中一个的引用
        leaky_objects.append(a)
    
    # 跟踪一个泄漏对象
    detector.track_object(leaky_objects[0], "leaky_object_0")
    
    detector.take_snapshot("创建循环引用后")
    
    # 保存一个全局引用，防止对象被回收
    global leak_keeper
    leak_keeper = leaky_objects[0]
    
    # 删除正常对象的引用
    del normal_objects
    # 删除局部变量中的泄漏对象引用，但保留全局引用
    del leaky_objects
    
    detector.take_snapshot("删除外部引用后")
    
    # 强制垃圾回收
    gc.collect()
    
    detector.take_snapshot("强制垃圾回收后")
    
    # 分析跟踪的对象
    detector.check_tracked_objects()
    
    # 生成报告
    detector.print_report()
    
    # 生成可视化图表
    detector.visualize_memory_usage()
    
    # 如果跟踪的对象还活着，生成它的引用图
    tracked = detector.check_tracked_objects()
    if "leaky_object_0" in tracked["alive"]:
        obj = tracked["alive"]["leaky_object_0"]["ref"]()
        if tracked["alive"]["leaky_object_0"]["is_wrapper"]:
            obj = obj.obj  # 获取原始对象
        detector.visualize_object_graph(obj)
    
    # 也可以手动生成引用图（无论对象是否被回收）
    if leak_keeper:
        detector.visualize_object_graph(leak_keeper, max_depth=3)
        # 清除全局引用
        leak_keeper = None

# 定义全局变量用于保存对象的引用
leak_keeper = None

# 运行演示
memory_leak_visualization_demo()