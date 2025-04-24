"""
DreaminkFlora API客户端
提供与小说生成API的交互功能
"""
import time
import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urljoin
import uuid

import httpx
import aiohttp
from aiohttp import ClientTimeout


# 配置日志记录器
logger = logging.getLogger("api_client")


class APIResponse:
    """API响应对象，记录请求结果和性能指标"""
    
    def __init__(self, 
                 request_id: str,
                 endpoint: str,
                 status_code: int,
                 success: bool,
                 ttft: float = 0.0,
                 ttct: float = 0.0,
                 first_token_time: float = 0.0,
                 complete_time: float = 0.0,
                 token_count: int = 0,
                 response_data: Optional[Dict] = None,
                 error: Optional[str] = None):
        """
        初始化API响应对象
        
        Args:
            request_id: 请求唯一标识
            endpoint: 请求的API端点
            status_code: HTTP状态码
            success: 请求是否成功
            ttft: 首token响应时间(秒)
            ttct: 完整响应时间(秒)
            first_token_time: 首token的时间戳
            complete_time: 完成响应的时间戳
            token_count: 生成的token数量
            response_data: API响应数据
            error: 错误信息
        """
        self.request_id = request_id
        self.endpoint = endpoint
        self.status_code = status_code
        self.success = success
        self.ttft = ttft
        self.ttct = ttct
        self.first_token_time = first_token_time
        self.complete_time = complete_time
        self.token_count = token_count
        self.response_data = response_data or {}
        self.error = error
        self.tokens_per_second = token_count / ttct if ttct > 0 and token_count > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将响应对象转换为字典
        
        Returns:
            包含所有响应数据的字典
        """
        return {
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "success": self.success,
            "ttft": self.ttft,
            "ttct": self.ttct,
            "first_token_time": self.first_token_time,
            "complete_time": self.complete_time,
            "token_count": self.token_count,
            "tokens_per_second": self.tokens_per_second,
            "response_data": self.response_data,
            "error": self.error
        }


class DreaminkFloraClient:
    """DreaminkFlora API客户端类，处理API请求和响应"""
    
    def __init__(self, 
                 base_url: str, 
                 token: str,
                 timeout: int = 6000,
                 max_retries: int = 3,
                 retry_delay: int = 2):
        """
        初始化API客户端
        
        Args:
            base_url: API基础URL
            token: 访问令牌
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
            retry_delay: 重试延迟时间(秒)
        """
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _get_url(self, endpoint: str) -> str:
        """
        构建完整的URL
        
        Args:
            endpoint: API端点
            
        Returns:
            完整的URL字符串
        """
        return urljoin(self.base_url, endpoint)
    
    async def _make_request(self, 
                           method: str, 
                           endpoint: str, 
                           data: Optional[Dict] = None,
                           params: Optional[Dict] = None,
                           stream: bool = False) -> APIResponse:
        """
        发送异步API请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            data: 请求体数据
            params: URL参数
            stream: 是否使用流式响应
            
        Returns:
            APIResponse对象
        """
        request_id = str(uuid.uuid4())
        url = self._get_url(endpoint)
        start_time = time.time()
        first_token_time = 0
        
        # 设置超时
        timeout = ClientTimeout(total=self.timeout)
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
                    if stream:
                        # 流式处理
                        async with session.request(method, url, json=data, params=params) as response:
                            status_code = response.status
                            
                            if status_code >= 200 and status_code < 300:
                                token_count = 0
                                response_data = {"content": ""}
                                
                                async for chunk in response.content.iter_any():
                                    chunk_str = chunk.decode("utf-8")
                                    
                                    # 记录首个token时间
                                    if first_token_time == 0 and chunk_str.strip():
                                        first_token_time = time.time()
                                        
                                    if chunk_str:
                                        response_data["content"] += chunk_str
                                        # 简单估算token数量 (以空格分词的近似值)
                                        token_count += len(chunk_str.split())
                                
                                complete_time = time.time()
                                ttft = first_token_time - start_time if first_token_time > 0 else 0
                                ttct = complete_time - start_time
                                
                                return APIResponse(
                                    request_id=request_id,
                                    endpoint=endpoint,
                                    status_code=status_code,
                                    success=True,
                                    ttft=ttft,
                                    ttct=ttct,
                                    first_token_time=first_token_time,
                                    complete_time=complete_time,
                                    token_count=token_count,
                                    response_data=response_data
                                )
                            else:
                                error_content = await response.text()
                                complete_time = time.time()
                                return APIResponse(
                                    request_id=request_id,
                                    endpoint=endpoint,
                                    status_code=status_code,
                                    success=False,
                                    ttct=complete_time - start_time,
                                    error=f"HTTP Error: {status_code}, {error_content}"
                                )
                    else:
                        # 非流式处理
                        async with session.request(method, url, json=data, params=params) as response:
                            status_code = response.status
                            first_token_time = time.time()  # 非流式请求，首token时间就是响应时间
                            
                            if status_code >= 200 and status_code < 300:
                                response_data = await response.json()
                                complete_time = time.time()
                                
                                # 估算token数量
                                token_count = 0
                                if isinstance(response_data, dict) and "content" in response_data:
                                    content = response_data["content"]
                                    if isinstance(content, str):
                                        token_count = len(content.split())
                                
                                ttft = first_token_time - start_time
                                ttct = complete_time - start_time
                                
                                return APIResponse(
                                    request_id=request_id,
                                    endpoint=endpoint,
                                    status_code=status_code,
                                    success=True,
                                    ttft=ttft,
                                    ttct=ttct,
                                    first_token_time=first_token_time,
                                    complete_time=complete_time,
                                    token_count=token_count,
                                    response_data=response_data
                                )
                            else:
                                error_content = await response.text()
                                complete_time = time.time()
                                return APIResponse(
                                    request_id=request_id,
                                    endpoint=endpoint,
                                    status_code=status_code,
                                    success=False,
                                    ttct=complete_time - start_time,
                                    error=f"HTTP Error: {status_code}, {error_content}"
                                )
            
            except asyncio.TimeoutError:
                error = f"请求超时 (尝试 {attempt+1}/{self.max_retries})"
                logger.warning(error)
                if attempt == self.max_retries - 1:
                    complete_time = time.time()
                    return APIResponse(
                        request_id=request_id,
                        endpoint=endpoint,
                        status_code=0,
                        success=False,
                        ttct=complete_time - start_time,
                        error=f"请求超时: {self.timeout}秒"
                    )
                await asyncio.sleep(self.retry_delay)
            
            except Exception as e:
                error = f"请求错误: {str(e)} (尝试 {attempt+1}/{self.max_retries})"
                logger.error(error)
                if attempt == self.max_retries - 1:
                    complete_time = time.time()
                    return APIResponse(
                        request_id=request_id,
                        endpoint=endpoint,
                        status_code=0,
                        success=False,
                        ttct=complete_time - start_time,
                        error=f"请求错误: {str(e)}"
                    )
                await asyncio.sleep(self.retry_delay)
    
    # API操作方法
    
    async def create_book(self, title: str, description: str) -> APIResponse:
        """
        创建新书籍
        
        Args:
            title: 书籍标题
            description: 书籍描述
            
        Returns:
            APIResponse对象
        """
        endpoint = "/book "
        data = {
            "title": title,
            "description": description
        }
        return await self._make_request("POST", endpoint, data=data)
    
    async def get_book(self, book_id: int) -> APIResponse:
        """
        获取书籍信息
        
        Args:
            book_id: 书籍ID
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}"
        return await self._make_request("GET", endpoint)
    
    async def update_book(self, book_id: int, title: str, description: str) -> APIResponse:
        """
        更新书籍信息
        
        Args:
            book_id: 书籍ID
            title: 新标题
            description: 新描述
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}"
        data = {
            "title": title,
            "description": description
        }
        return await self._make_request("PUT", endpoint, data=data)
    
    async def delete_book(self, book_id: int) -> APIResponse:
        """
        删除书籍
        
        Args:
            book_id: 书籍ID
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}"
        return await self._make_request("DELETE", endpoint)
    
    async def list_books(self, page: int = 1, limit: int = 10) -> APIResponse:
        """
        获取书籍列表
        
        Args:
            page: 页码
            limit: 每页数量
            
        Returns:
            APIResponse对象
        """
        endpoint = "/books"
        params = {
            "page": page,
            "limit": limit
        }
        return await self._make_request("GET", endpoint, params=params)
    
    async def generate_outline(self, book_id: int, prompt: str) -> APIResponse:
        """
        生成书籍章节大纲
        
        Args:
            book_id: 书籍ID
            prompt: 生成提示信息
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/outline"
        data = {
            "prompt": prompt
        }
        return await self._make_request("POST", endpoint, data=data, stream=True)
    
    async def create_chapter(self, 
                           book_id: int, 
                           title: str, 
                           outline: str,
                           content: str = "") -> APIResponse:
        """
        创建书籍章节
        
        Args:
            book_id: 书籍ID
            title: 章节标题
            outline: 章节大纲
            content: 章节内容
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/chapters"
        data = {
            "title": title,
            "outline": outline,
            "content": content
        }
        return await self._make_request("POST", endpoint, data=data)
    
    async def get_chapter(self, book_id: int, chapter_id: int) -> APIResponse:
        """
        获取章节信息
        
        Args:
            book_id: 书籍ID
            chapter_id: 章节ID
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/chapters/{chapter_id}"
        return await self._make_request("GET", endpoint)
    
    async def generate_content(self, 
                             book_id: int, 
                             chapter_id: int, 
                             prompt: str) -> APIResponse:
        """
        生成章节内容
        
        Args:
            book_id: 书籍ID
            chapter_id: 章节ID
            prompt: 生成提示信息
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/chapters/{chapter_id}/generate"
        data = {
            "prompt": prompt
        }
        return await self._make_request("POST", endpoint, data=data, stream=True)
    
    async def continue_content(self,
                              book_id: int,
                              chapter_id: int,
                              current_content: str) -> APIResponse:
        """
        继续生成章节内容
        
        Args:
            book_id: 书籍ID
            chapter_id: 章节ID
            current_content: 当前内容
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/chapters/{chapter_id}/continue"
        data = {
            "content": current_content
        }
        return await self._make_request("POST", endpoint, data=data, stream=True)
    
    async def expand_content(self,
                            book_id: int,
                            chapter_id: int,
                            content: str,
                            instructions: str) -> APIResponse:
        """
        扩展章节内容
        
        Args:
            book_id: 书籍ID
            chapter_id: 章节ID
            content: 当前内容
            instructions: 扩展指令
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/chapters/{chapter_id}/expand"
        data = {
            "content": content,
            "instructions": instructions
        }
        return await self._make_request("POST", endpoint, data=data, stream=True)
    
    async def summarize_content(self,
                               book_id: int,
                               content: str) -> APIResponse:
        """
        总结内容
        
        Args:
            book_id: 书籍ID
            content: 要总结的内容
            
        Returns:
            APIResponse对象
        """
        endpoint = f"/books/{book_id}/summarize"
        data = {
            "content": content
        }
        return await self._make_request("POST", endpoint, data=data, stream=True)
    
    # 健康检查 API
    
    async def health_check(self) -> APIResponse:
        """
        API健康检查
        
        Returns:
            APIResponse对象
        """
        endpoint = "/health"
        return await self._make_request("GET", endpoint)


# 客户端池，用于管理和重用多个API客户端实例
class ClientPool:
    """
    API客户端连接池
    管理多个API客户端实例，支持并发请求
    """
    
    def __init__(self, base_url: str, tokens: List[str], max_clients: int = None):
        """
        初始化客户端池
        
        Args:
            base_url: API基础URL
            tokens: 访问令牌列表
            max_clients: 最大客户端数量，None表示不限制
        """
        self.base_url = base_url
        self.tokens = tokens
        self.max_clients = max_clients or len(tokens)
        self.clients = []
        self.lock = asyncio.Lock()
        self.available = asyncio.Semaphore(min(len(tokens), self.max_clients))
        
        # 初始化客户端池
        for i in range(min(len(tokens), self.max_clients)):
            client = DreaminkFloraClient(base_url, tokens[i])
            self.clients.append(client)
    
    async def get_client(self) -> DreaminkFloraClient:
        """
        获取一个可用的客户端实例
        
        Returns:
            API客户端实例
        """
        await self.available.acquire()
        async with self.lock:
            return self.clients.pop()
    
    async def release_client(self, client: DreaminkFloraClient):
        """
        释放客户端实例回池
        
        Args:
            client: 要释放的客户端实例
        """
        async with self.lock:
            self.clients.append(client)
        self.available.release()
    
    async def execute(self, func_name: str, *args, **kwargs) -> APIResponse:
        """
        执行API客户端方法
        
        Args:
            func_name: 客户端方法名
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            APIResponse对象
        """
        client = await self.get_client()
        try:
            method = getattr(client, func_name)
            result = await method(*args, **kwargs)
            return result
        finally:
            await self.release_client(client) 