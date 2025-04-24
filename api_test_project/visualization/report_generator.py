"""
报告生成器模块

根据测试结果生成美观、详细的HTML测试报告
"""
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from plotly.subplots import make_subplots

# 配置日志
logger = logging.getLogger(__name__)


class ReportGenerator:
    """生成API性能测试报告的类"""
    
    def __init__(self) -> None:
        """初始化报告生成器"""
        self.reports_dir = Path("reports")
        self.templates_dir = Path(__file__).parent / "templates"
        
        # 确保报告目录存在
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # 确保模板目录存在
        if not self.templates_dir.exists():
            os.makedirs(self.templates_dir, exist_ok=True)
            logger.warning(f"模板目录不存在，已创建: {self.templates_dir}")
        
        # 初始化Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )
        
        # 检查模板文件是否存在
        self._check_templates()
    
    def _check_templates(self) -> None:
        """检查模板文件是否存在，如果不存在则使用内联模板"""
        template_files = {
            "basic_report_template.html": self._get_inline_basic_template,
            "locust_report_template.html": self._get_inline_locust_template,
            "comparison_report_template.html": self._get_inline_comparison_template
        }
        
        for template_name, template_func in template_files.items():
            template_path = self.templates_dir / template_name
            if not template_path.exists():
                logger.info(f"模板文件 {template_name} 不存在，使用内联模板")
    
    def generate_report(self, result_path: Union[str, Path]) -> str:
        """
        根据测试结果生成HTML报告
        
        Args:
            result_path: 测试结果目录路径
            
        Returns:
            生成的报告文件路径
        """
        try:
            # 确保路径是Path对象
            result_path = Path(result_path)
            if not result_path.exists():
                raise FileNotFoundError(f"测试结果目录不存在: {result_path}")
            
            # 加载测试结果数据
            data = self._load_result_data(result_path)
            
            # 获取报告类型
            if data.get("test_type") == "locust":
                return self._generate_locust_report(result_path, data)
            else:
                return self._generate_basic_report(result_path, data)
        
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"生成报告失败: {str(e)}")
    
    def generate_comparison_report(self, result_paths: List[Union[str, Path]]) -> str:
        """
        生成多个测试结果的比较报告
        
        Args:
            result_paths: 多个测试结果目录路径列表
            
        Returns:
            生成的比较报告文件路径
        """
        if len(result_paths) < 2:
            raise ValueError("比较报告至少需要两个测试结果")
        
        try:
            # 加载所有测试结果
            tests_data = []
            test_types = set()
            
            for path in result_paths:
                path = Path(path)
                if not path.exists():
                    logger.warning(f"测试结果路径不存在，将跳过: {path}")
                    continue
                
                data = self._load_result_data(path)
                data["result_path"] = path
                tests_data.append(data)
                test_types.add(data.get("test_type", "未知"))
            
            if len(tests_data) < 2:
                raise ValueError("没有足够的有效测试结果用于比较")
            
            # 生成比较报告
            return self._generate_comparison_report(tests_data)
            
        except Exception as e:
            logger.error(f"生成比较报告失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"生成比较报告失败: {str(e)}")
    
    def _generate_comparison_report(self, tests_data: List[Dict[str, Any]]) -> str:
        """生成测试结果比较报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"comparison_report_{timestamp}.html"
        report_path = self.reports_dir / report_filename
        
        # 准备测试信息
        tests = []
        test_types = []
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
        
        for i, test in enumerate(tests_data):
            test_name = test.get("test_name", f"测试 {i+1}")
            test_type = test.get("test_type", "未知")
            test_types.append(test_type)
            
            tests.append({
                "name": test_name,
                "type": test_type,
                "concurrent_users": test.get("concurrent_users", 0),
                "timestamp": test.get("timestamp", "未知"),
                "duration": test.get("planned_duration", "未知"),
                "color": colors[i % len(colors)]
            })
        
        # 准备指标比较数据
        metrics = []
        
        # 1. 平均首Token响应时间(TTFT)对比
        ttft_values = []
        for test in tests_data:
            avg_ttft = test.get("metrics_summary", {}).get("avg_ttft", 0)
            ttft_values.append({
                "value": avg_ttft,
                "formatted": f"{avg_ttft:.3f}秒",
                "class": ""  # 稍后计算
            })
        
        # 计算变化百分比（如果有两个测试）
        ttft_change = ""
        ttft_change_class = ""
        if len(ttft_values) >= 2:
            old_value = ttft_values[0]["value"]
            new_value = ttft_values[-1]["value"]
            if old_value > 0:
                change_pct = (new_value - old_value) / old_value * 100
                ttft_change = f"{change_pct:.1f}%"
                # 注意对于响应时间，减少是好的
                ttft_change_class = "better-value" if change_pct < 0 else "worse-value" if change_pct > 0 else "neutral-value"
        
        metrics.append({
            "name": "平均首Token响应时间(TTFT)",
            "values": ttft_values,
            "change": ttft_change,
            "change_class": ttft_change_class
        })
        
        # 2. 平均完整响应时间(TTCT)对比
        ttct_values = []
        for test in tests_data:
            avg_ttct = test.get("metrics_summary", {}).get("avg_ttct", 0)
            ttct_values.append({
                "value": avg_ttct,
                "formatted": f"{avg_ttct:.3f}秒",
                "class": ""
            })
        
        ttct_change = ""
        ttct_change_class = ""
        if len(ttct_values) >= 2:
            old_value = ttct_values[0]["value"]
            new_value = ttct_values[-1]["value"]
            if old_value > 0:
                change_pct = (new_value - old_value) / old_value * 100
                ttct_change = f"{change_pct:.1f}%"
                ttct_change_class = "better-value" if change_pct < 0 else "worse-value" if change_pct > 0 else "neutral-value"
        
        metrics.append({
            "name": "平均完整响应时间(TTCT)",
            "values": ttct_values,
            "change": ttct_change,
            "change_class": ttct_change_class
        })
        
        # 3. 吞吐量对比
        throughput_values = []
        for test in tests_data:
            throughput = test.get("metrics_summary", {}).get("avg_throughput", 0)
            throughput_values.append({
                "value": throughput,
                "formatted": f"{throughput:.2f}token/s",
                "class": ""
            })
        
        throughput_change = ""
        throughput_change_class = ""
        if len(throughput_values) >= 2:
            old_value = throughput_values[0]["value"]
            new_value = throughput_values[-1]["value"]
            if old_value > 0:
                change_pct = (new_value - old_value) / old_value * 100
                throughput_change = f"{change_pct:.1f}%"
                throughput_change_class = "better-value" if change_pct > 0 else "worse-value" if change_pct < 0 else "neutral-value"
        
        metrics.append({
            "name": "平均吞吐量",
            "values": throughput_values,
            "change": throughput_change,
            "change_class": throughput_change_class
        })
        
        # 4. 成功率对比
        success_values = []
        for test in tests_data:
            success_rate = test.get("metrics_summary", {}).get("success_rate", 0) * 100
            success_values.append({
                "value": success_rate,
                "formatted": f"{success_rate:.1f}%",
                "class": ""
            })
        
        success_change = ""
        success_change_class = ""
        if len(success_values) >= 2:
            old_value = success_values[0]["value"]
            new_value = success_values[-1]["value"]
            if old_value > 0:
                change_pct = (new_value - old_value) / old_value * 100
                success_change = f"{change_pct:.1f}%"
                success_change_class = "better-value" if change_pct > 0 else "worse-value" if change_pct < 0 else "neutral-value"
        
        metrics.append({
            "name": "成功率",
            "values": success_values,
            "change": success_change,
            "change_class": success_change_class
        })
        
        # 创建对比图表
        charts = {}
        
        # 准备各种对比图表 - 这里使用简单示例
        # 在实际应用中，可以根据更详细的数据生成更复杂的图表
        
        # TTFT对比图
        ttft_data = {
            "测试": [test["name"] for test in tests],
            "TTFT(秒)": [test.get("metrics_summary", {}).get("avg_ttft", 0) for test in tests_data]
        }
        ttft_df = pd.DataFrame(ttft_data)
        fig = px.bar(
            ttft_df,
            x="测试",
            y="TTFT(秒)",
            title="首Token响应时间对比",
            color="测试",
            text_auto='.3f'
        )
        charts["ttft_comparison"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # TTCT对比图
        ttct_data = {
            "测试": [test["name"] for test in tests],
            "TTCT(秒)": [test.get("metrics_summary", {}).get("avg_ttct", 0) for test in tests_data]
        }
        ttct_df = pd.DataFrame(ttct_data)
        fig = px.bar(
            ttct_df,
            x="测试",
            y="TTCT(秒)",
            title="完整响应时间对比",
            color="测试",
            text_auto='.3f'
        )
        charts["ttct_comparison"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 吞吐量对比图
        throughput_data = {
            "测试": [test["name"] for test in tests],
            "吞吐量(token/s)": [test.get("metrics_summary", {}).get("avg_throughput", 0) for test in tests_data]
        }
        throughput_df = pd.DataFrame(throughput_data)
        fig = px.bar(
            throughput_df,
            x="测试",
            y="吞吐量(token/s)",
            title="吞吐量对比",
            color="测试",
            text_auto='.2f'
        )
        charts["throughput_comparison"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 成功率对比图
        success_data = {
            "测试": [test["name"] for test in tests],
            "成功率(%)": [test.get("metrics_summary", {}).get("success_rate", 0) * 100 for test in tests_data]
        }
        success_df = pd.DataFrame(success_data)
        fig = px.bar(
            success_df,
            x="测试",
            y="成功率(%)",
            title="成功率对比",
            color="测试",
            text_auto='.1f'
        )
        charts["success_rate_comparison"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 性能雷达图
        if len(tests) > 1:
            # 归一化指标值用于雷达图
            normalized_metrics = []
            metric_names = ["TTFT", "TTCT", "吞吐量", "成功率"]
            
            for i, test in enumerate(tests):
                ttft = tests_data[i].get("metrics_summary", {}).get("avg_ttft", 0)
                ttct = tests_data[i].get("metrics_summary", {}).get("avg_ttct", 0)
                throughput = tests_data[i].get("metrics_summary", {}).get("avg_throughput", 0)
                success_rate = tests_data[i].get("metrics_summary", {}).get("success_rate", 0) * 100
                
                # 对于响应时间，小值更好，需要反转
                max_ttft = max([test.get("metrics_summary", {}).get("avg_ttft", 0) for test in tests_data]) + 0.001
                max_ttct = max([test.get("metrics_summary", {}).get("avg_ttct", 0) for test in tests_data]) + 0.001
                max_throughput = max([test.get("metrics_summary", {}).get("avg_throughput", 0) for test in tests_data]) + 0.001
                
                normalized_ttft = 1 - (ttft / max_ttft) if max_ttft > 0 else 0
                normalized_ttct = 1 - (ttct / max_ttct) if max_ttct > 0 else 0
                normalized_throughput = throughput / max_throughput if max_throughput > 0 else 0
                normalized_success = success_rate / 100
                
                normalized_metrics.append([normalized_ttft * 10, normalized_ttct * 10, normalized_throughput * 10, normalized_success * 10])
            
            # 创建雷达图
            fig = go.Figure()
            
            for i, test in enumerate(tests):
                fig.add_trace(go.Scatterpolar(
                    r=normalized_metrics[i],
                    theta=metric_names,
                    fill='toself',
                    name=test["name"]
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 10]
                    )
                ),
                title="性能指标雷达图"
            )
            charts["performance_radar"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 生成总体结论
        conclusion = "基于性能指标对比分析，"
        
        if len(tests) == 2:
            # 如果只有两个测试，生成简单的对比结论
            if ttft_change_class == "better-value":
                conclusion += f"{tests[1]['name']}的首Token响应时间比{tests[0]['name']}改善了{ttft_change.replace('-', '')}。"
            elif ttft_change_class == "worse-value":
                conclusion += f"{tests[1]['name']}的首Token响应时间比{tests[0]['name']}恶化了{ttft_change}。"
            
            if throughput_change_class == "better-value":
                conclusion += f"吞吐量提高了{throughput_change}。"
            elif throughput_change_class == "worse-value":
                conclusion += f"吞吐量下降了{throughput_change.replace('-', '')}。"
            
            if success_change_class == "better-value":
                conclusion += f"成功率提高了{success_change}。"
            elif success_change_class == "worse-value":
                conclusion += f"成功率下降了{success_change.replace('-', '')}。"
        else:
            # 多个测试的情况
            best_ttft_idx = ttft_values.index(min([v for v in ttft_values], key=lambda x: x["value"]))
            best_throughput_idx = throughput_values.index(max([v for v in throughput_values], key=lambda x: x["value"]))
            best_success_idx = success_values.index(max([v for v in success_values], key=lambda x: x["value"]))
            
            conclusion += f"{tests[best_ttft_idx]['name']}的首Token响应时间最佳，{tests[best_throughput_idx]['name']}的吞吐量最高，{tests[best_success_idx]['name']}的成功率最高。"
        
        # 准备报告数据
        report_data = {
            "title": f"LLM API测试结果比较报告",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tests": tests,
            "test_types": list(set(test_types)),
            "metrics": metrics,
            "charts": charts,
            "conclusion": conclusion
        }
        
        # 渲染报告模板
        template = self.env.get_template("comparison_report_template.html")
        if template is None:
            # 如果模板不存在，使用内联模板
            template_str = self._get_inline_comparison_template()
            report_html = Environment().from_string(template_str).render(**report_data)
        else:
            report_html = template.render(**report_data)
        
        # 保存报告
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_html)
        
        logger.info(f"比较报告已生成: {report_path}")
        return str(report_path)
    
    def _load_result_data(self, result_path: Path) -> Dict[str, Any]:
        """加载测试结果数据"""
        # 检查report.json文件
        report_file = result_path / "report.json"
        if report_file.exists():
            with open(report_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        # 检查test_info.json文件
        info_file = result_path / "test_info.json"
        if info_file.exists():
            with open(info_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 如果是Locust测试，解析stats.csv
            if data.get("test_type") == "locust":
                stats_file = result_path / "stats.csv"
                if stats_file.exists():
                    stats_df = pd.read_csv(stats_file)
                    if not stats_df.empty:
                        data.update({
                            "total_requests": stats_df["Total"].sum(),
                            "average_response_time": stats_df["Average Response Time"].mean(),
                            "p90_response_time": stats_df["90%ile Response Time"].mean(),
                            "failure_rate": stats_df["Fail Ratio"].mean() * 100 if "Fail Ratio" in stats_df.columns else 0,
                            "requests_per_second": stats_df["Requests/s"].sum()
                        })
            
            return data
        
        # 如果没有找到任何结果文件，尝试基于目录结构推断信息
        return {
            "test_type": "unknown",
            "timestamp": datetime.fromtimestamp(result_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "result_path": str(result_path)
        }
    
    def _generate_basic_report(self, result_path: Path, data: Dict[str, Any]) -> str:
        """生成基础测试报告"""
        # 创建报告文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_basic_{result_path.name}_{timestamp}.html"
        report_path = self.reports_dir / report_filename
        
        # 创建图表
        charts = {}
        
        # 1. 响应时间分布图
        response_time_data = self._load_csv_data(result_path / "response_times.csv")
        if response_time_data is not None:
            fig = px.histogram(
                response_time_data, 
                x="response_time",
                nbins=30,
                labels={"response_time": "响应时间(秒)"},
                title="响应时间分布"
            )
            fig.update_layout(
                xaxis_title="响应时间(秒)",
                yaxis_title="请求数",
                bargap=0.1
            )
            charts["response_time_dist"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
            
            # 响应时间随时间变化图
            if "timestamp" in response_time_data.columns:
                response_time_data["timestamp"] = pd.to_datetime(response_time_data["timestamp"])
                fig = px.scatter(
                    response_time_data, 
                    x="timestamp", 
                    y="response_time",
                    labels={"timestamp": "时间", "response_time": "响应时间(秒)"},
                    title="响应时间随时间变化"
                )
                fig.update_layout(
                    xaxis_title="时间",
                    yaxis_title="响应时间(秒)"
                )
                charts["response_time_series"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 2. 首Token响应时间(TTFT)分析
        ttft_data = self._load_csv_data(result_path / "ttft.csv")
        if ttft_data is not None:
            fig = px.histogram(
                ttft_data, 
                x="ttft",
                nbins=30,
                labels={"ttft": "首Token响应时间(秒)"},
                title="首Token响应时间分布"
            )
            fig.update_layout(
                xaxis_title="首Token响应时间(秒)",
                yaxis_title="请求数",
                bargap=0.1
            )
            charts["ttft_dist"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
            
            # TTFT随时间变化图
            if "timestamp" in ttft_data.columns:
                ttft_data["timestamp"] = pd.to_datetime(ttft_data["timestamp"])
                fig = px.scatter(
                    ttft_data, 
                    x="timestamp", 
                    y="ttft",
                    labels={"timestamp": "时间", "ttft": "首Token响应时间(秒)"},
                    title="首Token响应时间随时间变化"
                )
                fig.update_layout(
                    xaxis_title="时间",
                    yaxis_title="首Token响应时间(秒)"
                )
                charts["ttft_series"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 3. 吞吐量(Throughput)分析
        throughput_data = self._load_csv_data(result_path / "throughput.csv")
        if throughput_data is not None:
            if "tokens_per_second" in throughput_data.columns:
                fig = px.histogram(
                    throughput_data, 
                    x="tokens_per_second",
                    nbins=30,
                    labels={"tokens_per_second": "每秒生成Token数"},
                    title="每秒生成Token数分布"
                )
                fig.update_layout(
                    xaxis_title="每秒生成Token数",
                    yaxis_title="请求数",
                    bargap=0.1
                )
                charts["throughput_dist"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
            
            # 吞吐量随时间变化图
            if "timestamp" in throughput_data.columns and "tokens_per_second" in throughput_data.columns:
                throughput_data["timestamp"] = pd.to_datetime(throughput_data["timestamp"])
                fig = px.line(
                    throughput_data, 
                    x="timestamp", 
                    y="tokens_per_second",
                    labels={"timestamp": "时间", "tokens_per_second": "每秒生成Token数"},
                    title="吞吐量随时间变化"
                )
                fig.update_layout(
                    xaxis_title="时间",
                    yaxis_title="每秒生成Token数"
                )
                charts["throughput_series"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 4. 错误率分析
        errors_data = self._load_csv_data(result_path / "errors.csv")
        if errors_data is not None and not errors_data.empty:
            # 如果有错误数据，创建错误分布图
            if "error_type" in errors_data.columns:
                error_counts = errors_data["error_type"].value_counts().reset_index()
                error_counts.columns = ["error_type", "count"]
                
                fig = px.pie(
                    error_counts, 
                    values="count", 
                    names="error_type",
                    title="错误类型分布"
                )
                charts["error_dist"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
            
            # 错误随时间变化图
            if "timestamp" in errors_data.columns:
                errors_data["timestamp"] = pd.to_datetime(errors_data["timestamp"])
                errors_over_time = errors_data.groupby(pd.Grouper(key="timestamp", freq="1min")).size().reset_index(name="error_count")
                
                fig = px.line(
                    errors_over_time, 
                    x="timestamp", 
                    y="error_count",
                    labels={"timestamp": "时间", "error_count": "错误数"},
                    title="错误数随时间变化"
                )
                fig.update_layout(
                    xaxis_title="时间",
                    yaxis_title="错误数"
                )
                charts["error_series"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 准备报告数据
        report_data = {
            "title": f"API性能测试报告 - {data.get('test_type', '基础测试')}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_info": {
                "测试类型": data.get("test_type", "未知"),
                "工作流类型": data.get("workflow_type", "未知"),
                "并发用户数": data.get("concurrent_users", 0),
                "计划持续时间": f"{data.get('planned_duration', 0)}秒",
                "实际持续时间": f"{data.get('actual_duration', 0):.1f}秒",
                "测试时间": data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "结果目录": str(result_path)
            },
            "metrics_summary": {},
            "charts": charts
        }
        
        # 添加指标摘要
        metrics = data.get("metrics_summary", {})
        if metrics:
            # 格式化指标
            metrics_formatted = {}
            for key, value in metrics.items():
                if key == "success_rate":
                    metrics_formatted["成功率"] = f"{value * 100:.1f}%"
                elif key == "avg_ttft":
                    metrics_formatted["平均首Token响应时间"] = f"{value:.3f}秒"
                elif key == "avg_ttct":
                    metrics_formatted["平均完整响应时间"] = f"{value:.3f}秒"
                elif key == "avg_throughput":
                    metrics_formatted["平均吞吐量"] = f"{value:.2f}每秒Token数"
                elif key == "p90_ttft":
                    metrics_formatted["90%首Token响应时间"] = f"{value:.3f}秒"
                elif key == "p95_ttft":
                    metrics_formatted["95%首Token响应时间"] = f"{value:.3f}秒"
                elif key == "max_ttft":
                    metrics_formatted["最大首Token响应时间"] = f"{value:.3f}秒"
                elif key == "min_ttft":
                    metrics_formatted["最小首Token响应时间"] = f"{value:.3f}秒"
                else:
                    metrics_formatted[key] = f"{value}"
            
            report_data["metrics_summary"] = metrics_formatted
        
        # 渲染报告模板
        template = self.env.get_template("basic_report_template.html")
        if template is None:
            # 如果模板不存在，使用内联模板
            template_str = self._get_inline_basic_template()
            report_html = Environment().from_string(template_str).render(**report_data)
        else:
            report_html = template.render(**report_data)
        
        # 保存报告
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_html)
        
        return str(report_path)
    
    def _generate_locust_report(self, result_path: Path, data: Dict[str, Any]) -> str:
        """生成Locust负载测试报告"""
        # 创建报告文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_locust_{result_path.name}_{timestamp}.html"
        report_path = self.reports_dir / report_filename
        
        # 创建图表
        charts = {}
        
        # 1. 响应时间分布
        stats_file = result_path / "stats.csv"
        stats_history_file = result_path / "stats_history.csv"
        
        if stats_file.exists():
            stats_df = pd.read_csv(stats_file)
            if not stats_df.empty:
                # 创建请求统计表格
                fig = go.Figure(data=[
                    go.Table(
                        header=dict(
                            values=["端点", "请求数", "失败数", "平均响应时间(ms)", "中位数响应时间(ms)", "90%响应时间(ms)", "每秒请求数"],
                            fill_color="paleturquoise",
                            align="left"
                        ),
                        cells=dict(
                            values=[
                                stats_df["Name"],
                                stats_df["Total"],
                                stats_df["Fails"],
                                stats_df["Average Response Time"].round(2),
                                stats_df["Median Response Time"].round(2),
                                stats_df["90%ile Response Time"].round(2),
                                stats_df["Requests/s"].round(2)
                            ],
                            fill_color="lavender",
                            align="left"
                        )
                    )
                ])
                fig.update_layout(title="请求统计")
                charts["request_stats"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 2. 响应时间随时间变化
        if stats_history_file.exists():
            history_df = pd.read_csv(stats_history_file)
            if not history_df.empty:
                history_df["Timestamp"] = pd.to_datetime(history_df["Timestamp"])
                
                # 创建响应时间随时间变化图
                fig = px.line(
                    history_df,
                    x="Timestamp",
                    y=["Average Response Time", "Median Response Time", "95%ile Response Time"],
                    labels={"value": "响应时间(ms)", "Timestamp": "时间"},
                    title="响应时间随时间变化"
                )
                fig.update_layout(
                    xaxis_title="时间",
                    yaxis_title="响应时间(ms)",
                    legend_title="统计类型"
                )
                charts["response_time_history"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
                
                # 创建RPS和用户数随时间变化图
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                fig.add_trace(
                    go.Scatter(
                        x=history_df["Timestamp"],
                        y=history_df["Requests/s"],
                        name="每秒请求数(RPS)",
                        line=dict(color="blue")
                    ),
                    secondary_y=False
                )
                
                if "User Count" in history_df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=history_df["Timestamp"],
                            y=history_df["User Count"],
                            name="并发用户数",
                            line=dict(color="red")
                        ),
                        secondary_y=True
                    )
                
                fig.update_layout(
                    title="请求率和用户数随时间变化",
                    xaxis_title="时间"
                )
                fig.update_yaxes(title_text="每秒请求数", secondary_y=False)
                fig.update_yaxes(title_text="并发用户数", secondary_y=True)
                
                charts["rps_users_history"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
                
                # 创建错误率随时间变化图
                if "Failures/s" in history_df.columns:
                    fig = px.line(
                        history_df,
                        x="Timestamp",
                        y="Failures/s",
                        labels={"Failures/s": "每秒失败数", "Timestamp": "时间"},
                        title="失败率随时间变化"
                    )
                    fig.update_layout(
                        xaxis_title="时间",
                        yaxis_title="每秒失败数"
                    )
                    charts["failures_history"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 3. 吞吐量分析
        if data.get("failure_rate", 0) > 0:
            # 创建失败率饼图
            fig = go.Figure(data=[
                go.Pie(
                    labels=["成功", "失败"],
                    values=[100 - data.get("failure_rate", 0), data.get("failure_rate", 0)],
                    hole=.3
                )
            ])
            fig.update_layout(title="请求成功率")
            charts["success_rate_pie"] = fig.to_html(full_html=False, include_plotlyjs="cdn")
        
        # 准备报告数据
        report_data = {
            "title": f"Locust负载测试报告 - {data.get('test_type', '负载测试')}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_info": {
                "测试类型": f"Locust {data.get('test_type', '未知')}",
                "并发用户数": data.get("users", 0),
                "用户生成速率": f"{data.get('spawn_rate', 0)}用户/秒",
                "运行时间": data.get("run_time", "未知"),
                "测试文件": data.get("test_file", "未知"),
                "测试开始时间": data.get("start_time", "未知"),
                "结果目录": str(result_path)
            },
            "metrics_summary": {
                "总请求数": data.get("total_requests", 0),
                "平均响应时间": f"{data.get('average_response_time', 0):.2f}ms",
                "90%响应时间": f"{data.get('p90_response_time', 0):.2f}ms",
                "每秒请求数": f"{data.get('requests_per_second', 0):.2f}",
                "失败率": f"{data.get('failure_rate', 0):.2f}%"
            },
            "charts": charts
        }
        
        # 渲染报告模板
        template = self.env.get_template("locust_report_template.html")
        if template is None:
            # 如果模板不存在，使用内联模板
            template_str = self._get_inline_locust_template()
            report_html = Environment().from_string(template_str).render(**report_data)
        else:
            report_html = template.render(**report_data)
        
        # 保存报告
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_html)
        
        return str(report_path)
    
    def _load_csv_data(self, file_path: Path) -> Optional[pd.DataFrame]:
        """加载CSV数据文件"""
        if not file_path.exists():
            return None
        
        try:
            return pd.read_csv(file_path)
        except Exception as e:
            logger.warning(f"无法加载CSV文件 {file_path}: {str(e)}")
            return None
    
    def _get_inline_basic_template(self) -> str:
        """获取内联的基础报告HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .container {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
            text-align: center;
        }
        .section {
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .chart-container {
            margin: 20px 0;
            overflow: hidden;
        }
        .chart-row {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        .chart-box {
            flex: 1;
            min-width: 45%;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            padding: 15px;
            overflow: hidden;
        }
        @media (max-width: 768px) {
            .chart-box {
                min-width: 100%;
            }
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ title }}</h1>
            <div class="timestamp">生成时间: {{ timestamp }}</div>
        </div>
        
        <div class="section">
            <h2>测试信息</h2>
            <table>
                <tbody>
                    {% for key, value in test_info.items() %}
                    <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        {% if metrics_summary %}
        <div class="section">
            <h2>性能指标摘要</h2>
            <table>
                <tbody>
                    {% for key, value in metrics_summary.items() %}
                    <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
        
        {% if charts %}
        <div class="section">
            <h2>性能分析图表</h2>
            
            <div class="chart-container">
                {% if charts.response_time_dist or charts.ttft_dist %}
                <div class="chart-row">
                    {% if charts.response_time_dist %}
                    <div class="chart-box">
                        {{ charts.response_time_dist | safe }}
                    </div>
                    {% endif %}
                    
                    {% if charts.ttft_dist %}
                    <div class="chart-box">
                        {{ charts.ttft_dist | safe }}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                {% if charts.response_time_series or charts.ttft_series %}
                <div class="chart-row">
                    {% if charts.response_time_series %}
                    <div class="chart-box">
                        {{ charts.response_time_series | safe }}
                    </div>
                    {% endif %}
                    
                    {% if charts.ttft_series %}
                    <div class="chart-box">
                        {{ charts.ttft_series | safe }}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                {% if charts.throughput_dist or charts.throughput_series %}
                <div class="chart-row">
                    {% if charts.throughput_dist %}
                    <div class="chart-box">
                        {{ charts.throughput_dist | safe }}
                    </div>
                    {% endif %}
                    
                    {% if charts.throughput_series %}
                    <div class="chart-box">
                        {{ charts.throughput_series | safe }}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                {% if charts.error_dist or charts.error_series %}
                <div class="chart-row">
                    {% if charts.error_dist %}
                    <div class="chart-box">
                        {{ charts.error_dist | safe }}
                    </div>
                    {% endif %}
                    
                    {% if charts.error_series %}
                    <div class="chart-box">
                        {{ charts.error_series | safe }}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}
        
        <div class="footer">
            <p>LLM API性能测试报告 | 生成时间: {{ timestamp }}</p>
        </div>
    </div>
</body>
</html>
        """
    
    def _get_inline_locust_template(self) -> str:
        """获取内联的Locust报告HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .container {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
            text-align: center;
        }
        .section {
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .chart-container {
            margin: 20px 0;
            overflow: hidden;
        }
        .chart-row {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        .chart-box {
            flex: 1;
            min-width: 45%;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            padding: 15px;
            overflow: hidden;
        }
        @media (max-width: 768px) {
            .chart-box {
                min-width: 100%;
            }
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .metrics-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-card {
            flex: 1;
            min-width: 150px;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            text-align: center;
            background-color: #f8f9fa;
        }
        .metric-card .value {
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
            margin: 10px 0;
        }
        .metric-card .label {
            font-size: 0.9em;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ title }}</h1>
            <div class="timestamp">生成时间: {{ timestamp }}</div>
        </div>
        
        <div class="section">
            <h2>测试信息</h2>
            <table>
                <tbody>
                    {% for key, value in test_info.items() %}
                    <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        {% if metrics_summary %}
        <div class="section">
            <h2>性能指标摘要</h2>
            <div class="metrics-summary">
                {% for key, value in metrics_summary.items() %}
                <div class="metric-card">
                    <div class="value">{{ value }}</div>
                    <div class="label">{{ key }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        {% if charts %}
        <div class="section">
            <h2>性能分析图表</h2>
            
            <div class="chart-container">
                {% if charts.request_stats %}
                <div class="chart-row">
                    <div class="chart-box" style="min-width: 100%;">
                        {{ charts.request_stats | safe }}
                    </div>
                </div>
                {% endif %}
                
                {% if charts.response_time_history or charts.rps_users_history %}
                <div class="chart-row">
                    {% if charts.response_time_history %}
                    <div class="chart-box">
                        {{ charts.response_time_history | safe }}
                    </div>
                    {% endif %}
                    
                    {% if charts.rps_users_history %}
                    <div class="chart-box">
                        {{ charts.rps_users_history | safe }}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                {% if charts.failures_history or charts.success_rate_pie %}
                <div class="chart-row">
                    {% if charts.failures_history %}
                    <div class="chart-box">
                        {{ charts.failures_history | safe }}
                    </div>
                    {% endif %}
                    
                    {% if charts.success_rate_pie %}
                    <div class="chart-box">
                        {{ charts.success_rate_pie | safe }}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}
        
        <div class="footer">
            <p>LLM API负载测试报告 | 生成时间: {{ timestamp }}</p>
        </div>
    </div>
</body>
</html>
        """

    def _get_inline_comparison_template(self) -> str:
        """获取内联的比较报告HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .container {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
            text-align: center;
        }
        .section {
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .chart-container {
            margin: 20px 0;
            overflow: hidden;
        }
        .chart-row {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        .chart-box {
            flex: 1;
            min-width: 45%;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            padding: 15px;
            overflow: hidden;
        }
        @media (max-width: 768px) {
            .chart-box {
                min-width: 100%;
            }
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .comparison-table {
            margin-bottom: 30px;
        }
        .comparison-table th {
            text-align: center;
            background-color: #e3e7ed;
        }
        .better-value {
            color: #28a745;
            font-weight: bold;
        }
        .worse-value {
            color: #dc3545;
            font-weight: bold;
        }
        .neutral-value {
            color: #6c757d;
        }
        .info-box {
            background-color: #e7f5ff;
            border-left: 4px solid #4dabf7;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 0 5px 5px 0;
        }
        .highlight {
            background-color: #fffde7;
            padding: 2px 5px;
            border-radius: 3px;
        }
        .test-icon {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .recommendation-card {
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid #6c757d;
        }
        .recommendation-card.primary {
            border-left-color: #4e8df5;
        }
        .recommendation-card.success {
            border-left-color: #28a745;
        }
        .recommendation-card.warning {
            border-left-color: #ffc107;
        }
        .radar-chart {
            padding: 15px;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ title }}</h1>
            <div class="timestamp">生成时间: {{ timestamp }}</div>
        </div>
        
        <div class="section">
            <h2>测试对比概述</h2>
            <div class="info-box">
                <p>本报告对比了 {{ tests|length }} 个测试结果，包括
                {% for test_type in test_types %}{{ test_type }}{% if not loop.last %}、{% endif %}{% endfor %}。
                对比维度包括：响应时间、吞吐量、成功率、资源利用率等关键性能指标。</p>
            </div>
            
            <h3>测试基本信息</h3>
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>测试标识</th>
                        <th>测试类型</th>
                        <th>并发用户数</th>
                        <th>测试时间</th>
                        <th>测试持续时间</th>
                    </tr>
                </thead>
                <tbody>
                    {% for test in tests %}
                    <tr>
                        <td>
                            <span class="test-icon" style="background-color: {{ test.color }};"></span>
                            {{ test.name }}
                        </td>
                        <td>{{ test.type }}</td>
                        <td>{{ test.concurrent_users }}</td>
                        <td>{{ test.timestamp }}</td>
                        <td>{{ test.duration }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>关键指标对比</h2>
            
            {% if charts.key_metrics_chart %}
            <div class="chart-box" style="min-width: 100%;">
                {{ charts.key_metrics_chart | safe }}
            </div>
            {% endif %}
            
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>指标</th>
                        {% for test in tests %}
                        <th>{{ test.name }}</th>
                        {% endfor %}
                        <th>变化百分比</th>
                    </tr>
                </thead>
                <tbody>
                    {% for metric in metrics %}
                    <tr>
                        <td>{{ metric.name }}</td>
                        {% for value in metric.values %}
                        <td class="{{ value.class }}">{{ value.formatted }}</td>
                        {% endfor %}
                        <td class="{{ metric.change_class }}">{{ metric.change }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        {% if charts %}
        <div class="section">
            <h2>性能指标比较图表</h2>
            
            {% if charts.ttft_comparison or charts.ttct_comparison %}
            <div class="chart-row">
                {% if charts.ttft_comparison %}
                <div class="chart-box">
                    {{ charts.ttft_comparison | safe }}
                </div>
                {% endif %}
                
                {% if charts.ttct_comparison %}
                <div class="chart-box">
                    {{ charts.ttct_comparison | safe }}
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            {% if charts.throughput_comparison or charts.success_rate_comparison %}
            <div class="chart-row">
                {% if charts.throughput_comparison %}
                <div class="chart-box">
                    {{ charts.throughput_comparison | safe }}
                </div>
                {% endif %}
                
                {% if charts.success_rate_comparison %}
                <div class="chart-box">
                    {{ charts.success_rate_comparison | safe }}
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            {% if charts.performance_radar %}
            <div class="radar-chart">
                {{ charts.performance_radar | safe }}
            </div>
            {% endif %}
            
            {% if charts.ramp_up_comparison %}
            <div class="chart-box" style="min-width: 100%;">
                <h3>负载增加时的性能对比</h3>
                {{ charts.ramp_up_comparison | safe }}
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        {% if error_comparison %}
        <div class="section">
            <h2>错误分析对比</h2>
            
            {% if charts.error_comparison %}
            <div class="chart-box" style="min-width: 100%;">
                {{ charts.error_comparison | safe }}
            </div>
            {% endif %}
            
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>错误类型</th>
                        {% for test in tests %}
                        <th>{{ test.name }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for error in error_comparison %}
                    <tr>
                        <td>{{ error.type }}</td>
                        {% for count in error.counts %}
                        <td>{{ count }}</td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
        
        {% if recommendations %}
        <div class="section">
            <h2>优化建议</h2>
            
            {% for rec in recommendations %}
            <div class="recommendation-card {{ rec.priority }}">
                <h3>{{ rec.title }}</h3>
                <p>{{ rec.description }}</p>
                {% if rec.details %}
                <ul>
                    {% for detail in rec.details %}
                    <li>{{ detail }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <div class="section">
            <h2>结论</h2>
            <p>{{ conclusion }}</p>
        </div>
        
        <div class="footer">
            <p>LLM API测试对比报告 | 生成时间: {{ timestamp }}</p>
        </div>
    </div>
</body>
</html>
        """


# 创建报告生成器实例
report_generator = ReportGenerator() 