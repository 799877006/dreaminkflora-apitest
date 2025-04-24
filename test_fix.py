#!/usr/bin/env python3
"""
测试脚本，验证修复是否有效
"""
import sys

try:
    from api_test_project.api_client.client import APIClient
    print("成功导入 APIClient 类")
    
    from api_test_project.test_runner import test_runner
    print("成功导入 test_runner 模块")
    
    print("修复成功！所有导入正常工作。")
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1) 