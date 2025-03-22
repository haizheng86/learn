import gc
import weakref
import time
import os
import psutil
import matplotlib.pyplot as plt
import networkx as nx
from collections import defaultdict
import matplotlib

# 设置matplotlib支持中文显示
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Microsoft YaHei', 'PingFang SC', 'Heiti SC']
matplotlib.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class ObjectWrapper:
    """用于包装不支持弱引用的对象（如dict、list等）"""
    def __init__(self, obj):
        self.obj = obj

class MemoryLeakDetector:
    """Python内存泄漏检测器"""
    
    def __init__(self):
        """初始化内存泄漏检测器"""
        self.snapshots = []
        self.tracked_objects = {}
        self.process = psutil.Process(os.getpid())
        
        # 确保启用了垃圾回收器
        gc.enable()
    
    def take_snapshot(self, label):
        """记录当前内存使用情况"""
        # 获取当前内存使用
        memory_usage = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # 获取对象计数
        counts = defaultdict(int)
        for obj in gc.get_objects():
            counts[type(obj).__name__] += 1
        
        # 获取垃圾回收器统计信息
        gc_stats = {
            "gc_objects": len(gc.get_objects()),
            "gc_stats": gc.get_stats(),
            "gc_threshold": gc.get_threshold()
        }
        
        # 记录时间
        timestamp = time.time()
        
        self.snapshots.append({
            "label": label,
            "timestamp": timestamp,
            "memory_usage": memory_usage,
            "object_counts": dict(counts),
            "gc_stats": gc_stats
        })
        
        print(f"快照 [{label}]: {memory_usage:.2f} MB")
    
    def track_object(self, obj, label):
        """跟踪特定对象"""
        if label in self.tracked_objects:
            print(f"警告: 标签 '{label}' 已经在使用中")
        
        # 检查对象是否可以被弱引用
        try:
            ref = weakref.ref(obj)
            is_wrapper = False
        except TypeError:
            # 为不支持弱引用的对象创建一个包装器
            wrapper = ObjectWrapper(obj)
            ref = weakref.ref(wrapper)
            is_wrapper = True
            print(f"对象类型 {type(obj).__name__} 不支持弱引用，已使用包装器")
        
        # 使用弱引用来跟踪对象，不增加引用计数
        self.tracked_objects[label] = {
            "ref": ref,
            "added_time": time.time(),
            "type": type(obj).__name__,
            "is_wrapper": is_wrapper
        }
        
        print(f"开始跟踪对象 '{label}' (类型: {type(obj).__name__})")
    
    def check_tracked_objects(self):
        """检查被跟踪对象的状态"""
        alive = {}
        dead = {}
        
        for label, data in self.tracked_objects.items():
            ref_obj = data["ref"]()
            
            # 检查是否是包装器
            if data.get("is_wrapper", False) and ref_obj is not None:
                obj = ref_obj.obj  # 获取包装的原始对象
            else:
                obj = ref_obj
            
            if obj is not None:
                alive[label] = data
                print(f"对象 '{label}' 仍然存活 (类型: {data['type']})")
            else:
                dead[label] = data
                print(f"对象 '{label}' 已被回收")
        
        result = {"alive": alive, "dead": dead}
        return result
    
    def print_report(self):
        """打印内存使用报告"""
        if not self.snapshots:
            print("没有可用快照")
            return
        
        print("\n===== 内存泄漏检测报告 =====")
        print(f"记录了 {len(self.snapshots)} 个快照:")
        
        for i, snapshot in enumerate(self.snapshots):
            print(f"\n快照 {i+1}: [{snapshot['label']}]")
            print(f"  内存使用: {snapshot['memory_usage']:.2f} MB")
            
            # 显示对象数量前10名
            sorted_counts = sorted(
                snapshot['object_counts'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            print("  前10种对象类型:")
            for obj_type, count in sorted_counts:
                print(f"    {obj_type}: {count}")
        
        # 计算内存变化
        if len(self.snapshots) > 1:
            first = self.snapshots[0]
            last = self.snapshots[-1]
            memory_change = last['memory_usage'] - first['memory_usage']
            
            print(f"\n内存变化: {memory_change:.2f} MB ", end="")
            if memory_change > 0:
                print("(增加 ⚠️)")
            elif memory_change < 0:
                print("(减少 ✓)")
            else:
                print("(无变化 ✓)")
    
    def visualize_memory_usage(self):
        """可视化内存使用情况"""
        if len(self.snapshots) < 2:
            print("需要至少两个快照来生成图表")
            return
        
        # 准备数据
        labels = [s['label'] for s in self.snapshots]
        memory_usage = [s['memory_usage'] for s in self.snapshots]
        timestamps = [s['timestamp'] - self.snapshots[0]['timestamp'] for s in self.snapshots]
        
        # 创建图表
        plt.figure(figsize=(12, 6))
        
        # 内存使用曲线
        plt.subplot(1, 2, 1)
        plt.plot(labels, memory_usage, 'o-', linewidth=2)
        plt.xlabel('快照')
        plt.ylabel('内存使用 (MB)')
        plt.title('内存使用变化')
        plt.grid(True)
        plt.xticks(rotation=45)
        
        # 对象数量变化 (选择前5种最常见类型)
        plt.subplot(1, 2, 2)
        # 获取所有对象类型
        all_types = set()
        for s in self.snapshots:
            all_types.update(s['object_counts'].keys())
        
        # 找出最常见的5种类型
        type_counts = defaultdict(int)
        for s in self.snapshots:
            for t, count in s['object_counts'].items():
                type_counts[t] += count
        
        top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_types = [t[0] for t in top_types]
        
        # 绘制这些类型的对象数量变化
        for obj_type in top_types:
            counts = [s['object_counts'].get(obj_type, 0) for s in self.snapshots]
            plt.plot(labels, counts, 'o-', linewidth=2, label=obj_type)
        
        plt.xlabel('快照')
        plt.ylabel('对象数量')
        plt.title('对象数量变化 (前5种类型)')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig('memory_usage.png')
        plt.close()
        
        print(f"内存使用图表已保存为 'memory_usage.png'")
    
    def visualize_object_graph(self, obj, max_depth=3):
        """可视化对象引用图"""
        # 检查是否是包装类对象
        if isinstance(obj, ObjectWrapper):
            obj = obj.obj
            
        G = nx.DiGraph()
        visited = set()
        
        def add_node(obj, name=None, depth=0):
            if depth > max_depth:
                return
            
            obj_id = id(obj)
            if obj_id in visited:
                return obj_id
            
            visited.add(obj_id)
            
            # 为节点创建标签
            if name:
                node_name = f"{name}\n({type(obj).__name__})"
            else:
                node_name = f"Object {obj_id}\n({type(obj).__name__})"
            
            G.add_node(obj_id, label=node_name)
            
            # 处理不同类型的对象
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (dict, list, set, tuple)) or hasattr(value, '__dict__'):
                        value_id = add_node(value, str(key), depth + 1)
                        if value_id:
                            G.add_edge(obj_id, value_id)
            
            elif isinstance(obj, (list, tuple, set)):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list, set, tuple)) or hasattr(item, '__dict__'):
                        item_id = add_node(item, f"[{i}]", depth + 1)
                        if item_id:
                            G.add_edge(obj_id, item_id)
            
            elif hasattr(obj, '__dict__'):
                for attr, value in obj.__dict__.items():
                    if isinstance(value, (dict, list, set, tuple)) or hasattr(value, '__dict__'):
                        value_id = add_node(value, attr, depth + 1)
                        if value_id:
                            G.add_edge(obj_id, value_id)
            
            return obj_id
        
        # 从根对象开始构建图
        add_node(obj, "Root")
        
        # 使用Graphviz布局绘制图形
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G)
        
        nx.draw(G, pos, with_labels=False, node_color='lightblue', 
                node_size=1500, arrows=True, edge_color='gray')
        
        # 添加节点标签
        labels = nx.get_node_attributes(G, 'label')
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
        
        plt.title(f"对象引用图 (限制深度: {max_depth})")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig('object_graph.png')
        plt.close()
        
        print(f"对象引用图已保存为 'object_graph.png'") 