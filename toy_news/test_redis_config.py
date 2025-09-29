#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 Redis 配置脚本
用于验证环境变量和设置是否正确传递
"""

import os
import sys
from scrapy.utils.project import get_project_settings

def test_env_vars():
    """测试环境变量"""
    print("=== 环境变量测试 ===")
    redis_vars = ['REDIS_HOST', 'REDIS_PWD', 'REDIS_PORT', 'REDIS_DB', 'TRANSLATION_QUEUE']
    
    for var in redis_vars:
        value = os.getenv(var)
        print(f"{var}: {value if value else 'NOT SET'}")
    print()

def test_scrapy_settings():
    """测试 Scrapy 设置"""
    print("=== Scrapy 设置测试 ===")
    try:
        settings = get_project_settings()
        
        redis_settings = {
            'REDIS_HOST': settings.get('REDIS_HOST'),
            'REDIS_PWD': settings.get('REDIS_PWD'),
            'REDIS_PORT': settings.get('REDIS_PORT'),
            'REDIS_DB': settings.get('REDIS_DB'),
            'TRANSLATION_QUEUE': settings.get('TRANSLATION_QUEUE')
        }
        
        for key, value in redis_settings.items():
            print(f"{key}: {value}")
            
        print()
        return redis_settings
    except Exception as e:
        print(f"获取 Scrapy 设置失败: {e}")
        return None

def test_redis_connection(redis_settings=None):
    """测试 Redis 连接"""
    print("=== Redis 连接测试 ===")
    
    if not redis_settings:
        print("没有 Redis 设置，跳过连接测试")
        return
    
    try:
        import redis
        
        # 使用获取到的设置创建 Redis 客户端
        redis_client = redis.Redis(
            host=redis_settings.get('REDIS_HOST', 'localhost'),
            port=redis_settings.get('REDIS_PORT', 6379),
            db=redis_settings.get('REDIS_DB', 0),
            password=redis_settings.get('REDIS_PWD', '') or None  # 空字符串转换为 None
        )
        
        # 测试连接
        redis_client.ping()
        print("✓ Redis 连接成功")
        
        # 测试队列操作
        queue_name = redis_settings.get('TRANSLATION_QUEUE', 'toys:translation:pending')
        queue_length = redis_client.llen(queue_name)
        print(f"✓ 翻译队列 '{queue_name}' 当前长度: {queue_length}")
        
    except ImportError:
        print("✗ redis 模块未安装")
    except redis.exceptions.ConnectionError as e:
        print(f"✗ Redis 连接失败: {e}")
    except redis.exceptions.AuthenticationError as e:
        print(f"✗ Redis 认证失败: {e}")
        print("  可能原因: 密码错误或 Redis 未配置密码")
    except Exception as e:
        print(f"✗ Redis 错误: {e}")

def main():
    print("Redis 配置测试工具\n")
    
    # 测试环境变量
    test_env_vars()
    
    # 测试 Scrapy 设置
    redis_settings = test_scrapy_settings()
    
    # 测试 Redis 连接
    test_redis_connection(redis_settings)
    
    print("\n=== 解决方案 ===")
    print("如果 Redis 密码无法获取，请尝试:")
    print("1. 设置环境变量: export REDIS_PWD=your_password")
    print("2. 通过命令行传递: scrapy crawl spider_name -s REDIS_PWD=your_password")
    print("3. 在 .env 文件中配置: REDIS_PWD=your_password")
    print("4. 检查 Redis 服务器是否需要密码认证")

if __name__ == '__main__':
    main()
