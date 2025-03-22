import gc
print(f"gc阈值: {gc.get_threshold()}")
print(f"当前各代对象数: {gc.get_count()}")
