import time
import gc
import sys
from typing import Dict, List, Optional, Any, TypeVar, Generic, Callable

T = TypeVar('T')

class ObjectPool(Generic[T]):
    """
    一个通用的对象池实现，用于复用对象以减少内存分配和垃圾回收开销
    
    Generic[T] 使得这个类可以处理任意类型的对象
    """
    def __init__(self, factory: Callable[[], T], reset_func: Callable[[T], None], 
                 initial_size: int = 10, max_size: int = 100):
        """
        初始化对象池
        
        Args:
            factory: 创建新对象的工厂函数
            reset_func: 重置对象状态的函数
            initial_size: 初始池大小
            max_size: 池的最大容量
        """
        self.factory = factory
        self.reset_func = reset_func
        self.max_size = max_size
        self._pool: List[T] = []
        
        # 预创建对象
        for _ in range(initial_size):
            self._pool.append(factory())
        
        # 统计信息
        self.created_count = initial_size
        self.reused_count = 0
        self.returned_count = 0
    
    def acquire(self) -> T:
        """从池中获取一个对象"""
        if self._pool:
            # 如果池中有可用对象，复用它
            obj = self._pool.pop()
            self.reused_count += 1
            return obj
        else:
            # 否则创建新对象
            self.created_count += 1
            return self.factory()
    
    def release(self, obj: T) -> None:
        """将对象归还到池中"""
        # 重置对象状态
        self.reset_func(obj)
        self.returned_count += 1
        
        # 如果池未满，则添加到池中
        if len(self._pool) < self.max_size:
            self._pool.append(obj)
    
    def clear(self) -> None:
        """清空对象池"""
        self._pool.clear()
    
    def size(self) -> int:
        """返回当前池中对象数量"""
        return len(self._pool)
    
    def stats(self) -> Dict[str, int]:
        """返回池的统计信息"""
        return {
            "created": self.created_count,
            "reused": self.reused_count,
            "returned": self.returned_count,
            "available": len(self._pool)
        }


# 测试对象池性能
class ExpensiveObject:
    """一个模拟大型对象的类，创建和销毁开销较大"""
    def __init__(self, size: int = 1000000):
        # 模拟一个大型对象
        self.data = [0] * size
        self.initialized = True
    
    def process(self, value: int) -> int:
        """模拟对象的操作"""
        if not hasattr(self, 'initialized') or not self.initialized:
            raise ValueError("对象未正确初始化")
        
        # 模拟一些复杂计算
        result = sum(self.data[:100]) + value
        return result
    
    def reset(self) -> None:
        """重置对象状态"""
        # 只重置必要的状态，而不释放大型内存
        self.data[0] = 0
        self.initialized = True


def run_without_pool(iterations: int, size: int) -> float:
    """不使用对象池的情况"""
    start_time = time.time()
    
    for i in range(iterations):
        # 每次都创建新对象
        obj = ExpensiveObject(size)
        result = obj.process(i)
        # 对象在离开作用域后被垃圾回收
    
    return time.time() - start_time


def run_with_pool(pool: ObjectPool[ExpensiveObject], iterations: int) -> float:
    """使用对象池的情况"""
    start_time = time.time()
    
    for i in range(iterations):
        # 从池中获取对象
        obj = pool.acquire()
        result = obj.process(i)
        # 归还对象到池中
        pool.release(obj)
    
    return time.time() - start_time


def memory_usage() -> int:
    """获取当前内存使用量的粗略估计"""
    gc.collect()
    return len(gc.get_objects())


# 运行测试
if __name__ == "__main__":
    iterations = 1000
    object_size = 100000  # 较小的值以加快测试速度
    
    print("== 对象池性能测试 ==")
    
    # 对象工厂函数
    factory = lambda: ExpensiveObject(object_size)
    # 对象重置函数
    reset = lambda obj: obj.reset()
    
    # 创建对象池
    pool = ObjectPool(factory, reset, initial_size=10, max_size=50)
    
    print(f"初始内存对象数量: {memory_usage()}")
    
    # 测试不使用对象池
    print("\n不使用对象池:")
    memory_before = memory_usage()
    time_without_pool = run_without_pool(iterations, object_size)
    memory_after = memory_usage()
    print(f"执行时间: {time_without_pool:.4f} 秒")
    print(f"内存对象增加: {memory_after - memory_before}")
    
    # 强制垃圾回收
    gc.collect()
    
    # 测试使用对象池
    print("\n使用对象池:")
    memory_before = memory_usage()
    time_with_pool = run_with_pool(pool, iterations)
    memory_after = memory_usage()
    print(f"执行时间: {time_with_pool:.4f} 秒")
    print(f"内存对象增加: {memory_after - memory_before}")
    
    # 显示对象池统计信息
    stats = pool.stats()
    print("\n对象池统计:")
    print(f"创建的对象: {stats['created']}")
    print(f"重用的对象: {stats['reused']}")
    print(f"归还的对象: {stats['returned']}")
    print(f"当前可用对象: {stats['available']}")
    
    # 性能比较
    speedup = time_without_pool / time_with_pool
    print(f"\n性能提升: {speedup:.2f}x 倍")
    
    # 清理
    pool.clear()


# 实际应用案例：数据库连接池
print("\n\n== 数据库连接池示例 ==")

class DatabaseConnection:
    """模拟数据库连接"""
    def __init__(self, conn_str: str = "default_connection"):
        self.conn_str = conn_str
        self.is_open = False
        # 模拟连接建立耗时
        time.sleep(0.01)
        self.open()
        print(f"创建新连接: {conn_str}")
    
    def open(self) -> None:
        """打开连接"""
        if not self.is_open:
            # 模拟连接耗时
            time.sleep(0.001)
            self.is_open = True
    
    def close(self) -> None:
        """关闭连接"""
        if self.is_open:
            # 模拟关闭耗时
            time.sleep(0.001)
            self.is_open = False
    
    def execute(self, query: str) -> List[Dict[str, Any]]:
        """执行查询"""
        if not self.is_open:
            raise ValueError("连接已关闭")
        
        # 模拟查询执行
        time.sleep(0.005)
        return [{"id": 1, "data": "result"}]
    
    def reset(self) -> None:
        """重置连接状态"""
        # 保持连接打开，但清除任何事务状态
        self.open()


class ConnectionPool(ObjectPool[DatabaseConnection]):
    """数据库连接池"""
    def __init__(self, conn_str: str, min_size: int = 5, max_size: int = 20):
        factory = lambda: DatabaseConnection(conn_str)
        reset_func = lambda conn: conn.reset()
        super().__init__(factory, reset_func, min_size, max_size)
        self.conn_str = conn_str


def simulate_web_requests(pool: ConnectionPool, num_requests: int) -> float:
    """模拟多个并发web请求"""
    start_time = time.time()
    
    for i in range(num_requests):
        # 从连接池获取连接
        conn = pool.acquire()
        
        try:
            # 执行查询
            result = conn.execute(f"SELECT * FROM users WHERE id = {i}")
        finally:
            # 确保连接被归还
            pool.release(conn)
    
    return time.time() - start_time


# 测试连接池
connection_pool = ConnectionPool("mysql://localhost:3306/testdb", min_size=5, max_size=20)
num_requests = 100

# 执行模拟请求
print(f"处理 {num_requests} 个并发请求:")
time_taken = simulate_web_requests(connection_pool, num_requests)
print(f"总耗时: {time_taken:.4f} 秒")

# 显示连接池统计信息
stats = connection_pool.stats()
print("\n连接池统计:")
print(f"创建的连接: {stats['created']}")
print(f"重用的连接: {stats['reused']}")
print(f"归还的连接: {stats['returned']}")
print(f"当前可用连接: {stats['available']}")

# 清理
for _ in range(connection_pool.size()):
    conn = connection_pool.acquire()
    conn.close()

connection_pool.clear()
print("连接池已清理") 