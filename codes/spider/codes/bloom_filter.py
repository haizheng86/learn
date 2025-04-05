#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
布隆过滤器去重实现
适用于大规模URL去重，内存效率比传统Set集合高出10倍以上
"""

from pybloom_live import ScalableBloomFilter
from scrapy.utils.job import job_dir
from scrapy.dupefilters import BaseDupeFilter
import os
import logging

logger = logging.getLogger(__name__)

class BloomFilterDupeFilter(BaseDupeFilter):
    """基于布隆过滤器的请求去重过滤器"""
    
    def __init__(self, path=None, debug=False, 
                 initial_capacity=100000000, error_rate=0.00001):
        """
        初始化布隆过滤器
        :param path: 持久化路径，如不提供则不持久化
        :param debug: 是否启用调试模式
        :param initial_capacity: 预计处理的请求数量
        :param error_rate: 可接受的误判率
        """
        self.file = None
        self.fingerprints = ScalableBloomFilter(
            initial_capacity=initial_capacity,
            error_rate=error_rate,
            mode=ScalableBloomFilter.LARGE_SET_GROWTH
        )
        self.debug = debug
        self.logdupes = True
        self.path = path
        self.seen_count = 0
        
        if path:
            # 确保目录存在
            dirname = os.path.dirname(path)
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname)
            
            # 尝试从持久化文件加载
            self._load()
    
    @classmethod
    def from_settings(cls, settings):
        """从Scrapy设置创建去重过滤器"""
        debug = settings.getbool('DUPEFILTER_DEBUG', False)
        initial_capacity = settings.getint('BLOOM_INITIAL_CAPACITY', 100000000)
        error_rate = settings.getfloat('BLOOM_ERROR_RATE', 0.00001)
        
        return cls(
            path=job_dir(settings),
            debug=debug,
            initial_capacity=initial_capacity,
            error_rate=error_rate
        )
        
    @classmethod
    def from_crawler(cls, crawler):
        """从爬虫实例创建去重过滤器"""
        return cls.from_settings(crawler.settings)
    
    def request_seen(self, request):
        """
        检查请求是否已被处理过
        :param request: Scrapy请求对象
        :return: True如果请求已处理过，否则False
        """
        fp = self.request_fingerprint(request)
        if fp in self.fingerprints:
            return True
        self.fingerprints.add(fp)
        self.seen_count += 1
        
        if self.seen_count % 100000 == 0:
            logger.info(f"已处理请求数: {self.seen_count}")
            # 定期保存
            if self.path:
                self._dump()
                
        return False
    
    def request_fingerprint(self, request):
        """生成请求的指纹"""
        # 这里简化处理，实际使用可能需要更复杂的指纹生成算法
        # 例如考虑请求方法、请求体、请求头等
        return f"{request.url}_{request.method}"
    
    def _load(self):
        """从文件加载布隆过滤器"""
        try:
            if os.path.exists(self.path):
                with open(self.path, 'rb') as f:
                    self.fingerprints = ScalableBloomFilter.fromfile(f)
                logger.info(f"从 {self.path} 加载布隆过滤器成功")
        except Exception as e:
            logger.error(f"加载布隆过滤器失败: {str(e)}")
    
    def _dump(self):
        """将布隆过滤器保存到文件"""
        try:
            with open(self.path, 'wb') as f:
                self.fingerprints.tofile(f)
            logger.info(f"布隆过滤器保存到 {self.path} 成功")
        except Exception as e:
            logger.error(f"保存布隆过滤器失败: {str(e)}")
    
    def close(self, reason=''):
        """关闭时保存布隆过滤器"""
        if self.path:
            self._dump()
    
    def log(self, request, spider):
        """记录重复请求日志"""
        if self.debug:
            msg = "重复的请求: %(request)s"
            self.logger.debug(msg, {'request': request}, extra={'spider': spider})
        elif self.logdupes:
            msg = ("忽略重复请求: %(request)s"
                   " - 指纹已存在")
            self.logger.debug(msg, {'request': request}, extra={'spider': spider})


# 示例用法
if __name__ == "__main__":
    # 创建布隆过滤器
    bf = ScalableBloomFilter(initial_capacity=1000, error_rate=0.001)
    
    # 添加URL
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3",
        "https://example.com/page1",  # 重复
        "https://example.com/page4"
    ]
    
    for url in urls:
        if url in bf:
            print(f"URL已存在: {url}")
        else:
            bf.add(url)
            print(f"添加新URL: {url}")
            
    # 内存占用估计
    print(f"\n布隆过滤器当前使用的比特数: {bf.num_bits_m}")
    print(f"估计的元素数量: {len(bf)}")
    # 假设使用Python Set
    print(f"如果使用Python Set, 估计内存占用: {len(set(urls)) * 84} 字节")  # 粗略估计 