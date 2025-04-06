import asyncio
import json
import logging
import random
import string
import time
import argparse
from contextlib import suppress
from typing import Dict, List

import aiohttp
import websockets
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LoadTest")

# 测试配置默认参数
DEFAULT_CONFIG = {
    "ws_server_url": "ws://localhost:8000/ws/{room_id}",
    "api_server_url": "http://localhost:8000",
    "total_connections": 1000,  # 总连接数
    "connections_per_second": 100,  # 每秒建立的连接数
    "rooms": 10,  # 聊天室数量
    "message_interval": 5.0,  # 消息发送间隔(秒)
    "test_duration": 60,  # 测试持续时间(秒)
    "ping_interval": 30.0,  # 心跳间隔(秒)
    "random_seed": 42,  # 随机种子
}

# 测试统计指标
test_stats = {
    "start_time": 0,
    "connections_sent": 0,
    "connections_active": 0,
    "connections_failed": 0,
    "connections_closed": 0,
    "messages_sent": 0,
    "messages_received": 0,
    "errors": 0,
    "latencies": [],  # 消息延迟(ms)
    "connect_times": [],  # 连接建立时间(ms)
    "timestamps": []  # 记录每个事件的时间戳
}

# 测试过程中的事件记录
events = []

class ChatClient:
    """WebSocket聊天客户端模拟器"""
    
    def __init__(self, server_url: str, user_id: str, room_id: str):
        self.server_url = server_url.format(room_id=room_id)
        self.user_id = user_id
        self.room_id = room_id
        self.websocket = None
        self.is_connected = False
        self.message_count = 0
        self.latencies = []
        self.last_ping_time = 0
        
    async def connect(self) -> bool:
        """建立WebSocket连接"""
        connect_start = time.time()
        try:
            # 在URL中添加用户ID查询参数
            url_with_params = f"{self.server_url}?user_id={self.user_id}"
            
            self.websocket = await websockets.connect(
                url_with_params,
                ping_interval=None,  # 禁用自动ping
                close_timeout=5
            )
            self.is_connected = True
            
            # 记录连接时间
            connect_time = (time.time() - connect_start) * 1000  # 转为毫秒
            test_stats["connect_times"].append(connect_time)
            
            test_stats["connections_active"] += 1
            events.append({
                "type": "connect",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time(),
                "connect_time": connect_time
            })
            return True
            
        except Exception as e:
            test_stats["connections_failed"] += 1
            events.append({
                "type": "connect_error",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time(),
                "error": str(e)
            })
            return False
    
    async def disconnect(self):
        """关闭WebSocket连接"""
        if self.websocket and self.is_connected:
            with suppress(Exception):
                await self.websocket.close()
            self.is_connected = False
            test_stats["connections_active"] -= 1
            test_stats["connections_closed"] += 1
            events.append({
                "type": "disconnect",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time()
            })
    
    async def send_message(self, content: str = None):
        """发送聊天消息"""
        if not self.is_connected or not self.websocket:
            return False
            
        try:
            if content is None:
                # 生成随机消息内容
                content = f"Test message {self.message_count} from {self.user_id}"
            
            message = {
                "content": content,
                "message_type": "text",
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            self.message_count += 1
            test_stats["messages_sent"] += 1
            
            events.append({
                "type": "message_sent",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time()
            })
            return True
            
        except Exception as e:
            test_stats["errors"] += 1
            events.append({
                "type": "message_error",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time(),
                "error": str(e)
            })
            return False
    
    async def send_ping(self):
        """发送ping消息用于保持连接"""
        if not self.is_connected or not self.websocket:
            return False
            
        try:
            message = {
                "message_type": "ping",
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            self.last_ping_time = time.time()
            return True
            
        except Exception as e:
            test_stats["errors"] += 1
            return False
    
    async def receive_messages(self):
        """接收并处理消息"""
        if not self.is_connected or not self.websocket:
            return
            
        try:
            async for message in self.websocket:
                try:
                    # 解析消息
                    data = json.loads(message)
                    
                    # 处理ping-pong消息
                    if data.get("type") == "pong":
                        continue
                        
                    # 计算消息延迟
                    if "timestamp" in data and data["timestamp"] is not None:
                        latency = (time.time() - float(data["timestamp"])) * 1000  # 转为毫秒
                        self.latencies.append(latency)
                        test_stats["latencies"].append(latency)
                    
                    test_stats["messages_received"] += 1
                    events.append({
                        "type": "message_received",
                        "user_id": self.user_id,
                        "room_id": self.room_id,
                        "timestamp": time.time()
                    })
                    
                except json.JSONDecodeError:
                    test_stats["errors"] += 1
                    
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            test_stats["connections_active"] -= 1
            test_stats["connections_closed"] += 1
            events.append({
                "type": "connection_closed",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time()
            })
            
        except Exception as e:
            test_stats["errors"] += 1
            self.is_connected = False
            events.append({
                "type": "receive_error",
                "user_id": self.user_id,
                "room_id": self.room_id,
                "timestamp": time.time(),
                "error": str(e)
            })

async def client_session(config, user_id, room_id):
    """完整的客户端会话流程"""
    client = ChatClient(config["ws_server_url"], user_id, room_id)
    
    # 连接到服务器
    connected = await client.connect()
    if not connected:
        return
    
    # 启动消息接收任务
    receive_task = asyncio.create_task(client.receive_messages())
    
    try:
        # 定期发送消息和心跳
        end_time = time.time() + config["test_duration"]
        while time.time() < end_time and client.is_connected:
            # 发送测试消息
            if random.random() < 0.2:  # 20%概率发送消息
                await client.send_message()
            
            # 发送心跳
            if time.time() - client.last_ping_time > config["ping_interval"]:
                await client.send_ping()
                
            # 随机等待
            await asyncio.sleep(random.uniform(0.5, config["message_interval"]))
    
    finally:
        # 关闭连接
        await client.disconnect()
        
        # 取消接收任务
        receive_task.cancel()
        with suppress(asyncio.CancelledError):
            await receive_task

async def check_server_health(config):
    """检查服务器健康状态"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{config['api_server_url']}/health") as response:
                if response.status != 200:
                    logger.error(f"Server health check failed with status {response.status}")
                    return False
                    
                data = await response.json()
                logger.info(f"Server health: {data['status']}")
                logger.info(f"Active connections: {data['connections']['total_connections']}")
                return data['status'] == 'ok'
    except Exception as e:
        logger.error(f"Server health check failed: {str(e)}")
        return False

async def run_load_test(config):
    """运行负载测试"""
    # 设置随机数种子
    random.seed(config["random_seed"])
    
    # 记录开始时间
    test_stats["start_time"] = time.time()
    logger.info(f"Starting load test with {config['total_connections']} connections across {config['rooms']} rooms")
    
    # 检查服务器健康状态
    server_ok = await check_server_health(config)
    if not server_ok:
        logger.error("Server health check failed, aborting test")
        return
    
    # 创建测试会话任务
    tasks = []
    pbar = tqdm(total=config["total_connections"], desc="Creating connections")
    
    for i in range(config["total_connections"]):
        # 生成用户ID和分配聊天室
        user_id = f"user_{i+1}"
        room_id = f"room_{(i % config['rooms']) + 1}"
        
        # 创建并启动客户端会话
        task = asyncio.create_task(client_session(config, user_id, room_id))
        tasks.append(task)
        test_stats["connections_sent"] += 1
        
        # 按照指定速率建立连接
        if (i + 1) % config["connections_per_second"] == 0:
            pbar.update(config["connections_per_second"])
            await asyncio.sleep(1)
        
    # 更新剩余的进度条
    remaining = config["total_connections"] % config["connections_per_second"]
    if remaining > 0:
        pbar.update(remaining)
    pbar.close()
    
    # 等待所有任务完成
    total_duration = config["test_duration"] + 10  # 额外等待时间
    try:
        _, pending = await asyncio.wait(tasks, timeout=total_duration)
        if pending:
            logger.warning(f"{len(pending)} tasks did not complete within the timeout period")
            for task in pending:
                task.cancel()
    except Exception as e:
        logger.error(f"Error waiting for tasks to complete: {str(e)}")
    
    # 最后检查服务器状态
    await check_server_health(config)

def generate_report(config):
    """生成测试报告"""
    # 计算测试持续时间
    duration = time.time() - test_stats["start_time"]
    
    # 基本指标
    print("\n============== 负载测试报告 ==============")
    print(f"测试持续时间: {duration:.2f} 秒")
    print(f"总连接请求数: {test_stats['connections_sent']}")
    print(f"成功建立连接数: {test_stats['connections_sent'] - test_stats['connections_failed']}")
    print(f"连接失败数: {test_stats['connections_failed']}")
    print(f"消息发送数: {test_stats['messages_sent']}")
    print(f"消息接收数: {test_stats['messages_received']}")
    print(f"错误数: {test_stats['errors']}")
    
    # 性能指标
    if test_stats["connect_times"]:
        print(f"\n连接时间 (ms):")
        print(f"  最小: {min(test_stats['connect_times']):.2f}")
        print(f"  最大: {max(test_stats['connect_times']):.2f}")
        print(f"  平均: {sum(test_stats['connect_times']) / len(test_stats['connect_times']):.2f}")
        print(f"  中位数: {sorted(test_stats['connect_times'])[len(test_stats['connect_times']) // 2]:.2f}")
        
    if test_stats["latencies"]:
        print(f"\n消息延迟 (ms):")
        print(f"  最小: {min(test_stats['latencies']):.2f}")
        print(f"  最大: {max(test_stats['latencies']):.2f}")
        print(f"  平均: {sum(test_stats['latencies']) / len(test_stats['latencies']):.2f}")
        print(f"  中位数: {sorted(test_stats['latencies'])[len(test_stats['latencies']) // 2]:.2f}")
    
    # 吞吐量
    print(f"\n吞吐量:")
    print(f"  连接/秒: {test_stats['connections_sent'] / duration:.2f}")
    print(f"  消息/秒: {test_stats['messages_sent'] / duration:.2f}")
    
    # 保存详细事件日志
    events_df = pd.DataFrame(events)
    if not events_df.empty:
        events_df.to_csv("load_test_events.csv", index=False)
        print("\n详细事件日志已保存到 load_test_events.csv")
    
    # 生成图表
    try:
        generate_charts()
    except Exception as e:
        logger.error(f"Error generating charts: {str(e)}")

def generate_charts():
    """生成测试图表"""
    if not events:
        return
        
    # 转换事件为DataFrame
    df = pd.DataFrame(events)
    df["relative_time"] = df["timestamp"] - test_stats["start_time"]
    
    # 按时间段分组统计连接数
    time_bins = pd.cut(df["relative_time"], bins=30)
    connections_over_time = df[df["type"].isin(["connect", "disconnect", "connection_closed"])].groupby([time_bins, "type"]).size().unstack().fillna(0)
    
    if not connections_over_time.empty:
        # 计算活跃连接数
        if "connect" in connections_over_time.columns:
            if "disconnect" not in connections_over_time.columns:
                connections_over_time["disconnect"] = 0
            if "connection_closed" not in connections_over_time.columns:
                connections_over_time["connection_closed"] = 0
                
            connections_over_time["active"] = connections_over_time["connect"].cumsum() - \
                                            connections_over_time["disconnect"].cumsum() - \
                                            connections_over_time["connection_closed"].cumsum()
            
            # 绘制连接数图表
            plt.figure(figsize=(12, 6))
            connections_over_time["active"].plot(kind='line', color='blue', marker='o')
            plt.title('Active Connections Over Time')
            plt.xlabel('Time (s)')
            plt.ylabel('Connections')
            plt.grid(True)
            plt.savefig("connections_chart.png")
            plt.close()
            print("连接数图表已保存到 connections_chart.png")
    
    # 绘制延迟分布图
    if test_stats["latencies"]:
        plt.figure(figsize=(12, 6))
        plt.hist(test_stats["latencies"], bins=50, color='green', alpha=0.7)
        plt.title('Message Latency Distribution')
        plt.xlabel('Latency (ms)')
        plt.ylabel('Frequency')
        plt.grid(True)
        plt.savefig("latency_chart.png")
        plt.close()
        print("延迟分布图已保存到 latency_chart.png")
        
    # 按时间段分组统计消息数
    messages_over_time = df[df["type"].isin(["message_sent", "message_received"])].groupby([time_bins, "type"]).size().unstack().fillna(0)
    
    if not messages_over_time.empty:
        # 绘制消息吞吐量图表
        plt.figure(figsize=(12, 6))
        if "message_sent" in messages_over_time.columns:
            messages_over_time["message_sent"].plot(kind='line', color='blue', marker='o', label='Sent')
        if "message_received" in messages_over_time.columns:
            messages_over_time["message_received"].plot(kind='line', color='green', marker='x', label='Received')
        plt.title('Message Throughput Over Time')
        plt.xlabel('Time (s)')
        plt.ylabel('Messages')
        plt.legend()
        plt.grid(True)
        plt.savefig("messages_chart.png")
        plt.close()
        print("消息吞吐量图表已保存到 messages_chart.png")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='WebSocket Chat Server Load Test')
    parser.add_argument('--server', type=str, help='WebSocket server URL', default=DEFAULT_CONFIG["ws_server_url"])
    parser.add_argument('--api', type=str, help='API server URL', default=DEFAULT_CONFIG["api_server_url"])
    parser.add_argument('--connections', type=int, help='Total number of connections', default=DEFAULT_CONFIG["total_connections"])
    parser.add_argument('--rate', type=int, help='Connections per second', default=DEFAULT_CONFIG["connections_per_second"])
    parser.add_argument('--rooms', type=int, help='Number of chat rooms', default=DEFAULT_CONFIG["rooms"])
    parser.add_argument('--duration', type=int, help='Test duration in seconds', default=DEFAULT_CONFIG["test_duration"])
    parser.add_argument('--message-interval', type=float, help='Message sending interval in seconds', default=DEFAULT_CONFIG["message_interval"])
    args = parser.parse_args()
    
    # 更新配置
    config = DEFAULT_CONFIG.copy()
    config.update({
        "ws_server_url": args.server,
        "api_server_url": args.api,
        "total_connections": args.connections,
        "connections_per_second": args.rate,
        "rooms": args.rooms,
        "test_duration": args.duration,
        "message_interval": args.message_interval
    })
    
    # 显示测试配置
    print("\n============== 负载测试配置 ==============")
    for key, value in config.items():
        print(f"{key}: {value}")
    print("========================================\n")
    
    # 运行测试
    asyncio.run(run_load_test(config))
    
    # 生成报告
    generate_report(config)

if __name__ == "__main__":
    main() 