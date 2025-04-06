#!/usr/bin/env python3
"""
进程监控守护程序

该脚本用于监控启动的聊天系统进程，确保在接收到终止信号时能强制关闭所有相关进程。
"""

import os
import sys
import signal
import time
import subprocess
import psutil
import atexit
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ShutdownMonitor")

# 存储PID文件
PID_FILE = "/tmp/chat_system_pids.txt"
# 存储主进程PID
MAIN_PID_FILE = "/tmp/chat_system_main_pid.txt"

# 标记清理过程是否已经开始，防止递归
_CLEANUP_IN_PROGRESS = False
# 标记是否已经屏蔽了信号
_SIGNALS_BLOCKED = False

def find_child_processes(parent_pid):
    """查找指定父进程的所有子进程"""
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
        return [p.pid for p in children]
    except psutil.NoSuchProcess:
        return []

def kill_process_tree(pid, sig=signal.SIGTERM, include_parent=True):
    """终止进程树"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        for child in children:
            try:
                logger.info(f"终止子进程 {child.pid}")
                child.send_signal(sig)
            except psutil.NoSuchProcess:
                pass
        
        if include_parent:
            logger.info(f"终止父进程 {pid}")
            parent.send_signal(sig)
    except psutil.NoSuchProcess:
        pass

def cleanup_processes():
    """清理所有相关进程"""
    global _CLEANUP_IN_PROGRESS, _SIGNALS_BLOCKED
    
    # 如果清理已在进行中，直接返回，防止递归
    if _CLEANUP_IN_PROGRESS:
        return
    
    _CLEANUP_IN_PROGRESS = True
    
    # 屏蔽信号处理，防止在清理过程中再次触发信号处理函数
    if not _SIGNALS_BLOCKED:
        _SIGNALS_BLOCKED = True
        # 临时忽略终止信号
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    
    try:
        logger.info("开始清理进程...")
        
        # 读取主进程PID
        try:
            if os.path.exists(MAIN_PID_FILE):
                with open(MAIN_PID_FILE, 'r') as f:
                    main_pid = int(f.read().strip())
                    logger.info(f"找到主进程 PID: {main_pid}")
                    kill_process_tree(main_pid)
        except Exception as e:
            logger.error(f"清理主进程时出错: {e}")
        
        # 读取PID文件中的所有进程
        try:
            if os.path.exists(PID_FILE):
                with open(PID_FILE, 'r') as f:
                    pids = [int(line.strip()) for line in f if line.strip()]
                    logger.info(f"发现 {len(pids)} 个进程需要终止")
                    
                    # 先尝试正常终止
                    for pid in pids:
                        try:
                            if pid != os.getpid() and psutil.pid_exists(pid):
                                logger.info(f"发送 SIGTERM 到进程 {pid}")
                                os.kill(pid, signal.SIGTERM)
                        except OSError:
                            pass
                    
                    # 等待1秒
                    time.sleep(1)
                    
                    # 检查是否仍然存在，如果存在则强制终止
                    for pid in pids:
                        try:
                            if pid != os.getpid() and psutil.pid_exists(pid):
                                logger.info(f"发送 SIGKILL 到进程 {pid}")
                                os.kill(pid, signal.SIGKILL)
                        except OSError:
                            pass
                
                # 清理PID文件
                os.unlink(PID_FILE)
                logger.info(f"已删除PID文件: {PID_FILE}")
        except Exception as e:
            logger.error(f"清理进程时出错: {e}")
        
        # 清理主进程PID文件
        try:
            if os.path.exists(MAIN_PID_FILE):
                os.unlink(MAIN_PID_FILE)
                logger.info(f"已删除主进程PID文件: {MAIN_PID_FILE}")
        except Exception as e:
            logger.error(f"清理主进程PID文件时出错: {e}")
        
        # 查找所有uvicorn和gunicorn进程
        try:
            self_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.pid != self_pid and any(x in proc.name().lower() for x in ['uvicorn', 'gunicorn', 'python']):
                        # 检查命令行参数是否包含main.py或聊天系统相关内容
                        cmdline = ' '.join(proc.cmdline())
                        if 'main.py' in cmdline or 'chat_system' in cmdline:
                            logger.info(f"发现残留进程: {proc.pid} ({proc.name()})")
                            kill_process_tree(proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.error(f"查找残留进程时出错: {e}")
        
        logger.info("进程清理完成")
    finally:
        # 恢复原来的信号处理
        if _SIGNALS_BLOCKED:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
            _SIGNALS_BLOCKED = False

def signal_handler(signum, frame):
    """信号处理函数"""
    logger.info(f"收到信号 {signum}，开始清理")
    
    # 调用清理进程函数（现在已有防递归保护）
    cleanup_processes()
    
    # 如果是终止信号，退出该脚本
    if signum in (signal.SIGTERM, signal.SIGINT):
        sys.exit(0)

def monitor_main_process():
    """监控主进程，如果主进程终止则清理所有子进程"""
    try:
        if os.path.exists(MAIN_PID_FILE):
            with open(MAIN_PID_FILE, 'r') as f:
                main_pid = int(f.read().strip())
                
                while True:
                    if not psutil.pid_exists(main_pid):
                        logger.info(f"主进程 {main_pid} 已终止，开始清理")
                        cleanup_processes()
                        break
                    time.sleep(1)
    except Exception as e:
        logger.error(f"监控主进程时出错: {e}")
    
    sys.exit(0)

def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 注册退出处理
    atexit.register(cleanup_processes)
    
    # 写入自己的PID到主进程PID文件
    with open(MAIN_PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    logger.info(f"启动进程监控 (PID: {os.getpid()})")
    
    # 如果传入了要监控的PID，则添加到PID文件
    if len(sys.argv) > 1:
        target_pid = int(sys.argv[1])
        logger.info(f"监控目标进程: {target_pid}")
        
        # 添加到PID文件，排除自己的PID
        if target_pid != os.getpid():
            with open(PID_FILE, 'a') as f:
                f.write(f"{target_pid}\n")
        
        # 添加子进程，排除自己
        for child_pid in find_child_processes(target_pid):
            if child_pid != os.getpid():
                with open(PID_FILE, 'a') as f:
                    f.write(f"{child_pid}\n")
        
        # 监控模式
        monitor_main_process()
    else:
        # 如果没有传入PID，则只进行一次清理
        cleanup_processes()

if __name__ == "__main__":
    main() 