#!/usr/bin/env python3
# regex_demo.py - 正则表达式功能演示

import re
import time
import sys
from collections import defaultdict

def basic_patterns():
    """演示基本匹配模式"""
    print("\n==== 基本匹配模式 ====")
    
    text = "Python3.9是2020年10月发布的，而Python3.10则是2021年10月发布的。"
    
    # 匹配普通字符
    pattern = r"Python"
    matches = re.findall(pattern, text)
    print(f"匹配普通字符 '{pattern}':")
    print(f"  结果: {matches}")
    print(f"  匹配次数: {len(matches)}")
    
    # 匹配数字
    pattern = r"\d+\.\d+"
    matches = re.findall(pattern, text)
    print(f"\n匹配小数 '{pattern}':")
    print(f"  结果: {matches}")
    
    # 匹配特定模式
    pattern = r"Python\d+\.\d+"
    matches = re.findall(pattern, text)
    print(f"\n匹配Python版本 '{pattern}':")
    print(f"  结果: {matches}")
    
    # 匹配年份
    pattern = r"\d{4}年"
    matches = re.findall(pattern, text)
    print(f"\n匹配年份 '{pattern}':")
    print(f"  结果: {matches}")

def character_classes():
    """演示字符类和特殊字符"""
    print("\n==== 字符类和特殊字符 ====")
    
    text = "电话: 010-12345678 或 13812345678, 邮箱: example@python.org, 网址: https://www.python.org"
    
    # 匹配电话号码
    pattern = r"\d{3}-\d{8}|\d{11}"
    matches = re.findall(pattern, text)
    print(f"匹配电话号码 '{pattern}':")
    print(f"  结果: {matches}")
    
    # 匹配邮箱
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    matches = re.findall(pattern, text)
    print(f"\n匹配邮箱 '{pattern}':")
    print(f"  结果: {matches}")
    
    # 匹配URL
    pattern = r"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/[a-zA-Z0-9._/-]*)?"
    matches = re.findall(pattern, text)
    print(f"\n匹配URL '{pattern}':")
    print(f"  结果: {re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)}")
    
    # 字符类简写
    print("\n字符类简写:")
    
    examples = {
        r"\d": "数字 [0-9]",
        r"\D": "非数字 [^0-9]",
        r"\w": "单词字符 [a-zA-Z0-9_]",
        r"\W": "非单词字符",
        r"\s": "空白字符 [ \t\n\r\f\v]",
        r"\S": "非空白字符"
    }
    
    for pattern, desc in examples.items():
        count = len(re.findall(pattern, text))
        print(f"  {pattern} ({desc}): {count}个匹配")

def groups_and_capturing():
    """演示分组和捕获"""
    print("\n==== 分组和捕获 ====")
    
    text = """
    文件名1: document_2023-05-15.pdf
    文件名2: report_2023-06-20.docx
    文件名3: data_2023-07-10.xlsx
    """
    
    # 基本分组
    pattern = r"(\w+)_(\d{4}-\d{2}-\d{2})\.(\w+)"
    matches = re.findall(pattern, text)
    
    print(f"分组匹配 '{pattern}':")
    print("  结果:")
    for match in matches:
        print(f"    文件类型: {match[0]}, 日期: {match[1]}, 扩展名: {match[2]}")
    
    # 命名分组
    pattern = r"(?P<type>\w+)_(?P<date>\d{4}-\d{2}-\d{2})\.(?P<ext>\w+)"
    
    print(f"\n命名分组 '{pattern}':")
    for match in re.finditer(pattern, text):
        print(f"    文件类型: {match.group('type')}, 日期: {match.group('date')}, 扩展名: {match.group('ext')}")
    
    # 非捕获分组
    pattern = r"(?:\w+)_(\d{4}-\d{2}-\d{2})\.(?:\w+)"
    matches = re.findall(pattern, text)
    
    print(f"\n非捕获分组 '{pattern}':")
    print(f"  只捕获日期: {matches}")

def greedy_vs_nongreedy():
    """
    演示贪婪与非贪婪匹配的区别
    
    贪婪匹配：尽可能多地匹配字符（默认行为）
    非贪婪匹配：尽可能少地匹配字符（需要添加?修饰符）
    """
    print("\n==== 贪婪匹配 vs 非贪婪匹配 ====")
    
    # 示例文本 - HTML格式
    html = """
    <div class="article">
        <h1>Python 正则表达式</h1>
        <p>正则表达式是文本处理的强大工具</p>
        <p>Python通过re模块提供正则表达式支持</p>
    </div>
    <div class="footer">
        <p>版权所有 © 2023</p>
    </div>
    """
    
    print("原始HTML文本:")
    print(html)
    
    # 贪婪匹配示例 - 匹配所有<p>标签内容
    print("\n1. 贪婪匹配示例（.*）:")
    pattern_greedy = r"<p>(.*)</p>"
    matches_greedy = re.findall(pattern_greedy, html, re.DOTALL)
    print(f"匹配结果 ({len(matches_greedy)}个):")
    for i, match in enumerate(matches_greedy, 1):
        print(f"  匹配{i}: {match}")
    
    print("\n解释: 贪婪模式匹配了从第一个<p>到最后一个</p>之间的所有内容，包括中间的其他标签")
    
    # 非贪婪匹配示例
    print("\n2. 非贪婪匹配示例（.*?）:")
    pattern_nongreedy = r"<p>(.*?)</p>"
    matches_nongreedy = re.findall(pattern_nongreedy, html, re.DOTALL)
    print(f"匹配结果 ({len(matches_nongreedy)}个):")
    for i, match in enumerate(matches_nongreedy, 1):
        print(f"  匹配{i}: {match}")
    
    print("\n解释: 非贪婪模式分别匹配了每个<p>标签中的内容，不会跨越多个标签")
    
    # 实际应用：提取链接
    html_links = """
    <a href="https://www.python.org">Python官网</a>
    <div class="content">
        <a href="https://docs.python.org">Python文档</a>
        <a href="https://pypi.org">PyPI</a>
    </div>
    """
    
    print("\n3. 从HTML中提取链接:")
    print(html_links)
    
    # 贪婪匹配链接
    print("\n使用贪婪匹配:")
    greedy_links = re.findall(r'href="(.*)"', html_links)
    print(f"结果 ({len(greedy_links)}个):")
    for link in greedy_links:
        print(f"  {link}")
    
    # 非贪婪匹配链接
    print("\n使用非贪婪匹配:")
    nongreedy_links = re.findall(r'href="(.*?)"', html_links)
    print(f"结果 ({len(nongreedy_links)}个):")
    for link in nongreedy_links:
        print(f"  {link}")
    
    # 可视化比较
    print("\n贪婪与非贪婪匹配的可视化比较:")
    text = "开始<tag>内容1</tag>中间<tag>内容2</tag>结束"
    print(f"文本: {text}")
    
    pattern_g = r"<tag>.*</tag>"
    match_g = re.search(pattern_g, text)
    g_start, g_end = match_g.span()
    
    pattern_ng = r"<tag>.*?</tag>"
    matches_ng = list(re.finditer(pattern_ng, text))
    
    print("\n贪婪匹配结果:")
    print(text)
    print(" " * g_start + "^" + "~" * (g_end - g_start - 2) + "^")
    print(" " * g_start + match_g.group())
    
    print("\n非贪婪匹配结果:")
    print(text)
    for match in matches_ng:
        ng_start, ng_end = match.span()
        print(" " * ng_start + "^" + "~" * (ng_end - ng_start - 2) + "^")
        print(" " * ng_start + match.group())
    
    # 实用建议
    print("\n实用建议:")
    print("1. 提取HTML标签内容时，优先使用非贪婪匹配 .*?")
    print("2. 解析结构化数据（如JSON、XML）时，考虑使用专用库替代正则表达式")
    print("3. 在复杂模式中，组合使用贪婪和非贪婪模式可以精确控制匹配行为")
    print("4. 始终测试边缘情况，尤其是处理用户生成的内容时")

def lookaround_assertions():
    """演示前瞻和后顾断言"""
    print("\n==== 前瞻和后顾断言 ====")
    
    text = "价格: ¥100, $200, €300, £400"
    
    # 正向前瞻
    pattern = r"\d+(?=\s*,|\s*$)"
    matches = re.findall(pattern, text)
    
    print(f"正向前瞻 '{pattern}':")
    print(f"  查找后面是逗号或行尾的数字")
    print(f"  结果: {matches}")
    
    # 负向前瞻
    pattern = r"\d+(?!,)"
    matches = re.findall(pattern, text)
    
    print(f"\n负向前瞻 '{pattern}':")
    print(f"  查找后面不是逗号的数字")
    print(f"  结果: {matches}")
    
    # 正向后顾
    pattern = r"(?<=¥)\d+"
    matches = re.findall(pattern, text)
    
    print(f"\n正向后顾 '{pattern}':")
    print(f"  查找前面是¥的数字")
    print(f"  结果: {matches}")
    
    # 负向后顾
    pattern = r"(?<!¥)\d+"
    matches = re.findall(pattern, text)
    
    print(f"\n负向后顾 '{pattern}':")
    print(f"  查找前面不是¥的数字")
    print(f"  结果: {matches}")
    
    # 实际应用
    text = "产品A: ¥1299, 产品B: ¥899, 产品C: $1499, 产品D: €2099"
    
    # 提取人民币价格
    pattern = r"产品\w+:\s*¥(\d+)"
    matches = re.findall(pattern, text)
    
    print(f"\n提取人民币价格 '{pattern}':")
    print(f"  结果: {matches}")
    
    # 更复杂的断言组合
    pattern = r"(?<=产品)[A-Z](?=:)"
    matches = re.findall(pattern, text)
    
    print(f"\n使用断言组合提取产品标识 '{pattern}':")
    print(f"  结果: {matches}")

def regex_functions():
    """演示正则表达式主要函数"""
    print("\n==== 正则表达式函数 ====")
    
    text = "Python是一种编程语言，发布于1991年。Python 3.9是2020年10月发布的。"
    
    # re.search
    pattern = r"Python \d\.\d"
    result = re.search(pattern, text)
    
    print(f"re.search('{pattern}', text):")
    if result:
        print(f"  匹配到: {result.group()}")
        print(f"  位置: {result.start()}-{result.end()}")
    else:
        print("  未匹配")
    
    # re.match
    pattern = r"Python"
    result = re.match(pattern, text)
    
    print(f"\nre.match('{pattern}', text):")
    if result:
        print(f"  匹配到: {result.group()}")
    else:
        print("  未匹配")
    
    # re.fullmatch
    pattern = r"Python.*\d{4}年.*\."
    result = re.fullmatch(pattern, text)
    
    print(f"\nre.fullmatch('{pattern}', text):")
    if result:
        print(f"  完全匹配: {result.group()}")
    else:
        print("  未完全匹配")
    
    # re.findall 与 re.finditer
    pattern = r"Python(?:\s\d\.\d)?"
    findall_result = re.findall(pattern, text)
    
    print(f"\nre.findall('{pattern}', text):")
    print(f"  结果: {findall_result}")
    
    print(f"\nre.finditer('{pattern}', text):")
    for match in re.finditer(pattern, text):
        print(f"  匹配: {match.group()}, 位置: {match.start()}-{match.end()}")
    
    # re.split
    pattern = r"[,。]"
    split_result = re.split(pattern, text)
    
    print(f"\nre.split('{pattern}', text):")
    print(f"  结果: {split_result}")
    
    # re.sub 和 re.subn
    pattern = r"Python (\d\.\d)"
    replacement = r"Python版本\1"
    sub_result = re.sub(pattern, replacement, text)
    subn_result = re.subn(pattern, replacement, text)
    
    print(f"\nre.sub('{pattern}', '{replacement}', text):")
    print(f"  结果: {sub_result}")
    
    print(f"\nre.subn('{pattern}', '{replacement}', text):")
    print(f"  结果: {subn_result}")

def compilation_and_flags():
    """演示编译和标志"""
    print("\n==== 编译和标志 ====")
    
    text = """
    Python是一种编程语言
    python可以用于Web开发
    PYTHON支持面向对象编程
    """
    
    # 不区分大小写
    pattern = r"python"
    
    # 不使用标志
    matches1 = re.findall(pattern, text)
    
    # 使用标志
    matches2 = re.findall(pattern, text, re.IGNORECASE)
    
    print(f"标志示例 - re.IGNORECASE:")
    print(f"  不使用标志: {matches1}")
    print(f"  使用标志: {matches2}")
    
    # 编译正则表达式
    start_time = time.time()
    for _ in range(1000):
        re.findall(r"python", text, re.IGNORECASE)
    non_compiled_time = time.time() - start_time
    
    compiled_pattern = re.compile(r"python", re.IGNORECASE)
    start_time = time.time()
    for _ in range(1000):
        compiled_pattern.findall(text)
    compiled_time = time.time() - start_time
    
    print(f"\n编译性能对比 (1000次搜索):")
    print(f"  非编译: {non_compiled_time:.6f}秒")
    print(f"  编译后: {compiled_time:.6f}秒")
    print(f"  速度提升: {non_compiled_time/compiled_time:.2f}倍")
    
    # 常用标志组合
    pattern = r"^python.*$"
    matches1 = re.findall(pattern, text, re.MULTILINE)
    matches2 = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
    
    print(f"\n多标志组合:")
    print(f"  re.MULTILINE: {matches1}")
    print(f"  re.MULTILINE | re.IGNORECASE: {matches2}")

def practical_examples():
    """实际应用示例"""
    print("\n==== 实际应用示例 ====")
    
    # 示例1: 提取日志中的信息
    print("示例1: 解析日志文件")
    
    log_text = """
    2023-07-15 08:30:45 INFO [MainThread] 应用程序启动
    2023-07-15 08:30:47 DEBUG [ThreadID-123] 连接数据库
    2023-07-15 08:30:50 WARNING [ThreadID-123] 查询执行时间过长: 2.5秒
    2023-07-15 08:31:02 ERROR [MainThread] 无法访问配置文件: /etc/app/config.ini
    2023-07-15 08:32:15 INFO [ThreadID-124] 用户登录: user123
    """
    
    log_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) \[([^\]]+)\] (.+)'
    
    log_entries = []
    for match in re.finditer(log_pattern, log_text):
        log_entries.append({
            'timestamp': match.group(1),
            'level': match.group(2),
            'thread': match.group(3),
            'message': match.group(4)
        })
    
    print("  解析后的日志条目:")
    for entry in log_entries:
        print(f"    [{entry['timestamp']}] {entry['level']} - {entry['message']}")
    
    # 统计各级别日志数量
    level_counts = defaultdict(int)
    for entry in log_entries:
        level_counts[entry['level']] += 1
    
    print("\n  日志级别统计:")
    for level, count in level_counts.items():
        print(f"    {level}: {count}")
    
    # 示例2: 验证输入
    print("\n示例2: 验证用户输入")
    
    def validate_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_password(password):
        # 至少8位，包含大小写字母，数字和特殊字符
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])[A-Za-z\d!@#$%^&*]{8,}$'
        return bool(re.match(pattern, password))
    
    test_emails = [
        "user@example.com",       # 有效
        "invalid-email",          # 无效
        "user@domain",            # 无效
        "user.name@company.cn"    # 有效
    ]
    
    test_passwords = [
        "Password1!",             # 有效
        "password",               # 无效 (没有大写、数字和特殊字符)
        "Pass1!",                 # 无效 (不足8位)
        "PASSWORD123!"            # 无效 (没有小写字母)
    ]
    
    print("  邮箱验证:")
    for email in test_emails:
        result = "有效" if validate_email(email) else "无效"
        print(f"    {email}: {result}")
    
    print("\n  密码验证:")
    for password in test_passwords:
        result = "有效" if validate_password(password) else "无效"
        print(f"    {password}: {result}")
    
    # 示例3: 替换和处理文本
    print("\n示例3: 文本处理和替换")
    
    html_text = """
    <article>
        <h1>Python正则表达式</h1>
        <p>正则表达式提供了强大的文本处理能力。</p>
        <p>通过<code>re</code>模块，我们可以在Python中使用正则表达式。</p>
        <div class="example">
            <pre><code>import re
pattern = r'\\w+'
re.findall(pattern, text)</code></pre>
        </div>
    </article>
    """
    
    # 移除HTML标签
    def strip_html(html):
        pattern = r'<[^>]+>'
        return re.sub(pattern, '', html)
    
    # 提取代码块
    def extract_code(html):
        pattern = r'<code>(.*?)</code>'
        return re.findall(pattern, html, re.DOTALL)
    
    # 应用
    plain_text = strip_html(html_text)
    code_blocks = extract_code(html_text)
    
    print("  移除HTML标签后的文本:")
    print(f"    {' '.join(line.strip() for line in plain_text.split('\n') if line.strip())}")
    
    print("\n  提取的代码块:")
    for i, code in enumerate(code_blocks, 1):
        print(f"    代码块 {i}:")
        print(f"      {code}")

def regex_pitfalls():
    """常见陷阱和优化"""
    print("\n==== 常见陷阱和优化 ====")
    
    # 灾难性回溯
    print("陷阱1: 灾难性回溯")
    
    # 生成一个导致灾难性回溯的文本
    problematic_text = "a" * 25 + "!"
    
    # 有问题的模式 (会导致指数级回溯)
    bad_pattern = r'a+a+a+a+!$'
    
    # 优化的模式
    good_pattern = r'a+!$'
    
    print("  测试文本:", problematic_text)
    
    # 测试有问题的模式
    start_time = time.time()
    re.search(bad_pattern, problematic_text)
    bad_time = time.time() - start_time
    
    # 测试优化的模式
    start_time = time.time()
    re.search(good_pattern, problematic_text)
    good_time = time.time() - start_time
    
    print(f"  有问题的模式 '{bad_pattern}' 耗时: {bad_time:.6f}秒")
    print(f"  优化的模式 '{good_pattern}' 耗时: {good_time:.6f}秒")
    print(f"  性能差异: {bad_time/good_time:.1f}倍")
    
    # Unicode陷阱
    print("\n陷阱2: Unicode处理")
    
    unicode_text = "Python程序员"
    
    # 不正确的字符数计算
    incorrect_count = len(re.findall(r'.', unicode_text))
    
    # 正确的方式
    correct_count = len(unicode_text)
    
    print(f"  文本: {unicode_text}")
    print(f"  用 '.'. 匹配的字符数: {incorrect_count}")
    print(f"  实际字符数: {correct_count}")
    
    # 过度使用捕获组
    print("\n陷阱3: 过度使用捕获组")
    
    text = "程序版本: Python-3.9.5"
    
    # 不必要的捕获组
    pattern_with_groups = r'Python-(\d+)\.(\d+)\.(\d+)'
    
    # 非捕获组 (仅在需要时捕获)
    pattern_optimized = r'Python-(?:\d+\.){2}\d+'
    
    match_with_groups = re.search(pattern_with_groups, text)
    match_optimized = re.search(pattern_optimized, text)
    
    print(f"  使用多个捕获组: {match_with_groups.group()}, 组: {match_with_groups.groups()}")
    print(f"  使用非捕获组: {match_optimized.group()}")
    
    # 编译正则表达式的最佳实践
    print("\n最佳实践: 编译和复用")
    
    # 全局编译模式
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    test_email = "user@example.com"
    
    # 多次使用同一模式，只编译一次
    for _ in range(3):
        print(f"  验证邮箱: {EMAIL_PATTERN.match(test_email) is not None}")

def main():
    """主函数"""
    print("===== 正则表达式(re模块)演示 =====")
    print("Python版本:", sys.version)
    
    basic_patterns()
    character_classes()
    groups_and_capturing()
    greedy_vs_nongreedy()
    lookaround_assertions()
    regex_functions()
    compilation_and_flags()
    practical_examples()
    regex_pitfalls()
    
    print("\n演示完成!")

if __name__ == "__main__":
    main() 