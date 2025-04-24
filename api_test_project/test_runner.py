"""
测试运行器模块 - 提供统一的测试管理和执行能力
"""
import asyncio
import logging
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import pandas as pd

from api_test_project.api_client.client import APIClient
from api_test_project.metrics.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

class TestRunner:
    """测试运行器类，用于管理和执行各种API性能测试"""
    
    def __init__(
        self, 
        base_url: str = "https://api.dreaminkflora.ai", 
        tokens_file: str = "access_tokens.csv",
        results_dir: str = "results",
        log_dir: str = "logs"
    ):
        """
        初始化测试运行器
        
        Args:
            base_url: API基础URL
            tokens_file: 访问令牌文件路径
            results_dir: 结果保存目录
            log_dir: 日志保存目录
        """
        self.base_url = base_url
        self.tokens_file = tokens_file
        self.results_dir = Path(results_dir)
        self.log_dir = Path(log_dir)
        
        # 确保结果和日志目录存在
        self.results_dir.mkdir(exist_ok=True, parents=True)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # 当前测试进程
        self.current_test_process: Optional[subprocess.Popen] = None
        self.metrics_collector: Optional[MetricsCollector] = None
        self.test_start_time: Optional[float] = None
        self.test_end_time: Optional[float] = None
        
        logger.info(f"测试运行器初始化完成，API基础URL: {base_url}")
    
    async def run_basic_test(
        self, 
        test_type: str,
        concurrent_users: int,
        duration_seconds: int,
        workflow_type: str = "basic",
        custom_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        运行基本性能测试
        
        Args:
            test_type: 测试类型，例如"response_time"、"throughput"
            concurrent_users: 并发用户数
            duration_seconds: 测试持续时间（秒）
            workflow_type: 工作流类型，例如"basic"、"advanced"
            custom_params: 自定义参数
            
        Returns:
            测试结果字典
        """
        logger.info(f"开始执行基本测试: {test_type}, 并发用户: {concurrent_users}, 持续时间: {duration_seconds}秒")
        
        if self.current_test_process:
            logger.warning("已有测试正在运行，请先停止当前测试")
            return {"error": "已有测试正在运行"}
        
        # 开始记录指标
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_path = self.results_dir / f"basic_test_{test_type}_{timestamp}"
        result_path.mkdir(exist_ok=True)
        
        # 初始化指标收集器
        self.metrics_collector = MetricsCollector(
            output_dir=str(result_path),
            test_name=f"{test_type}_{workflow_type}"
        )
        
        # 记录测试开始时间
        self.test_start_time = time.time()
        
        # 创建API客户端
        client = APIClient(base_url=self.base_url, tokens_file=self.tokens_file)
        
        # 测试任务列表
        tasks = []
        
        # 根据测试类型和工作流创建测试任务
        for i in range(concurrent_users):
            if workflow_type == "basic":
                tasks.append(self._run_basic_workflow(client, i, self.metrics_collector))
            elif workflow_type == "advanced":
                tasks.append(self._run_advanced_workflow(client, i, self.metrics_collector))
            else:
                logger.error(f"不支持的工作流类型: {workflow_type}")
                return {"error": f"不支持的工作流类型: {workflow_type}"}
        
        # 设置测试超时
        try:
            # 执行所有任务，设置总超时
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=duration_seconds)
        except asyncio.TimeoutError:
            logger.info(f"测试达到预设时间 {duration_seconds}秒，正常结束")
        except Exception as e:
            logger.error(f"测试执行过程中发生错误: {str(e)}")
        finally:
            # 记录测试结束时间
            self.test_end_time = time.time()
            
            # 停止指标收集
            if self.metrics_collector:
                self.metrics_collector.stop()
                
            # 生成测试报告
            test_duration = self.test_end_time - self.test_start_time
            report = {
                "test_type": test_type,
                "workflow_type": workflow_type,
                "concurrent_users": concurrent_users,
                "planned_duration": duration_seconds,
                "actual_duration": test_duration,
                "result_path": str(result_path),
                "timestamp": timestamp,
                "metrics_summary": self.metrics_collector.get_summary() if self.metrics_collector else {}
            }
            
            # 保存报告
            report_file = result_path / "report.json"
            import json
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
                
            logger.info(f"测试完成，结果保存在: {report_file}")
            return report
            
    async def _run_basic_workflow(self, client: APIClient, user_id: int, metrics_collector: MetricsCollector):
        """基本工作流测试实现"""
        logger.debug(f"用户 {user_id} 开始执行基本工作流")
        try:
            # 1. 用户认证
            logger.info(f"用户 {user_id} 正在进行认证...")
            await client.authenticate(user_id=user_id)
            logger.info(f"用户 {user_id} 认证成功")
            
            # 2. 创建新书
            book_data = {
                "title": f"测试书籍 {user_id}",
                "genre": "科幻小说",
                "description": "这是一本用于API测试的书籍"
            }
            logger.info(f"用户 {user_id} 正在创建新书: {book_data['title']}...")
            book_response = await client.create_book(book_data)
            book_id = book_response.get("id")
            logger.info(f"用户 {user_id} 成功创建书籍，标题: {book_data['title']}, ID: {book_id}")
            
            # 3. 生成章节大纲
            logger.info(f"用户 {user_id} 正在为书籍 {book_id} 生成章节大纲...")
            outline_response = await client.generate_outline(book_id)
            chapter_count = len(outline_response.get("chapters", []))
            logger.info(f"用户 {user_id} 成功生成书籍 {book_id} 的大纲，包含 {chapter_count} 个章节")
            
            # 4. 生成内容
            logger.info(f"用户 {user_id} 正在为书籍 {book_id} 的第1章生成内容...")
            content_response = await client.generate_content(
                book_id=book_id,
                chapter_id=1,
                prompt="请基于大纲生成第一章内容"
            )
            content_length = len(content_response.get("content", ""))
            logger.info(f"用户 {user_id} 成功生成书籍 {book_id} 第1章内容，长度: {content_length} 字符")
            
            # 5. 继续写作
            logger.info(f"用户 {user_id} 正在为书籍 {book_id} 的第1章继续写作...")
            continuation_response = await client.continue_content(
                book_id=book_id,
                chapter_id=1
            )
            new_content_length = len(continuation_response.get("content", ""))
            logger.info(f"用户 {user_id} 成功继续书籍 {book_id} 第1章内容，新增: {new_content_length} 字符")
            
            # 记录完成情况
            metrics_collector.record_workflow_completion(user_id, True)
            logger.info(f"用户 {user_id} 成功完成基本工作流，完成了全部 5 个步骤")
            
        except Exception as e:
            # 记录错误
            error_msg = str(e)
            metrics_collector.record_workflow_error(user_id, error_msg)
            logger.error(f"用户 {user_id} 执行基本工作流失败: {error_msg}")
    
    async def _run_advanced_workflow(self, client: APIClient, user_id: int, metrics_collector: MetricsCollector):
        """高级工作流测试实现"""
        logger.debug(f"用户 {user_id} 开始执行高级工作流")
        try:
            # 1. 用户认证
            logger.info(f"用户 {user_id} 正在进行认证...")
            await client.authenticate(user_id=user_id)
            logger.info(f"用户 {user_id} 认证成功")
            
            # 2. 并行多书操作
            book_ids = []
            logger.info(f"用户 {user_id} 开始并行创建3本书籍...")
            for i in range(3):  # 创建3本书
                book_data = {
                    "title": f"测试书籍 {user_id}-{i}",
                    "genre": "奇幻小说",
                    "description": f"这是用户{user_id}的第{i}本测试书籍"
                }
                logger.info(f"用户 {user_id} 正在创建书籍: {book_data['title']}...")
                book_response = await client.create_book(book_data)
                book_id = book_response.get("id")
                book_ids.append(book_id)
                logger.info(f"用户 {user_id} 成功创建书籍，标题: {book_data['title']}, ID: {book_id}")
            
            logger.info(f"用户 {user_id} 成功创建了 {len(book_ids)} 本书")
            
            # 3. 为每本书生成大纲和内容
            tasks = []
            logger.info(f"用户 {user_id} 正在并行为 {len(book_ids)} 本书生成大纲...")
            for book_id in book_ids:
                # 生成大纲
                tasks.append(client.generate_outline(book_id))
            
            # 等待所有大纲生成完成
            outlines = await asyncio.gather(*tasks)
            logger.info(f"用户 {user_id} 成功为 {len(book_ids)} 本书生成大纲")
            
            # 4. 长上下文维护测试
            long_context_book_id = book_ids[0]
            chapter_content = ""
            
            logger.info(f"用户 {user_id} 开始长上下文测试，选择书籍ID: {long_context_book_id}")
            
            # 连续生成5个章节
            for chapter_id in range(1, 6):
                logger.info(f"用户 {user_id} 正在为书籍 {long_context_book_id} 生成第 {chapter_id} 章内容...")
                content_response = await client.generate_content(
                    book_id=long_context_book_id,
                    chapter_id=chapter_id,
                    prompt=f"请生成第{chapter_id}章的内容，继续前面的故事情节"
                )
                content = content_response.get("content", "")
                chapter_content += content
                logger.info(f"用户 {user_id} 成功生成书籍 {long_context_book_id} 第 {chapter_id} 章内容，长度: {len(content)} 字符")
            
            logger.info(f"用户 {user_id} 已完成连续5章内容生成，总字数: {len(chapter_content)}")
            
            # 5. 中断和恢复测试
            # 模拟中断
            logger.info(f"用户 {user_id} 模拟中断写作过程...")
            time.sleep(1)
            # 恢复写作
            logger.info(f"用户 {user_id} 正在恢复书籍 {long_context_book_id} 第5章的写作...")
            resume_response = await client.continue_content(
                book_id=long_context_book_id,
                chapter_id=5,
                prompt="请继续写作，接着上次中断的地方"
            )
            resume_content = resume_response.get("content", "")
            logger.info(f"用户 {user_id} 成功恢复中断的写作，新增内容: {len(resume_content)} 字符")
            
            # 记录完成情况
            metrics_collector.record_workflow_completion(user_id, True)
            logger.info(f"用户 {user_id} 成功完成高级工作流，完成了全部测试步骤")
            
        except Exception as e:
            # 记录错误
            error_msg = str(e)
            metrics_collector.record_workflow_error(user_id, error_msg)
            logger.error(f"用户 {user_id} 执行高级工作流失败: {error_msg}")
    
    def run_locust_test(
        self,
        test_file: str = "workflow_test.py",
        test_type: str = "spike",
        users: int = 100,
        spawn_rate: int = 10,
        run_time: str = "5m",
        host: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行Locust负载测试
        
        Args:
            test_file: Locust测试文件
            test_type: 测试类型（ramp-up, spike, soak）
            users: 用户数量
            spawn_rate: 用户生成速率
            run_time: 运行时间（格式：1h30m, 5m, 30s等）
            host: 目标主机（如果为None则使用默认base_url）
            
        Returns:
            测试启动结果
        """
        logger.info(f"开始执行Locust测试: {test_type}, 文件: {test_file}")
        
        if self.current_test_process:
            logger.warning("已有测试正在运行，请先停止当前测试")
            return {"error": "已有测试正在运行"}
        
        # 确保Locust测试文件存在
        test_file_path = Path("locust_tests") / test_file
        if not test_file_path.exists():
            logger.error(f"Locust测试文件不存在: {test_file_path}")
            return {"error": f"Locust测试文件不存在: {test_file_path}"}
        
        # 记录测试开始时间
        self.test_start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 设置结果路径
        result_path = self.results_dir / f"locust_{test_type}_{timestamp}"
        result_path.mkdir(exist_ok=True)
        
        # 构建Locust命令
        target_host = host or self.base_url
        
        # 检查测试类型，设置不同的参数
        locust_cmd = [
            "locust", 
            "-f", str(test_file_path),
            "--headless",
            "--host", target_host,
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", run_time,
            "--csv", str(result_path / "stats"),
            "--html", str(result_path / "report.html")
        ]
        
        # 根据测试类型调整参数
        if test_type == "ramp-up":
            # 渐进式增加负载
            locust_cmd.extend(["--step-load", "--step-users", str(int(users/5))])
        elif test_type == "spike":
            # 尖峰测试，直接使用全部用户
            pass  # 默认参数就是尖峰测试
        elif test_type == "soak":
            # 浸泡测试，较长时间
            if run_time == "5m":  # 如果使用默认值，则调整为更长时间
                locust_cmd[locust_cmd.index("--run-time") + 1] = "4h"
        
        logger.info(f"执行Locust命令: {' '.join(locust_cmd)}")
        
        # 启动Locust进程
        self.current_test_process = subprocess.Popen(
            locust_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 记录测试信息
        test_info = {
            "test_type": test_type,
            "command": " ".join(locust_cmd),
            "start_time": timestamp,
            "status": "running",
            "pid": self.current_test_process.pid,
            "result_path": str(result_path)
        }
        
        # 保存测试信息
        import json
        with open(result_path / "test_info.json", "w") as f:
            json.dump(test_info, f, indent=2)
            
        logger.info(f"Locust测试启动成功，PID: {self.current_test_process.pid}, 结果将保存到: {result_path}")
        return test_info
    
    def stop_current_test(self, force: bool = False) -> Dict[str, Any]:
        """
        停止当前正在运行的测试
        
        Args:
            force: 是否强制停止
            
        Returns:
            停止结果
        """
        if not self.current_test_process:
            logger.warning("没有正在运行的测试")
            return {"status": "no_test_running"}
        
        logger.info(f"正在停止测试进程，PID: {self.current_test_process.pid}, 强制: {force}")
        
        # 记录测试结束时间
        self.test_end_time = time.time()
        
        try:
            if force:
                # 强制终止
                self.current_test_process.kill()
            else:
                # 发送终止信号
                self.current_test_process.send_signal(signal.SIGTERM)
                
                # 等待进程结束，最多等待10秒
                try:
                    self.current_test_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # 如果超时，则强制终止
                    logger.warning("测试进程未在10秒内终止，强制结束")
                    self.current_test_process.kill()
            
            # 收集输出
            stdout, stderr = self.current_test_process.communicate()
            
            # 保存日志
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = self.log_dir / f"test_log_{timestamp}.txt"
            with open(log_file, "w") as f:
                f.write("=== STDOUT ===\n")
                f.write(stdout)
                f.write("\n\n=== STDERR ===\n")
                f.write(stderr)
            
            result = {
                "status": "stopped",
                "exit_code": self.current_test_process.returncode,
                "duration": self.test_end_time - self.test_start_time if self.test_start_time else None,
                "log_file": str(log_file)
            }
            
            # 清理进程引用
            self.current_test_process = None
            
            logger.info(f"测试已停止，退出代码: {result['exit_code']}, 日志: {log_file}")
            return result
            
        except Exception as e:
            logger.error(f"停止测试时发生错误: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def get_test_status(self) -> Dict[str, Any]:
        """
        获取当前测试状态
        
        Returns:
            测试状态信息
        """
        if not self.current_test_process:
            return {"status": "no_test_running"}
        
        # 检查进程是否还在运行
        if self.current_test_process.poll() is None:
            # 进程正在运行
            current_time = time.time()
            elapsed_time = current_time - self.test_start_time if self.test_start_time else None
            
            return {
                "status": "running",
                "pid": self.current_test_process.pid,
                "elapsed_time": elapsed_time,
                "start_time": self.test_start_time
            }
        else:
            # 进程已结束
            return {
                "status": "completed",
                "exit_code": self.current_test_process.returncode,
                "duration": self.test_end_time - self.test_start_time if self.test_start_time and self.test_end_time else None
            }
    
    def load_results(self, result_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载测试结果
        
        Args:
            result_path: 结果目录路径
            
        Returns:
            测试结果汇总
        """
        result_path = Path(result_path)
        
        if not result_path.exists():
            logger.error(f"结果路径不存在: {result_path}")
            return {"error": f"结果路径不存在: {result_path}"}
        
        logger.info(f"正在加载测试结果: {result_path}")
        
        # 检查是否是Locust测试结果
        locust_stats_file = result_path / "stats_history.csv"
        if locust_stats_file.exists():
            # Locust测试结果
            try:
                # 加载Locust统计数据
                stats_history = pd.read_csv(locust_stats_file)
                stats = pd.read_csv(result_path / "stats.csv")
                
                # 提取关键指标
                summary = {
                    "test_type": "locust",
                    "total_requests": stats["Total"].iloc[0] if not stats.empty else 0,
                    "failure_rate": stats["Failure Rate"].iloc[0] if not stats.empty else 0,
                    "average_response_time": stats["Average Response Time"].iloc[0] if not stats.empty else 0,
                    "min_response_time": stats["Min Response Time"].iloc[0] if not stats.empty else 0,
                    "max_response_time": stats["Max Response Time"].iloc[0] if not stats.empty else 0,
                    "requests_per_second": stats["Requests/s"].iloc[0] if not stats.empty else 0,
                    "duration": stats_history["timestamp"].max() - stats_history["timestamp"].min() if not stats_history.empty else 0,
                    "timestamp": datetime.fromtimestamp(stats_history["timestamp"].min()).strftime("%Y-%m-%d %H:%M:%S") if not stats_history.empty else None
                }
                
                # 读取测试信息
                info_file = result_path / "test_info.json"
                if info_file.exists():
                    import json
                    with open(info_file, "r") as f:
                        test_info = json.load(f)
                    summary.update(test_info)
                
                logger.info(f"已加载Locust测试结果，总请求数: {summary['total_requests']}")
                return summary
                
            except Exception as e:
                logger.error(f"加载Locust测试结果时发生错误: {str(e)}")
                return {"error": f"加载Locust测试结果时发生错误: {str(e)}"}
        
        # 检查是否是基本测试结果
        report_file = result_path / "report.json"
        if report_file.exists():
            # 基本测试结果
            try:
                import json
                with open(report_file, "r") as f:
                    report = json.load(f)
                
                logger.info(f"已加载基本测试结果")
                return report
                
            except Exception as e:
                logger.error(f"加载基本测试结果时发生错误: {str(e)}")
                return {"error": f"加载基本测试结果时发生错误: {str(e)}"}
        
        # 如果没有找到已知格式的结果
        logger.warning(f"在路径中没有找到已知格式的测试结果: {result_path}")
        return {"error": "未识别的测试结果格式"}
    
    def get_test_logs(self, num_lines: int = 100) -> List[str]:
        """
        获取测试日志
        
        Args:
            num_lines: 要获取的最近日志行数
            
        Returns:
            日志行列表
        """
        # 获取日志目录中最新的日志文件
        log_files = list(self.log_dir.glob("*.txt"))
        if not log_files:
            return ["无可用日志文件"]
        
        # 按修改时间排序
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_log = log_files[0]
        
        try:
            # 读取最近的日志行
            with open(latest_log, "r") as f:
                lines = f.readlines()
            
            # 获取最后num_lines行
            return lines[-num_lines:] if len(lines) > num_lines else lines
            
        except Exception as e:
            logger.error(f"读取日志文件时发生错误: {str(e)}")
            return [f"读取日志文件时发生错误: {str(e)}"]

# 创建测试运行器单例实例
test_runner = TestRunner() 