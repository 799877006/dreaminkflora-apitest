"""
API客户端实现模块，包含与LLM服务交互的客户端类
"""
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, AsyncIterable
import asyncio
import time
from urllib.parse import urljoin
import json
import csv
import random
from pathlib import Path

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from api_test_project.metrics.metrics_collector import MetricsCollector
from api_test_project.models.response_models import (
    ApiResponse, 
    TokenStreamEvent, 
    ErrorResponse
)


class ApiClientConfig(BaseModel):
    """API客户端配置"""
    base_url: str = "https://server.dreaminkflora.com/api/v1/"
    timeout: float = 60.0  # 默认超时时间（秒）
    max_retries: int = 3   # 最大重试次数
    retry_delay: float = 1.0  # 重试间隔（秒）
    tokens_file: str = Field(default="access_tokens.csv")  # 访问令牌文件
    metrics_enabled: bool = True  # 是否启用指标收集


class LlmApiClient:
    """LLM API客户端基类"""
    
    def __init__(self, config: ApiClientConfig):
        """
        初始化API客户端
        
        Args:
            config: 客户端配置
        """
        self.config = config
        self.token_data = self._load_tokens()  # 包含user_id(手机号)和token的映射
        self.tokens = list(self.token_data.values())  # 为了保持兼容性
        self.user_ids = list(self.token_data.keys())  # 手机号列表
        self.metrics_collector = MetricsCollector() if config.metrics_enabled else None
        self._client: Optional[httpx.AsyncClient] = None
        self._last_token_index = 0  # 上次使用的令牌索引
    
    def _load_tokens(self) -> Dict[str, str]:
        """
        从CSV文件加载访问令牌和用户ID(手机号)
        
        Returns:
            字典，键为用户ID(手机号)，值为访问令牌
        """
        token_data = {}
        try:
            token_file = Path(self.config.tokens_file)
            if not token_file.exists():
                logger.warning(f"令牌文件 {self.config.tokens_file} 不存在")
                return {}
            
            with open(token_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # 跳过表头
                for row in reader:
                    if len(row) > 1:
                        user_id = row[0]  # 手机号作为user_id
                        token = row[1]    # 访问令牌
                        token_data[user_id] = token
        except Exception as e:
            logger.error(f"加载令牌文件出错: {e}")
        
        logger.info(f"已加载 {len(token_data)} 个用户令牌")
        return token_data
    
    def get_token(self, user_id: Optional[str] = None) -> str:
        """
        获取一个访问令牌，如果指定了user_id则返回该用户的令牌
        
        Args:
            user_id: 可选，指定的用户ID(手机号)
            
        Returns:
            访问令牌
        """
        if not self.tokens:
            raise ValueError("没有可用的访问令牌")
        
        if user_id:
            # 如果指定了用户ID，返回该用户的令牌
            if user_id in self.token_data:
                return self.token_data[user_id]
            else:
                logger.warning(f"未找到用户ID {user_id} 对应的令牌，将使用随机令牌")
                
        # 未指定用户ID或用户ID不存在，轮流使用令牌
        self._last_token_index = (self._last_token_index + 1) % len(self.tokens)
        return self.tokens[self._last_token_index]
    
    def get_user_id(self) -> str:
        """
        获取与当前令牌对应的用户ID(手机号)
        
        Returns:
            用户ID(手机号)
        """
        if not self.user_ids:
            raise ValueError("没有可用的用户ID")
        
        return self.user_ids[self._last_token_index]
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        获取异步HTTP客户端
        
        Returns:
            异步HTTP客户端
        """
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
            timeout = httpx.Timeout(self.config.timeout)
            self._client = httpx.AsyncClient(limits=limits, timeout=timeout)
        return self._client
    
    async def close(self) -> None:
        """关闭客户端连接"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False,
        retry_count: int = 0,
        user_id: Optional[str] = None
    ) -> Union[ApiResponse, AsyncIterable]:
        """
        发送API请求
        
        Args:
            method: HTTP方法 (GET, POST, PATCH等)
            endpoint: API端点路径
            token: 认证令牌
            params: 查询参数
            json_data: JSON请求体
            headers: 请求头
            stream: 是否使用流式响应
            retry_count: 当前重试次数
            user_id: 可选，指定的用户ID(手机号)
            
        Returns:
            API响应或流式生成器
        """
        if retry_count > self.config.max_retries:
            raise Exception(f"请求达到最大重试次数: {endpoint}")
        
        url = self.config.base_url + endpoint
        client = await self.get_client()
        
        # 准备请求头
        request_headers = headers or {}
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        
        # 记录请求开始时间
        start_time = time.time()
        first_byte_time = None
        
        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=request_headers,
                timeout=self.config.timeout,
                follow_redirects=True
            )
            
            # 记录首字节时间
            first_byte_time = time.time()
            
            if stream:
                # 返回流式生成器
                return self._handle_streaming_response(response, start_time, first_byte_time)
            
            # 处理非流式响应
            content = await response.aread()
            complete_time = time.time()
            
            # 收集指标
            if self.metrics_collector:
                self.metrics_collector.record_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    ttft=first_byte_time - start_time if first_byte_time else None,
                    ttct=complete_time - start_time,
                    content_length=len(content),
                    is_stream=False
                )
            
            if response.status_code >= 400:
                print(response.content)
                # 处理错误响应
                error_data = json.loads(content)
                error = ErrorResponse(
                    status_code=response.status_code,
                    message=error_data.get("message", "未知错误"),
                    error=error_data.get("error")
                )
                logger.error(f"API请求失败: {error.status_code} - {error.message}")
                return ApiResponse(success=False, error=error)
            
            try:
                data = json.loads(content)
                # 根据响应格式，确保我们返回正确的数据
                # 新的API响应格式示例:
                # {
                #     "timestamp": 1745380923971,
                #     "statusCode": 201,
                #     "message": "作品创建成功",
                #     "data": { ... },
                #     "error": null
                # }
                
                # 检查是否包含statusCode字段，表示使用新的API响应格式
                if "statusCode" in data and "message" in data:
                    status_code = data.get("statusCode", 200)
                    # 如果状态码表示错误但没有触发HTTP错误状态
                    if status_code >= 400:
                        error = ErrorResponse(
                            status_code=status_code,
                            message=data.get("message", "API错误"),
                            error=data.get("error")
                        )
                        logger.error(f"API请求返回错误状态码: {status_code} - {data.get('message')}")
                        return ApiResponse(success=False, error=error)
                    
                return ApiResponse(success=True, data=data)
            except json.JSONDecodeError:
                return ApiResponse(success=True, data={"content": content.decode('utf-8')})
            
        except httpx.TimeoutException as e:
            logger.warning(f"请求超时 ({retry_count+1}/{self.config.max_retries}): {url} - {str(e)}")
            if self.metrics_collector:
                self.metrics_collector.record_error("timeout", str(e), endpoint)
            await asyncio.sleep(self.config.retry_delay)
            return await self._make_request(method, endpoint, token, params, json_data, 
                                           headers, stream, retry_count + 1, user_id)
            
        except httpx.NetworkError as e:
            logger.warning(f"网络错误 ({retry_count+1}/{self.config.max_retries}): {url} - {str(e)}")
            if self.metrics_collector:
                self.metrics_collector.record_error("network", str(e), endpoint)
            await asyncio.sleep(self.config.retry_delay)
            return await self._make_request(method, endpoint, token, params, json_data, 
                                           headers, stream, retry_count + 1, user_id)
            
        except Exception as e:
            logger.error(f"请求异常: {url} - {str(e)}")
            if self.metrics_collector:
                self.metrics_collector.record_error("general", str(e), endpoint)
            # 重要错误，不重试
            return ApiResponse(
                success=False, 
                error=ErrorResponse(status_code=500, message=str(e))
            )
    
    async def _handle_streaming_response(
        self, 
        response: httpx.Response, 
        start_time: float,
        first_byte_time: float
    ) -> AsyncIterable:
        """
        处理流式响应
        
        Args:
            response: HTTP响应对象
            start_time: 请求开始时间
            first_byte_time: 首字节接收时间
            
        Yields:
            解析后的事件对象
        """
        endpoint = str(response.url).replace(self.config.base_url, "")
        total_tokens = 0
        
        if response.status_code >= 400:
            # 处理错误响应
            error_text = await response.aread()
            error_data = json.loads(error_text)
            error = ErrorResponse(
                status_code=response.status_code,
                message=error_data.get("message", "流式请求失败"),
                error=error_data.get("error")
            )
            logger.error(f"流式API请求失败: {error.status_code} - {error.message}")
            if self.metrics_collector:
                self.metrics_collector.record_error("stream", error.message, endpoint)
            yield TokenStreamEvent(event_type="error", data=error.dict())
            return
        
        try:
            async for chunk in response.aiter_lines():
                if not chunk.strip():
                    continue
                
                # 解析SSE格式
                if chunk.startswith("data:"):
                    try:
                        data = json.loads(chunk[5:].strip())
                        token = data.get("content", "")
                        total_tokens += 1
                        
                        # 构造事件
                        event = TokenStreamEvent(
                            event_type="token",
                            data={"token": token, "index": total_tokens}
                        )
                        yield event
                    except json.JSONDecodeError:
                        # 处理非JSON格式的数据块
                        yield TokenStreamEvent(
                            event_type="raw",
                            data={"content": chunk[5:].strip()}
                        )
                elif chunk.startswith("event:"):
                    event_type = chunk[6:].strip()
                    yield TokenStreamEvent(event_type=event_type)
            
            # 流结束
            complete_time = time.time()
            if self.metrics_collector:
                self.metrics_collector.record_stream_completion(
                    endpoint=endpoint,
                    status_code=response.status_code,
                    ttft=first_byte_time - start_time,
                    ttct=complete_time - start_time,
                    token_count=total_tokens
                )
            
            yield TokenStreamEvent(event_type="done")
                
        except Exception as e:
            logger.error(f"处理流式响应出错: {str(e)}")
            if self.metrics_collector:
                self.metrics_collector.record_error("stream_process", str(e), endpoint)
            yield TokenStreamEvent(event_type="error", data={"error": str(e)})
    
    async def get(
        self, 
        endpoint: str, 
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        发送GET请求
        
        Args:
            endpoint: API端点
            token: 访问令牌
            params: 查询参数
            headers: 请求头
            stream: 是否流式响应
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        return await self._make_request(
            method="GET",
            endpoint=endpoint,
            token=token or self.get_token(user_id),
            params=params,
            headers=headers,
            stream=stream,
            user_id=user_id
        )
    
    async def post(
        self, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        发送POST请求
        
        Args:
            endpoint: API端点
            data: 请求体数据
            token: 访问令牌
            params: 查询参数
            headers: 请求头
            stream: 是否流式响应
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        return await self._make_request(
            method="POST",
            endpoint=endpoint,
            token=token or self.get_token(user_id),
            params=params,
            json_data=data,
            headers=headers,
            stream=stream,
            user_id=user_id
        )
    
    async def patch(
        self, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        发送PATCH请求
        
        Args:
            endpoint: API端点
            data: 请求体数据
            token: 访问令牌
            params: 查询参数
            headers: 请求头
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        return await self._make_request(
            method="PATCH",
            endpoint=endpoint,
            token=token or self.get_token(user_id),
            params=params,
            json_data=data,
            headers=headers,
            user_id=user_id
        )
    
    async def delete(
        self, 
        endpoint: str, 
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        发送DELETE请求
        
        Args:
            endpoint: API端点
            token: 访问令牌
            params: 查询参数
            headers: 请求头
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        return await self._make_request(
            method="DELETE",
            endpoint=endpoint,
            token=token or self.get_token(user_id),
            params=params,
            headers=headers,
            user_id=user_id
        )

# 为了兼容性，添加别名
APIClient = LlmApiClient 