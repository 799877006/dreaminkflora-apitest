"""
性能指标收集和分析模块
"""
from typing import Any, Dict, List, Optional, Tuple, Set
import time
import threading
import statistics
from collections import defaultdict, deque
import json
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from api_test_project.models.response_models import PerformanceMetrics, TestResult


class MetricsCollector:
    """
    性能指标收集器类
    用于收集和分析API调用的性能指标
    """
    
    def __init__(self, results_dir: str = "data/results"):
        """
        初始化指标收集器
        
        Args:
            results_dir: 结果保存目录
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用线程锁保护共享数据
        self._lock = threading.RLock()
        
        # 收集的指标
        self._requests: List[Dict[str, Any]] = []
        self._stream_metrics: List[Dict[str, Any]] = []
        self._errors: Dict[str, List[str]] = defaultdict(list)
        
        # 实时指标
        self._active_requests = 0
        self._request_times = deque(maxlen=1000)  # 最近1000个请求的时间
        self._recent_ttfts = deque(maxlen=100)    # 最近100个首token时间
        self._recent_ttcts = deque(maxlen=100)    # 最近100个完整响应时间
        
        # 测试会话指标
        self._session_start_time = time.time()
        self._success_count = 0
        self._failure_count = 0
        self._timeout_count = 0
        self._total_tokens = 0
        
        # 分类指标 - 区分SSE和非SSE接口
        self._sse_endpoints = set()  # 记录SSE接口端点
        self._non_sse_endpoints = set()  # 记录非SSE接口端点
        self._sse_requests = []  # SSE请求指标
        self._non_sse_requests = []  # 非SSE请求指标
        
        # 新增：跟踪已经计数的SSE请求
        self._sse_request_ids: Set[str] = set()  # 记录已完成的SSE请求ID，避免重复计数
        self._total_request_count = 0  # 总请求数（包括SSE和非SSE）
        
        logger.info("指标收集器已初始化")
    
    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        ttft: Optional[float] = None,
        ttct: float = 0.0,
        content_length: int = 0,
        is_stream: bool = False,
        request_id: Optional[str] = None
    ) -> None:
        """
        记录API请求指标
        
        Args:
            endpoint: API端点
            method: HTTP方法
            status_code: 响应状态码
            ttft: 首token返回时间(秒)
            ttct: 完整响应时间(秒)
            content_length: 响应内容长度(字节)
            is_stream: 是否为流式请求
            request_id: 请求唯一标识，用于避免SSE请求重复计数
        """
        with self._lock:
            timestamp = time.time()
            
            # 生成一个请求ID，如果没有提供
            if request_id is None:
                request_id = f"{endpoint}-{timestamp}"
            
            request_data = {
                "timestamp": timestamp,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "ttft": ttft,
                "ttct": ttct,
                "content_length": content_length,
                "is_stream": is_stream,
                "request_id": request_id
            }
            
            self._requests.append(request_data)
            self._request_times.append(timestamp)
            self._total_request_count += 1  # 增加总请求计数
            
            if ttft is not None:
                self._recent_ttfts.append(ttft)
            
            self._recent_ttcts.append(ttct)
            
            # 按SSE和非SSE分类记录
            if is_stream:
                self._sse_endpoints.add(endpoint)
                self._sse_requests.append(request_data)
                # 对于流式请求，不在此时计数成功/失败，而是等待流结束时计数
            else:
                self._non_sse_endpoints.add(endpoint)
                self._non_sse_requests.append(request_data)
                # 对于非流式请求，直接在此计数成功/失败
                if 200 <= status_code < 300:
                    self._success_count += 1
                else:
                    self._failure_count += 1
    
    def record_stream_completion(
        self,
        endpoint: str,
        status_code: int,
        ttft: float,
        ttct: float,
        token_count: int,
        request_id: Optional[str] = None
    ) -> None:
        """
        记录流式请求完成指标
        
        Args:
            endpoint: API端点
            status_code: 响应状态码
            ttft: 首token返回时间(秒)
            ttct: 完整响应时间(秒)
            token_count: 生成的token数
            request_id: 请求唯一标识，用于避免SSE请求重复计数
        """
        with self._lock:
            timestamp = time.time()
            
            # 生成一个请求ID，如果没有提供
            if request_id is None:
                request_id = f"{endpoint}-{timestamp}"
            
            tokens_per_second = token_count / ttct if ttct > 0 else 0
            
            stream_data = {
                "timestamp": timestamp,
                "endpoint": endpoint,
                "status_code": status_code,
                "ttft": ttft,
                "ttct": ttct,
                "token_count": token_count,
                "tokens_per_second": tokens_per_second,
                "request_id": request_id
            }
            
            self._stream_metrics.append(stream_data)
            self._recent_ttfts.append(ttft)
            self._recent_ttcts.append(ttct)
            self._total_tokens += token_count
            
            # 记录为SSE请求
            self._sse_endpoints.add(endpoint)
            self._sse_requests.append(stream_data)
            
            # 更新统计数据 - 只有当请求ID还未被计数时才计数
            if request_id not in self._sse_request_ids:
                self._sse_request_ids.add(request_id)
                
                # 仅在流式请求完成时才计数成功/失败
                if 200 <= status_code < 300:
                    self._success_count += 1
                else:
                    self._failure_count += 1
                
                logger.debug(f"SSE请求完成：{request_id}，状态码：{status_code}")
    
    def record_error(self, error_type: str, error_message: str, endpoint: str) -> None:
        """
        记录错误
        
        Args:
            error_type: 错误类型 (timeout, network, general等)
            error_message: 错误消息
            endpoint: API端点
        """
        with self._lock:
            if error_type == "timeout":
                self._timeout_count += 1
            
            self._failure_count += 1
            error_data = {
                "timestamp": time.time(),
                "message": error_message,
                "endpoint": endpoint
            }
            self._errors[error_type].append(error_data)
    
    def get_success_rate(self) -> float:
        """
        获取请求成功率
        
        Returns:
            成功率(0.0-1.0)
        """
        with self._lock:
            total = self._success_count + self._failure_count
            if total == 0:
                return 0.0
            return self._success_count / total
    
    def get_current_rps(self) -> float:
        """
        获取当前每秒请求数
        
        Returns:
            每秒请求数
        """
        with self._lock:
            if len(self._request_times) < 2:
                return 0.0
            
            # 计算最近请求的时间范围
            now = time.time()
            # 获取最近60秒的请求
            recent_requests = [t for t in self._request_times if now - t <= 60]
            
            if not recent_requests:
                return 0.0
            
            time_span = now - min(recent_requests)
            if time_span <= 0:
                return 0.0
            
            return len(recent_requests) / time_span
    
    def get_recent_latencies(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        获取最近的延迟统计
        
        Returns:
            (TTFT统计, TTCT统计)
        """
        with self._lock:
            ttft_stats = {}
            ttct_stats = {}
            
            if self._recent_ttfts:
                ttft_array = np.array(self._recent_ttfts)
                ttft_stats = {
                    "avg": float(np.mean(ttft_array)),
                    "median": float(np.median(ttft_array)),
                    "p90": float(np.percentile(ttft_array, 90)),
                    "p95": float(np.percentile(ttft_array, 95)),
                    "min": float(np.min(ttft_array)),
                    "max": float(np.max(ttft_array))
                }
            
            if self._recent_ttcts:
                ttct_array = np.array(self._recent_ttcts)
                ttct_stats = {
                    "avg": float(np.mean(ttct_array)),
                    "median": float(np.median(ttct_array)),
                    "p90": float(np.percentile(ttct_array, 90)),
                    "p95": float(np.percentile(ttct_array, 95)),
                    "min": float(np.min(ttct_array)),
                    "max": float(np.max(ttct_array))
                }
            
            return ttft_stats, ttct_stats
    
    def get_error_summary(self) -> Dict[str, int]:
        """
        获取错误统计摘要
        
        Returns:
            按错误类型统计的数量
        """
        with self._lock:
            return {error_type: len(errors) for error_type, errors in self._errors.items()}
    
    def get_session_metrics(self, concurrent_users: int) -> TestResult:
        """
        获取当前测试会话的指标
        
        Args:
            concurrent_users: 当前并发用户数
            
        Returns:
            测试结果对象
        """
        with self._lock:
            ttft_stats, ttct_stats = self.get_recent_latencies()
            error_summary = self.get_error_summary()
            
            # 计算每秒token数
            total_ttct = sum(self._recent_ttcts) if self._recent_ttcts else 0
            avg_tokens_per_second = self._total_tokens / total_ttct if total_ttct > 0 else 0
            
            return TestResult(
                timestamp=time.time(),
                concurrent_users=concurrent_users,
                success_count=self._success_count,
                failure_count=self._failure_count,
                total_requests=self._total_request_count,  # 添加总请求数
                timeout_count=self._timeout_count,
                avg_ttft=ttft_stats.get("avg"),
                avg_ttct=ttct_stats.get("avg"),
                p50_ttft=ttft_stats.get("median"),
                p90_ttft=ttft_stats.get("p90"),
                p95_ttft=ttft_stats.get("p95"),
                p50_ttct=ttct_stats.get("median"),
                p90_ttct=ttct_stats.get("p90"),
                p95_ttct=ttct_stats.get("p95"),
                total_tokens=self._total_tokens,
                avg_tokens_per_second=avg_tokens_per_second,
                error_types=error_summary
            )
    
    def save_results(self, test_name: str, concurrent_users: int) -> str:
        """
        保存测试结果到文件
        
        Args:
            test_name: 测试名称
            concurrent_users: 并发用户数
            
        Returns:
            保存的文件路径
        """
        with self._lock:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            result_dir = self.results_dir / f"{test_name}_{concurrent_users}users_{timestamp}"
            result_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存请求指标
            if self._requests:
                requests_df = pd.DataFrame(self._requests)
                requests_path = result_dir / "requests.csv"
                requests_df.to_csv(requests_path, index=False)
            
            # 保存流式指标
            if self._stream_metrics:
                stream_df = pd.DataFrame(self._stream_metrics)
                stream_path = result_dir / "stream_metrics.csv"
                stream_df.to_csv(stream_path, index=False)
            
            # 保存错误信息
            if self._errors:
                errors_path = result_dir / "errors.json"
                with open(errors_path, 'w', encoding='utf-8') as f:
                    json.dump(self._errors, f, ensure_ascii=False, indent=2)
            
            # 保存测试摘要
            summary = self.get_session_metrics(concurrent_users)
            summary_path = result_dir / "summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json_data = summary.model_dump()
                f.write(json.dumps(json_data, indent=2, ensure_ascii=False))
            
            # 生成可视化报告并保存
            self._generate_visualizations(result_dir)
            
            logger.info(f"测试结果已保存到 {result_dir}")
            return str(result_dir)
    
    def _generate_visualizations(self, result_dir: Path) -> None:
        """
        生成可视化图表并保存
        
        Args:
            result_dir: 结果保存目录
        """
        # 创建可视化保存目录
        vis_dir = result_dir / "visualizations"
        vis_dir.mkdir(exist_ok=True)
        
        # 1. 生成SSE接口的指标图表
        self._generate_sse_visualizations(vis_dir)
        
        # 2. 生成非SSE接口的指标图表
        self._generate_non_sse_visualizations(vis_dir)
        
        # 3. 生成整体性能指标图表
        self._generate_overall_visualizations(vis_dir)
        
        # 4. 生成汇总报告HTML
        self._generate_report_html(result_dir, vis_dir)
        
        logger.info(f"可视化报告已生成到 {vis_dir}")
    
    def _generate_sse_visualizations(self, vis_dir: Path) -> None:
        """
        生成SSE接口指标可视化
        
        Args:
            vis_dir: 可视化保存目录
        """
        # 如果没有SSE请求数据，则跳过
        if not self._sse_requests:
            logger.info("没有SSE请求数据，跳过SSE接口可视化")
            return
        
        # 转换为DataFrame方便处理
        df = pd.DataFrame(self._sse_requests)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # 1. TPS (Tokens Per Second) 曲线图
        if 'tokens_per_second' in df.columns:
            fig = px.line(
                df, 
                x='timestamp', 
                y='tokens_per_second',
                title='大模型接口 - 令牌生成速率 (TPS)',
                labels={'timestamp': '时间', 'tokens_per_second': '每秒令牌数 (TPS)'}
            )
            fig.update_layout(height=500, width=800)
            fig.write_html(str(vis_dir / "sse_tps.html"))
            fig.write_image(str(vis_dir / "sse_tps.png"))
        
        # 2. TTFT 和 TTCT 分布
        if all(col in df.columns for col in ['ttft', 'ttct']):
            fig = make_subplots(rows=1, cols=2, subplot_titles=("首令牌响应时间 (TTFT)", "完整响应时间 (TTCT)"))
            
            fig.add_trace(go.Histogram(x=df['ttft'], name='TTFT'), row=1, col=1)
            fig.add_trace(go.Histogram(x=df['ttct'], name='TTCT'), row=1, col=2)
            
            fig.update_layout(
                title_text='大模型接口 - 响应时间分布',
                height=500, 
                width=1000
            )
            fig.write_html(str(vis_dir / "sse_latency_distribution.html"))
            fig.write_image(str(vis_dir / "sse_latency_distribution.png"))
        
        # 3. 令牌生成数量分布
        if 'token_count' in df.columns:
            fig = px.histogram(
                df, 
                x='token_count',
                title='大模型接口 - 令牌生成数量分布',
                labels={'token_count': '生成令牌数'}
            )
            fig.update_layout(height=500, width=800)
            fig.write_html(str(vis_dir / "sse_token_count.html"))
            fig.write_image(str(vis_dir / "sse_token_count.png"))
        
        # 4. 随时间变化的响应时间
        if all(col in df.columns for col in ['timestamp', 'ttft', 'ttct']):
            fig = make_subplots(rows=1, cols=2, subplot_titles=("TTFT随时间变化", "TTCT随时间变化"))
            
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ttft'], mode='markers', name='TTFT'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ttct'], mode='markers', name='TTCT'), row=1, col=2)
            
            fig.update_layout(
                title_text='大模型接口 - 响应时间随时间变化',
                height=500, 
                width=1000
            )
            fig.write_html(str(vis_dir / "sse_latency_over_time.html"))
            fig.write_image(str(vis_dir / "sse_latency_over_time.png"))
        
        # 5. 端点性能对比
        if 'endpoint' in df.columns:
            # 按端点分组计算平均指标
            endpoint_metrics = df.groupby('endpoint').agg({
                'ttft': 'mean',
                'ttct': 'mean',
                'tokens_per_second': 'mean' if 'tokens_per_second' in df.columns else None
            }).reset_index()
            
            if not endpoint_metrics.empty and len(endpoint_metrics) > 1:
                metrics_to_plot = ['ttft', 'ttct']
                if 'tokens_per_second' in endpoint_metrics.columns:
                    metrics_to_plot.append('tokens_per_second')
                
                for metric in metrics_to_plot:
                    if metric in endpoint_metrics.columns:
                        metric_name = {
                            'ttft': '首令牌响应时间 (秒)',
                            'ttct': '完整响应时间 (秒)',
                            'tokens_per_second': '每秒令牌数 (TPS)'
                        }.get(metric, metric)
                        
                        fig = px.bar(
                            endpoint_metrics, 
                            x='endpoint', 
                            y=metric,
                            title=f'大模型接口 - 各端点{metric_name}对比',
                            labels={'endpoint': '端点', metric: metric_name}
                        )
                        fig.update_layout(height=500, width=800)
                        fig.write_html(str(vis_dir / f"sse_endpoint_{metric}.html"))
                        fig.write_image(str(vis_dir / f"sse_endpoint_{metric}.png"))
    
    def _generate_non_sse_visualizations(self, vis_dir: Path) -> None:
        """
        生成非SSE接口指标可视化
        
        Args:
            vis_dir: 可视化保存目录
        """
        # 如果没有非SSE请求数据，则跳过
        if not self._non_sse_requests:
            logger.info("没有非SSE请求数据，跳过非SSE接口可视化")
            return
        
        # 转换为DataFrame方便处理
        df = pd.DataFrame(self._non_sse_requests)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # 1. QPS (Queries Per Second) 计算和可视化
        # 按分钟聚合计算QPS
        df['minute'] = df['timestamp'].dt.floor('1min')
        qps_df = df.groupby('minute').size().reset_index()
        qps_df.columns = ['minute', 'count']
        qps_df['qps'] = qps_df['count'] / 60  # 转换为每秒请求数
        
        fig = px.line(
            qps_df, 
            x='minute', 
            y='qps',
            title='非SSE接口 - 每秒请求数 (QPS)',
            labels={'minute': '时间', 'qps': 'QPS'}
        )
        fig.update_layout(height=500, width=800)
        fig.write_html(str(vis_dir / "non_sse_qps.html"))
        fig.write_image(str(vis_dir / "non_sse_qps.png"))
        
        # 2. 延迟分布
        if 'ttct' in df.columns:
            fig = px.histogram(
                df, 
                x='ttct',
                title='非SSE接口 - 响应时间分布',
                labels={'ttct': '响应时间 (秒)'}
            )
            fig.update_layout(height=500, width=800)
            fig.write_html(str(vis_dir / "non_sse_latency_distribution.html"))
            fig.write_image(str(vis_dir / "non_sse_latency_distribution.png"))
        
        # 3. 端点性能对比
        if 'endpoint' in df.columns and 'ttct' in df.columns:
            # 按端点分组计算平均延迟
            endpoint_latency = df.groupby('endpoint')['ttct'].mean().reset_index()
            
            if not endpoint_latency.empty and len(endpoint_latency) > 1:
                fig = px.bar(
                    endpoint_latency, 
                    x='endpoint', 
                    y='ttct',
                    title='非SSE接口 - 各端点平均响应时间',
                    labels={'endpoint': '端点', 'ttct': '平均响应时间 (秒)'}
                )
                fig.update_layout(height=500, width=800)
                fig.write_html(str(vis_dir / "non_sse_endpoint_latency.html"))
                fig.write_image(str(vis_dir / "non_sse_endpoint_latency.png"))
        
        # 4. 成功率计算和可视化
        if 'status_code' in df.columns:
            df['success'] = df['status_code'].apply(lambda x: 200 <= x < 300)
            success_rate = df['success'].mean() * 100
            
            # 创建成功率饼图
            fig = go.Figure(data=[go.Pie(
                labels=['成功', '失败'],
                values=[df['success'].sum(), len(df) - df['success'].sum()],
                hole=.3
            )])
            fig.update_layout(
                title_text=f'非SSE接口 - 请求成功率: {success_rate:.2f}%',
                height=500, 
                width=800
            )
            fig.write_html(str(vis_dir / "non_sse_success_rate.html"))
            fig.write_image(str(vis_dir / "non_sse_success_rate.png"))
            
            # 按端点计算成功率
            if 'endpoint' in df.columns:
                endpoint_success = df.groupby('endpoint')['success'].mean().reset_index()
                endpoint_success['success_rate'] = endpoint_success['success'] * 100
                
                if not endpoint_success.empty and len(endpoint_success) > 1:
                    fig = px.bar(
                        endpoint_success, 
                        x='endpoint', 
                        y='success_rate',
                        title='非SSE接口 - 各端点成功率',
                        labels={'endpoint': '端点', 'success_rate': '成功率 (%)'}
                    )
                    fig.update_layout(height=500, width=800)
                    fig.write_html(str(vis_dir / "non_sse_endpoint_success_rate.html"))
                    fig.write_image(str(vis_dir / "non_sse_endpoint_success_rate.png"))
    
    def _generate_overall_visualizations(self, vis_dir: Path) -> None:
        """
        生成整体性能指标可视化
        
        Args:
            vis_dir: 可视化保存目录
        """
        # 如果没有请求数据，则跳过
        if not self._requests:
            logger.info("没有请求数据，跳过整体性能可视化")
            return
        
        # 转换为DataFrame方便处理
        df = pd.DataFrame(self._requests)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # 1. SSE与非SSE请求占比饼图
        sse_count = sum(1 for req in self._requests if req.get('is_stream', False))
        non_sse_count = len(self._requests) - sse_count
        
        fig = go.Figure(data=[go.Pie(
            labels=['SSE (大模型) 请求', '非SSE请求'],
            values=[sse_count, non_sse_count],
            hole=.3
        )])
        fig.update_layout(
            title_text='请求类型分布',
            height=500, 
            width=800
        )
        fig.write_html(str(vis_dir / "request_type_distribution.html"))
        fig.write_image(str(vis_dir / "request_type_distribution.png"))
        
        # 2. 错误类型分布
        if self._errors:
            error_counts = {error_type: len(errors) for error_type, errors in self._errors.items()}
            error_df = pd.DataFrame([
                {'error_type': error_type, 'count': count}
                for error_type, count in error_counts.items()
            ])
            
            if not error_df.empty:
                fig = px.pie(
                    error_df, 
                    values='count', 
                    names='error_type',
                    title='错误类型分布'
                )
                fig.update_layout(height=500, width=800)
                fig.write_html(str(vis_dir / "error_distribution.html"))
                fig.write_image(str(vis_dir / "error_distribution.png"))
        
        # 3. 测试摘要信息图表
        # 创建一个包含测试摘要信息的图表
        ttft_stats, ttct_stats = self.get_recent_latencies()
        
        # 获取测试持续时间
        test_duration = time.time() - self._session_start_time
        
        # 获取准确的成功率
        success_rate = self.get_success_rate() * 100
        
        # 准备摘要数据
        summary_data = {
            "指标": [
                "总请求数", 
                "成功率 (%)", 
                "测试持续时间 (秒)", 
                "平均TPS", 
                "平均TTFT (秒)", 
                "平均TTCT (秒)"
            ],
            "值": [
                self._total_request_count,
                success_rate,
                test_duration,
                self._total_tokens / max(1, test_duration),
                ttft_stats.get("avg", 0),
                ttct_stats.get("avg", 0)
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        
        fig = px.bar(
            summary_df, 
            x="指标", 
            y="值",
            title="测试摘要信息",
            text_auto='.2f'
        )
        fig.update_layout(height=600, width=1000)
        fig.write_html(str(vis_dir / "test_summary.html"))
        fig.write_image(str(vis_dir / "test_summary.png"))
    
    def _generate_report_html(self, result_dir: Path, vis_dir: Path) -> None:
        """
        生成HTML报告
        
        Args:
            result_dir: 结果目录
            vis_dir: 可视化目录
        """
        # 创建HTML报告
        report_path = result_dir / "performance_report.html"
        
        # 获取所有生成的图片
        vis_files = list(vis_dir.glob("*.html"))
        
        # 计算准确的成功率
        success_rate = self.get_success_rate() * 100
        
        # 构建HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>API性能测试报告</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: #fff;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }}
                h1, h2, h3 {{
                    color: #333;
                }}
                .section {{
                    margin-bottom: 30px;
                    padding: 20px;
                    background-color: #f9f9f9;
                    border-radius: 5px;
                }}
                .chart-container {{
                    margin-top: 20px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    overflow: hidden;
                }}
                .metrics-summary {{
                    display: flex;
                    flex-wrap: wrap;
                    margin: 0 -10px;
                }}
                .metric-card {{
                    background-color: #fff;
                    border-radius: 5px;
                    box-shadow: 0 0 5px rgba(0,0,0,0.1);
                    margin: 10px;
                    padding: 15px;
                    flex: 1 0 200px;
                    max-width: calc(25% - 20px);
                    text-align: center;
                }}
                .metric-card .value {{
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 5px;
                    color: #2c7be5;
                }}
                .metric-card .label {{
                    color: #6e84a3;
                    font-size: 14px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                table, th, td {{
                    border: 1px solid #ddd;
                }}
                th, td {{
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                iframe {{
                    width: 100%;
                    height: 500px;
                    border: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>API性能测试报告</h1>
                <div class="section">
                    <h2>测试摘要</h2>
                    <div class="metrics-summary">
                        <div class="metric-card">
                            <div class="value">{self._total_request_count}</div>
                            <div class="label">总请求数</div>
                        </div>
                        <div class="metric-card">
                            <div class="value">{success_rate:.2f}%</div>
                            <div class="label">成功率</div>
                        </div>
                        <div class="metric-card">
                            <div class="value">{time.time() - self._session_start_time:.2f}s</div>
                            <div class="label">测试持续时间</div>
                        </div>
                        <div class="metric-card">
                            <div class="value">{self._total_tokens / max(1, time.time() - self._session_start_time):.2f}</div>
                            <div class="label">平均TPS</div>
                        </div>
                    </div>
                </div>
        """
        
        # 添加SSE指标部分
        if self._sse_requests:
            html_content += """
                <div class="section">
                    <h2>大模型接口(SSE)指标</h2>
            """
            
            # 尝试添加SSE图表
            sse_charts = [f for f in vis_files if "sse_" in f.name]
            for chart_file in sse_charts:
                chart_name = chart_file.stem.replace("sse_", "").replace("_", " ").title()
                html_content += f"""
                    <h3>{chart_name}</h3>
                    <div class="chart-container">
                        <iframe src="visualizations/{chart_file.name}"></iframe>
                    </div>
                """
            
            html_content += """
                </div>
            """
        
        # 添加非SSE指标部分
        if self._non_sse_requests:
            html_content += """
                <div class="section">
                    <h2>普通接口(非SSE)指标</h2>
            """
            
            # 尝试添加非SSE图表
            non_sse_charts = [f for f in vis_files if "non_sse_" in f.name]
            for chart_file in non_sse_charts:
                chart_name = chart_file.stem.replace("non_sse_", "").replace("_", " ").title()
                html_content += f"""
                    <h3>{chart_name}</h3>
                    <div class="chart-container">
                        <iframe src="visualizations/{chart_file.name}"></iframe>
                    </div>
                """
            
            html_content += """
                </div>
            """
        
        # 添加整体指标部分
        overall_charts = [f for f in vis_files if not ("sse_" in f.name or "non_sse_" in f.name)]
        if overall_charts:
            html_content += """
                <div class="section">
                    <h2>整体性能指标</h2>
            """
            
            for chart_file in overall_charts:
                chart_name = chart_file.stem.replace("_", " ").title()
                html_content += f"""
                    <h3>{chart_name}</h3>
                    <div class="chart-container">
                        <iframe src="visualizations/{chart_file.name}"></iframe>
                    </div>
                """
            
            html_content += """
                </div>
            """
        
        # 结束HTML
        html_content += """
            </div>
        </body>
        </html>
        """
        
        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已生成: {report_path}")
    
    def reset(self) -> None:
        """重置所有指标"""
        with self._lock:
            self._requests = []
            self._stream_metrics = []
            self._errors = defaultdict(list)
            self._request_times.clear()
            self._recent_ttfts.clear()
            self._recent_ttcts.clear()
            self._session_start_time = time.time()
            self._success_count = 0
            self._failure_count = 0
            self._timeout_count = 0
            self._total_tokens = 0
            self._sse_endpoints = set()
            self._non_sse_endpoints = set()
            self._sse_requests = []
            self._non_sse_requests = []
            self._sse_request_ids.clear()
            self._total_request_count = 0
            logger.info("指标收集器已重置") 