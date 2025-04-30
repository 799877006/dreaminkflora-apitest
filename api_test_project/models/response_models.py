"""
API响应模型定义
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """错误响应模型"""
    status_code: int = Field(..., description="HTTP状态码")
    message: str = Field(..., description="错误消息")
    error: Optional[Any] = Field(None, description="详细错误信息")


class ApiResponse(BaseModel):
    """API响应模型"""
    success: bool = Field(..., description="是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    error: Optional[ErrorResponse] = Field(None, description="错误信息")


class TokenStreamEvent(BaseModel):
    """流式令牌事件模型"""
    event_type: str = Field(..., description="事件类型: token, finish, error等")
    data: Optional[Dict[str, Any]] = Field(None, description="事件数据")


class BookResponse(BaseModel):
    """书籍响应模型"""
    book_id: int = Field(..., description="书籍ID")
    book_name: str = Field(..., description="书籍名称")
    chapters: List[Dict[str, Any]] = Field(default_factory=list, description="章节列表")


class ChapterResponse(BaseModel):
    """章节响应模型"""
    chapter_id: int = Field(..., description="章节ID")
    book_id: int = Field(..., description="书籍ID")
    outline: Optional[str] = Field(None, description="章节大纲")
    background: Optional[str] = Field(None, description="前文梗概")
    chapter_word_count: int = Field(0, description="章节字数")
    outline_word_count: Optional[int] = Field(None, description="大纲字数")
    chapter_order: int = Field(..., description="章节顺序")
    update_time: str = Field(..., description="更新时间")


class PerformanceMetrics(BaseModel):
    """性能指标模型"""
    ttft: float = Field(..., description="首token返回时间(秒)")
    ttct: float = Field(..., description="完整响应时间(秒)")
    token_count: Optional[int] = Field(None, description="生成的token数量")
    tokens_per_second: Optional[float] = Field(None, description="每秒token数")
    success: bool = Field(True, description="请求是否成功")
    endpoint: str = Field(..., description="请求的API端点")
    error: Optional[str] = Field(None, description="错误信息")


class TestResult(BaseModel):
    """测试结果模型"""
    timestamp: float = Field(..., description="测试时间戳")
    concurrent_users: int = Field(..., description="并发用户数")
    success_count: int = Field(0, description="成功请求数")
    failure_count: int = Field(0, description="失败请求数")
    total_requests: int = Field(0, description="总请求数")
    timeout_count: int = Field(0, description="超时请求数")
    avg_ttft: Optional[float] = Field(None, description="平均首token返回时间")
    avg_ttct: Optional[float] = Field(None, description="平均完整响应时间")
    p50_ttft: Optional[float] = Field(None, description="首token返回时间中位数")
    p90_ttft: Optional[float] = Field(None, description="首token返回时间90百分位")
    p95_ttft: Optional[float] = Field(None, description="首token返回时间95百分位")
    p50_ttct: Optional[float] = Field(None, description="完整响应时间中位数")
    p90_ttct: Optional[float] = Field(None, description="完整响应时间90百分位")
    p95_ttct: Optional[float] = Field(None, description="完整响应时间95百分位")
    total_tokens: int = Field(0, description="生成的总token数")
    avg_tokens_per_second: Optional[float] = Field(None, description="平均每秒token数")
    error_types: Dict[str, int] = Field(default_factory=dict, description="错误类型统计")
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.success_count + self.failure_count == 0:
            return 0.0
        return self.success_count / (self.success_count + self.failure_count) 