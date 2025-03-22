import objgraph

# 创建嵌套引用
a = [1, 2]
b = [3, 4, a]
c = {'key': b}
d = [a, c]

# 生成引用图
objgraph.show_refs([d], filename='nested_refs.png')