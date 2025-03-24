#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
迷你天气预报助手

一个简单的命令行天气查询工具，可以：
1. 获取指定城市的当前天气和预报
2. 保存查询历史
3. 提供简单的数据可视化

作者: Python学习者
日期: 2023年12月
"""

import os
import json
import time
import requests
import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

# 天气图标映射（用于命令行显示）
WEATHER_ICONS = {
    "Clear": "☀️ ",
    "Clouds": "☁️ ",
    "Rain": "🌧️ ",
    "Drizzle": "🌦️ ",
    "Thunderstorm": "⛈️ ",
    "Snow": "❄️ ",
    "Mist": "🌫️ ",
    "Fog": "🌫️ ",
    "Haze": "🌫️ ",
    "Default": "🌡️ "
}

# 温度颜色区间（用于命令行彩色显示）
TEMP_COLORS = {
    "cold": "\033[94m",  # 蓝色 < 10°C
    "cool": "\033[96m",  # 青色 10-20°C
    "warm": "\033[93m",  # 黄色 20-30°C
    "hot": "\033[91m",   # 红色 > 30°C
    "end": "\033[0m"     # 结束颜色
}

@dataclass
class WeatherData:
    """天气数据结构"""
    city: str
    country: str
    condition: str
    description: str
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    timestamp: int
    forecast: List[Dict[str, Any]]

    @property
    def icon(self) -> str:
        """获取天气对应的图标"""
        return WEATHER_ICONS.get(self.condition, WEATHER_ICONS["Default"])

    @property
    def temp_color(self) -> str:
        """根据温度获取颜色代码"""
        if self.temperature < 10:
            return TEMP_COLORS["cold"]
        elif self.temperature < 20:
            return TEMP_COLORS["cool"]
        elif self.temperature < 30:
            return TEMP_COLORS["warm"]
        else:
            return TEMP_COLORS["hot"]


class WeatherService:
    """天气服务类，负责API交互和数据处理"""
    
    def __init__(self):
        # OpenWeatherMap API密钥（免费注册获取）
        # 请替换为你自己的API密钥
        self.api_key = "YOUR_API_KEY"
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.history_file = os.path.expanduser("~/.weather_history.json")
        self.history = self._load_history()
    
    def _load_history(self) -> Dict[str, int]:
        """加载查询历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_history(self):
        """保存查询历史"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)
    
    def get_weather(self, city: str) -> Optional[WeatherData]:
        """获取指定城市的天气数据"""
        # 更新查询历史
        if city in self.history:
            self.history[city] += 1
        else:
            self.history[city] = 1
        self._save_history()
        
        # 构建API请求
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric"  # 使用摄氏度
        }
        
        try:
            # 获取当前天气
            current_url = f"{self.base_url}/weather"
            response = requests.get(current_url, params=params)
            response.raise_for_status()
            current_data = response.json()
            
            # 获取天气预报
            forecast_url = f"{self.base_url}/forecast"
            response = requests.get(forecast_url, params=params)
            response.raise_for_status()
            forecast_data = response.json()
            
            # 从响应中提取需要的数据
            weather_data = WeatherData(
                city=current_data["name"],
                country=current_data["sys"]["country"],
                condition=current_data["weather"][0]["main"],
                description=current_data["weather"][0]["description"],
                temperature=current_data["main"]["temp"],
                feels_like=current_data["main"]["feels_like"],
                humidity=current_data["main"]["humidity"],
                wind_speed=current_data["wind"]["speed"],
                timestamp=current_data["dt"],
                forecast=self._process_forecast(forecast_data["list"][:8])  # 未来24小时
            )
            return weather_data
            
        except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
            print(f"获取天气数据时出错: {e}")
            return None
    
    def _process_forecast(self, forecast_list: List[Dict]) -> List[Dict[str, Any]]:
        """处理天气预报数据"""
        processed = []
        for item in forecast_list:
            processed.append({
                "time": item["dt"],
                "temp": item["main"]["temp"],
                "condition": item["weather"][0]["main"],
                "description": item["weather"][0]["description"]
            })
        return processed
    
    def get_popular_cities(self, limit: int = 5) -> List[str]:
        """获取最常查询的城市"""
        return sorted(self.history, key=self.history.get, reverse=True)[:limit]


class WeatherApp:
    """天气应用类，负责用户交互"""
    
    def __init__(self):
        self.weather_service = WeatherService()
    
    def display_weather(self, weather: WeatherData):
        """显示天气信息"""
        print("\n" + "="*50)
        print(f"{weather.icon} {weather.city}, {weather.country} 天气")
        print("="*50)
        
        # 当前天气
        local_time = datetime.datetime.fromtimestamp(weather.timestamp)
        print(f"观测时间: {local_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"天气状况: {weather.condition} - {weather.description}")
        
        # 使用颜色显示温度
        temp_color = weather.temp_color
        print(f"当前温度: {temp_color}{weather.temperature:.1f}°C{TEMP_COLORS['end']}")
        print(f"体感温度: {temp_color}{weather.feels_like:.1f}°C{TEMP_COLORS['end']}")
        print(f"湿度: {weather.humidity}%")
        print(f"风速: {weather.wind_speed} m/s")
        
        # 未来预报
        print("\n未来24小时预报:")
        print("-"*50)
        for i, forecast in enumerate(weather.forecast, 1):
            time_str = datetime.datetime.fromtimestamp(forecast["time"]).strftime('%H:%M')
            icon = WEATHER_ICONS.get(forecast["condition"], WEATHER_ICONS["Default"])
            
            # 选择温度颜色
            temp = forecast["temp"]
            if temp < 10:
                temp_color = TEMP_COLORS["cold"]
            elif temp < 20:
                temp_color = TEMP_COLORS["cool"]
            elif temp < 30:
                temp_color = TEMP_COLORS["warm"]
            else:
                temp_color = TEMP_COLORS["hot"]
                
            print(f"{time_str}: {icon} {forecast['condition']}, "
                  f"{temp_color}{temp:.1f}°C{TEMP_COLORS['end']}")
        
        print("="*50 + "\n")
    
    def display_ascii_chart(self, weather: WeatherData):
        """显示ASCII温度图表"""
        temps = [f["temp"] for f in weather.forecast]
        max_temp = max(temps)
        min_temp = min(temps)
        range_temp = max(1, max_temp - min_temp)  # 避免除以零
        
        print("\n温度变化趋势图:")
        print("-"*50)
        
        # 图表高度
        chart_height = 5
        
        for i in range(chart_height, -1, -1):
            line = ""
            for temp in temps:
                # 计算温度对应的高度
                bar_height = int((temp - min_temp) / range_temp * chart_height)
                if bar_height >= i:
                    line += "█ "
                else:
                    line += "  "
            
            # 添加Y轴标签
            temp_value = min_temp + (range_temp / chart_height) * i
            line = f"{temp_value:4.1f}°C |" + line
            print(line)
        
        # X轴
        print("       " + "-"*(len(temps)*2))
        
        # X轴标签
        times = [datetime.datetime.fromtimestamp(f["time"]).strftime('%H') for f in weather.forecast]
        time_line = "       "
        for time in times:
            time_line += time + " "
        print(time_line)
        
        print("-"*50 + "\n")
    
    def run(self):
        """运行天气应用"""
        print("\n欢迎使用迷你天气预报助手！")
        
        while True:
            print("\n选项:")
            print("1. 查询城市天气")
            print("2. 查看常用城市")
            print("3. 退出")
            
            choice = input("\n请选择 (1-3): ")
            
            if choice == '1':
                city = input("请输入城市名称 (例如: Beijing): ")
                print(f"正在获取 {city} 的天气信息...")
                weather = self.weather_service.get_weather(city)
                if weather:
                    self.display_weather(weather)
                    self.display_ascii_chart(weather)
            
            elif choice == '2':
                popular_cities = self.weather_service.get_popular_cities()
                if not popular_cities:
                    print("暂无查询历史")
                else:
                    print("\n您最常查询的城市:")
                    for i, city in enumerate(popular_cities, 1):
                        count = self.weather_service.history[city]
                        print(f"{i}. {city} (查询次数: {count})")
                    
                    subchoice = input("\n输入编号查询对应城市天气，或按Enter返回: ")
                    if subchoice.isdigit() and 1 <= int(subchoice) <= len(popular_cities):
                        city = popular_cities[int(subchoice)-1]
                        print(f"正在获取 {city} 的天气信息...")
                        weather = self.weather_service.get_weather(city)
                        if weather:
                            self.display_weather(weather)
                            self.display_ascii_chart(weather)
            
            elif choice == '3':
                print("\n感谢使用迷你天气预报助手！再见！")
                break
            
            else:
                print("无效选择，请重试。")


if __name__ == "__main__":
    app = WeatherApp()
    app.run()