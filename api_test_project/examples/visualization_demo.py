"""
可视化功能演示脚本
"""
import asyncio
import random
import time
import os
from typing import List, Dict, Any
from pathlib import Path

from loguru import logger

from api_test_project.metrics.metrics_collector import MetricsCollector
from api_test_project.models.response_models import ApiResponse, ErrorResponse
from api_test_project.utils.logging_utils import setup_logging


# 配置日志系统
setup_logging(log_dir="logs", test_name="visualization_demo", add_test_details_file=True)


async def simulate_sse_request(
    metrics: MetricsCollector, 
    endpoint: str, 
    success_rate: float = 0.95,
    min_tokens: int = 50,
    max_tokens: int = 500
) -> None:
    """
    模拟一个SSE请求
    
    Args:
        metrics: 指标收集器
        endpoint: API端点
        success_rate: 成功率
        min_tokens: 最小令牌数
        max_tokens: 最大令牌数
    """
    start_time = time.time()
    
    # 生成唯一请求ID
    request_id = f"sse-{endpoint}-{time.time()}-{random.randint(1000, 9999)}"
    
    # 记录请求开始
    logger.info(f"开始SSE请求: {request_id} 端点: {endpoint}")
    
    # 模拟请求延迟
    ttft = random.uniform(0.1, 0.5)  # 模拟首令牌时间 (0.1-0.5秒)
    await asyncio.sleep(ttft)
    
    # 模拟生成的令牌数
    token_count = random.randint(min_tokens, max_tokens)
    
    # 模拟每个令牌的生成时间
    tokens_per_second = random.uniform(15, 30)  # 每秒15-30个令牌
    ttct = token_count / tokens_per_second  # 完整响应时间
    
    # 加入一点随机性
    ttct = ttct * random.uniform(0.9, 1.1)
    
    # 模拟完整的请求处理时间
    await asyncio.sleep(ttct - ttft)  # 减去已经等待的TTFT时间
    
    # 随机决定是否成功
    is_success = random.random() < success_rate
    status_code = 200 if is_success else random.choice([429, 500, 503])
    
    if is_success:
        # 记录成功的流式请求
        metrics.record_stream_completion(
            endpoint=endpoint,
            status_code=status_code,
            ttft=ttft,
            ttct=ttct,
            token_count=token_count,
            request_id=request_id  # 使用相同的请求ID
        )
        logger.info(f"SSE请求完成: {request_id} 状态码: {status_code} 令牌数: {token_count}")
    else:
        # 记录失败的请求
        error_type = random.choice(["timeout", "server_error", "rate_limit"])
        error_message = f"模拟错误: {error_type}"
        metrics.record_error(error_type, error_message, endpoint)
        logger.warning(f"SSE请求失败: {request_id} 错误类型: {error_type}")


async def simulate_regular_request(
    metrics: MetricsCollector, 
    endpoint: str, 
    success_rate: float = 0.98,
    min_latency: float = 0.05,
    max_latency: float = 0.3
) -> None:
    """
    模拟一个常规(非SSE)请求
    
    Args:
        metrics: 指标收集器
        endpoint: API端点
        success_rate: 成功率
        min_latency: 最小延迟
        max_latency: 最大延迟
    """
    start_time = time.time()
    
    # 生成唯一请求ID
    request_id = f"regular-{endpoint}-{time.time()}-{random.randint(1000, 9999)}"
    
    # 记录请求开始
    logger.info(f"开始普通请求: {request_id} 端点: {endpoint}")
    
    # 模拟请求延迟
    latency = random.uniform(min_latency, max_latency)
    await asyncio.sleep(latency)
    
    # 随机决定是否成功
    is_success = random.random() < success_rate
    status_code = 200 if is_success else random.choice([400, 401, 404, 429, 500])
    
    if is_success:
        # 记录成功的请求
        metrics.record_request(
            endpoint=endpoint,
            method="GET",
            status_code=status_code,
            ttct=latency,
            content_length=random.randint(500, 10000),
            is_stream=False,
            request_id=request_id
        )
        logger.info(f"普通请求完成: {request_id} 状态码: {status_code}")
    else:
        # 记录失败的请求
        error_type = random.choice(["validation_error", "auth_error", "not_found", "rate_limit", "server_error"])
        error_message = f"模拟错误: {error_type}"
        metrics.record_error(error_type, error_message, endpoint)
        logger.warning(f"普通请求失败: {request_id} 错误类型: {error_type}")


async def run_demo() -> None:
    """运行演示"""
    logger.info("开始可视化功能演示")
    
    # 初始化指标收集器
    metrics = MetricsCollector(results_dir="results/visualization_demo")
    
    # 定义模拟的API端点
    sse_endpoints = [
        "/api/v1/generate_content",
        "/api/v1/generate_chapter_outline",
        "/api/v1/expand_text"
    ]
    
    regular_endpoints = [
        "/api/v1/books",
        "/api/v1/chapters",
        "/api/v1/user/info",
        "/api/v1/settings"
    ]
    
    # 创建任务列表
    tasks = []
    
    # 模拟SSE请求 (大模型请求)
    for _ in range(50):
        endpoint = random.choice(sse_endpoints)
        tasks.append(
            simulate_sse_request(
                metrics, 
                endpoint,
                success_rate=0.95,
                min_tokens=100,
                max_tokens=1000
            )
        )
    
    # 模拟常规请求
    for _ in range(200):
        endpoint = random.choice(regular_endpoints)
        tasks.append(
            simulate_regular_request(
                metrics, 
                endpoint,
                success_rate=0.98
            )
        )
    
    # 执行所有任务
    logger.info(f"执行 {len(tasks)} 个模拟请求任务")
    
    # 随机打乱任务顺序
    random.shuffle(tasks)
    
    # 以不同的并发度执行任务
    for i in range(0, len(tasks), 10):
        batch = tasks[i:i+10]
        await asyncio.gather(*batch)
        # 稍微等待一下，模拟真实请求间隔
        await asyncio.sleep(0.1)
    
    # 保存结果并生成可视化
    logger.info("所有请求完成，保存结果并生成可视化")
    result_path = metrics.save_results("demo_test", 50)
    
    logger.info(f"演示完成! 请查看结果和可视化报告: {result_path}")
    logger.info(f"HTML报告路径: {result_path}/performance_report.html")


if __name__ == "__main__":
    asyncio.run(run_demo()) 