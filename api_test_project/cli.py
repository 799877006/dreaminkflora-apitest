"""
命令行界面

提供命令行工具用于启动和管理API性能测试
"""
import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from api_test_project.test_runner import test_runner
from api_test_project.visualization.report_generator import report_generator

# 创建Typer应用
app = typer.Typer(
    name="api-perf-test",
    help="LLM API性能测试工具",
    add_completion=False
)

# 创建Rich控制台实例
console = Console()


def get_results_directory() -> Path:
    """获取结果目录路径"""
    return Path(test_runner.results_dir)


@app.command("run-basic")
def run_basic_test(
    test_type: str = typer.Option(
        "response_time", 
        "--type", "-t", 
        help="测试类型: response_time, throughput, 或 ttft"
    ),
    users: int = typer.Option(
        10, 
        "--users", "-u", 
        help="并发用户数"
    ),
    duration: int = typer.Option(
        60, 
        "--duration", "-d", 
        help="测试持续时间(秒)"
    ),
    workflow: str = typer.Option(
        "basic", 
        "--workflow", "-w", 
        help="工作流类型: basic 或 advanced"
    ),
    api_url: Optional[str] = typer.Option(
        None, 
        "--api-url", 
        help="API基础URL(可选)"
    ),
) -> None:
    """
    运行基础API性能测试
    """
    # 设置API URL(如果提供)
    if api_url:
        test_runner.base_url = api_url
    
    # 显示测试配置
    console.print(Panel(
        f"[bold blue]启动基础测试[/bold blue]\n\n"
        f"测试类型: [yellow]{test_type}[/yellow]\n"
        f"并发用户数: [yellow]{users}[/yellow]\n"
        f"持续时间: [yellow]{duration}[/yellow]秒\n"
        f"工作流类型: [yellow]{workflow}[/yellow]\n"
        f"API URL: [yellow]{test_runner.base_url}[/yellow]",
        title="测试配置"
    ))
    
    # 创建进度条
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[bold]{task.completed}/{task.total}"),
        TimeElapsedColumn()
    ) as progress:
        test_task = progress.add_task("[bold blue]运行测试中...", total=None)
        
        # 运行测试
        try:
            # 获取事件循环或创建一个新的
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 运行测试
            test_result = loop.run_until_complete(
                test_runner.run_basic_test(
                    test_type=test_type,
                    concurrent_users=users,
                    duration_seconds=duration,
                    workflow_type=workflow
                )
            )
            
            progress.update(test_task, completed=1, total=1)
            
            # 检查测试结果
            if "error" in test_result:
                console.print(f"[bold red]测试失败:[/bold red] {test_result['error']}")
                sys.exit(1)
            
            # 显示测试结果摘要
            console.print(Panel(
                f"[bold green]测试完成！[/bold green]\n\n"
                f"结果目录: [yellow]{test_result.get('result_path', 'N/A')}[/yellow]\n"
                f"实际持续时间: [yellow]{test_result.get('actual_duration', 0):.2f}[/yellow]秒\n",
                title="测试结果摘要"
            ))
            
            # 询问是否生成报告
            if typer.confirm("是否生成HTML报告?"):
                report_path = report_generator.generate_report(test_result.get("result_path"))
                console.print(f"[bold green]报告已生成:[/bold green] {report_path}")
        
        except KeyboardInterrupt:
            console.print("\n[bold yellow]测试被用户中断[/bold yellow]")
            sys.exit(130)
        except Exception as e:
            console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
            sys.exit(1)


@app.command("run-locust")
def run_locust_test(
    test_type: str = typer.Option(
        "ramp-up", 
        "--type", "-t", 
        help="测试类型: spike, ramp-up, 或 soak"
    ),
    users: int = typer.Option(
        100, 
        "--users", "-u", 
        help="用户数量"
    ),
    spawn_rate: int = typer.Option(
        10, 
        "--spawn-rate", "-r", 
        help="用户生成速率(每秒)"
    ),
    run_time: str = typer.Option(
        "5m", 
        "--run-time", "-d", 
        help="运行时间(格式: 5m, 1h等)"
    ),
    test_file: str = typer.Option(
        "workflow_test.py", 
        "--file", "-f", 
        help="Locust测试文件"
    ),
    api_url: Optional[str] = typer.Option(
        None, 
        "--api-url", 
        help="API基础URL(可选)"
    ),
) -> None:
    """
    运行Locust负载测试
    """
    # 设置API URL(如果提供)
    if api_url:
        test_runner.base_url = api_url
    
    # 显示测试配置
    console.print(Panel(
        f"[bold blue]启动Locust测试[/bold blue]\n\n"
        f"测试类型: [yellow]{test_type}[/yellow]\n"
        f"用户数量: [yellow]{users}[/yellow]\n"
        f"用户生成速率: [yellow]{spawn_rate}[/yellow]用户/秒\n"
        f"运行时间: [yellow]{run_time}[/yellow]\n"
        f"测试文件: [yellow]{test_file}[/yellow]\n"
        f"API URL: [yellow]{test_runner.base_url}[/yellow]",
        title="测试配置"
    ))
    
    # 启动Locust测试
    try:
        test_info = test_runner.run_locust_test(
            test_type=test_type,
            test_file=test_file,
            users=users,
            spawn_rate=spawn_rate,
            run_time=run_time
        )
        
        # 检查测试结果
        if "error" in test_info:
            console.print(f"[bold red]测试启动失败:[/bold red] {test_info['error']}")
            sys.exit(1)
        
        # 显示测试信息
        console.print(Panel(
            f"[bold green]Locust测试已启动！[/bold green]\n\n"
            f"进程ID: [yellow]{test_info.get('pid', 'N/A')}[/yellow]\n"
            f"结果目录: [yellow]{test_info.get('result_path', 'N/A')}[/yellow]\n"
            f"Web UI: [yellow]http://localhost:8089[/yellow]\n",
            title="测试信息"
        ))
        
        console.print("[bold]测试正在后台运行中，可以使用以下命令查看状态:[/bold]\n")
        console.print("  api-perf-test check-status")
        console.print("  api-perf-test stop-test")
    
    except KeyboardInterrupt:
        console.print("\n[bold yellow]操作被用户中断[/bold yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
        sys.exit(1)


@app.command("stop-test")
def stop_test(
    force: bool = typer.Option(
        False, 
        "--force", "-f", 
        help="强制停止测试"
    )
) -> None:
    """
    停止当前运行的测试
    """
    try:
        # 获取当前测试状态
        status = test_runner.get_test_status()
        
        if status["status"] == "no_test_running":
            console.print("[yellow]当前没有测试在运行[/yellow]")
            return
        
        # 显示当前测试信息
        if status["status"] == "running":
            console.print(Panel(
                f"进程ID: [yellow]{status.get('pid', 'N/A')}[/yellow]\n"
                f"已运行: [yellow]{status.get('elapsed_time', 0):.1f}[/yellow]秒",
                title="当前运行的测试"
            ))
        
        # 确认停止
        if not force and not typer.confirm("确定要停止当前测试?"):
            console.print("[yellow]操作已取消[/yellow]")
            return
        
        # 停止测试
        with console.status("[bold blue]正在停止测试...[/bold blue]"):
            result = test_runner.stop_current_test(force=force)
        
        if result["status"] == "stopped":
            console.print("[bold green]测试已成功停止[/bold green]")
        else:
            console.print(f"[bold red]停止测试失败:[/bold red] {result.get('error', '未知错误')}")
    
    except Exception as e:
        console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
        sys.exit(1)


@app.command("check-status")
def check_status() -> None:
    """
    检查当前测试状态
    """
    try:
        # 获取当前测试状态
        status = test_runner.get_test_status()
        
        # 显示状态
        if status["status"] == "no_test_running":
            console.print("[yellow]当前没有测试在运行[/yellow]")
        elif status["status"] == "running":
            console.print(Panel(
                f"进程ID: [yellow]{status.get('pid', 'N/A')}[/yellow]\n"
                f"已运行: [yellow]{status.get('elapsed_time', 0):.1f}[/yellow]秒\n"
                f"命令: [yellow]{status.get('command', 'N/A')}[/yellow]",
                title="[bold green]测试正在运行中[/bold green]"
            ))
        elif status["status"] == "completed":
            console.print(Panel(
                f"退出代码: [yellow]{status.get('exit_code', 'N/A')}[/yellow]\n"
                f"持续时间: [yellow]{status.get('duration', 0):.1f}[/yellow]秒",
                title="[bold blue]测试已完成[/bold blue]"
            ))
    
    except Exception as e:
        console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
        sys.exit(1)


@app.command("list-results")
def list_results(
    limit: int = typer.Option(
        10, 
        "--limit", "-n", 
        help="显示结果数量"
    )
) -> None:
    """
    列出最近的测试结果
    """
    try:
        # 获取结果目录
        results_dir = get_results_directory()
        
        if not results_dir.exists():
            console.print(f"[yellow]结果目录不存在: {results_dir}[/yellow]")
            return
        
        # 获取所有结果目录
        result_dirs = sorted(
            [d for d in results_dir.iterdir() if d.is_dir()], 
            key=lambda d: d.stat().st_mtime, 
            reverse=True
        )
        
        if not result_dirs:
            console.print("[yellow]尚无测试结果[/yellow]")
            return
        
        # 限制结果数量
        result_dirs = result_dirs[:limit]
        
        # 创建表格
        table = Table(title="最近的测试结果")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("时间", style="magenta")
        table.add_column("测试类型", style="green")
        table.add_column("结果目录", style="blue")
        
        # 填充表格
        for i, result_dir in enumerate(result_dirs, 1):
            # 尝试读取测试信息
            try:
                info_path = result_dir / "test_info.json"
                if info_path.exists():
                    import json
                    with open(info_path, "r") as f:
                        test_info = json.load(f)
                        
                    test_type = test_info.get("test_type", "未知")
                    if test_info.get("workflow_type"):
                        test_type += f" ({test_info['workflow_type']})"
                else:
                    test_type = "未知"
            except:
                test_type = "未知"
            
            # 获取结果目录的修改时间
            mtime = datetime.fromtimestamp(result_dir.stat().st_mtime)
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
            
            # 添加行
            table.add_row(
                str(i),
                mtime_str,
                test_type,
                str(result_dir)
            )
        
        # 显示表格
        console.print(table)
        console.print("\n使用 'api-perf-test show-result <ID>' 命令查看详细结果")
    
    except Exception as e:
        console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
        sys.exit(1)


@app.command("show-result")
def show_result(
    result_id: int = typer.Argument(..., help="结果ID (从list-results命令中获取)"),
) -> None:
    """
    显示指定测试结果的详细信息
    """
    try:
        # 获取结果目录
        results_dir = get_results_directory()
        
        if not results_dir.exists():
            console.print(f"[yellow]结果目录不存在: {results_dir}[/yellow]")
            return
        
        # 获取所有结果目录
        result_dirs = sorted(
            [d for d in results_dir.iterdir() if d.is_dir()], 
            key=lambda d: d.stat().st_mtime, 
            reverse=True
        )
        
        if not result_dirs:
            console.print("[yellow]尚无测试结果[/yellow]")
            return
        
        # 检查结果ID是否有效
        if result_id < 1 or result_id > len(result_dirs):
            console.print(f"[bold red]无效的结果ID:[/bold red] {result_id}")
            console.print(f"有效ID范围: 1-{len(result_dirs)}")
            return
        
        # 获取指定的结果目录
        result_path = result_dirs[result_id - 1]
        
        # 加载结果数据
        result_data = test_runner.load_results(result_path)
        
        if "error" in result_data:
            console.print(f"[bold red]加载结果失败:[/bold red] {result_data['error']}")
            return
        
        # 显示结果数据
        console.print(Panel(
            f"结果目录: [yellow]{result_path}[/yellow]\n"
            f"测试类型: [yellow]{result_data.get('test_type', 'N/A')}[/yellow]\n"
            f"时间: [yellow]{datetime.fromtimestamp(result_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}[/yellow]",
            title="测试信息"
        ))
        
        # 根据测试类型显示不同的信息
        if result_data.get("test_type") == "locust":
            # Locust测试结果
            metrics_panel = Panel(
                f"总请求数: [green]{result_data.get('total_requests', 0)}[/green]\n"
                f"平均响应时间: [green]{result_data.get('average_response_time', 0)}[/green] ms\n"
                f"每秒请求数: [green]{result_data.get('requests_per_second', 0)}[/green]\n"
                f"失败率: [{'red' if result_data.get('failure_rate', 0) > 5 else 'green'}]{result_data.get('failure_rate', 0)}%[/{'red' if result_data.get('failure_rate', 0) > 5 else 'green'}]\n"
                f"测试持续时间: [green]{result_data.get('duration', 0):.1f}[/green] 秒",
                title="性能指标"
            )
            console.print(metrics_panel)
        else:
            # 基础测试结果
            metrics = result_data.get("metrics_summary", {})
            if metrics:
                metrics_panel = Panel(
                    f"并发用户数: [green]{result_data.get('concurrent_users', 0)}[/green]\n"
                    f"计划持续时间: [green]{result_data.get('planned_duration', 0)}[/green] 秒\n"
                    f"实际持续时间: [green]{result_data.get('actual_duration', 0):.1f}[/green] 秒\n"
                    + (f"平均首Token响应时间: [green]{metrics.get('avg_ttft', 0):.3f}[/green] 秒\n" if "avg_ttft" in metrics else "")
                    + (f"平均完整响应时间: [green]{metrics.get('avg_ttct', 0):.3f}[/green] 秒\n" if "avg_ttct" in metrics else "")
                    + (f"成功率: [{'red' if metrics.get('success_rate', 0) < 0.95 else 'green'}]{metrics.get('success_rate', 0) * 100:.1f}%[/{'red' if metrics.get('success_rate', 0) < 0.95 else 'green'}]" if "success_rate" in metrics else ""),
                    title="性能指标"
                )
                console.print(metrics_panel)
            else:
                console.print("[yellow]没有可用的指标摘要[/yellow]")
        
        # 检查HTML报告
        reports_dir = Path("reports")
        if reports_dir.exists():
            # 检查是否有对应的HTML报告
            report_files = list(reports_dir.glob(f"*{result_path.name}*.html"))
            if report_files:
                console.print("\n[bold]已生成的HTML报告:[/bold]")
                for i, report_file in enumerate(report_files, 1):
                    console.print(f"  {i}. [blue]{report_file}[/blue]")
            else:
                # 询问是否生成报告
                if typer.confirm("\n是否生成HTML报告?"):
                    report_path = report_generator.generate_report(result_path)
                    console.print(f"[bold green]报告已生成:[/bold green] {report_path}")
    
    except Exception as e:
        console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
        sys.exit(1)


@app.command("show-logs")
def show_logs(
    num_lines: int = typer.Option(
        50, 
        "--lines", "-n", 
        help="显示日志行数"
    )
) -> None:
    """
    显示测试日志
    """
    try:
        # 获取日志
        logs = test_runner.get_test_logs(num_lines=num_lines)
        
        if not logs or (len(logs) == 1 and logs[0].startswith("无可用日志")):
            console.print("[yellow]没有可用的日志文件[/yellow]")
            return
        
        # 显示日志内容
        console.print(Panel(
            "\n".join(logs),
            title=f"最近 {num_lines} 行日志",
            width=120
        ))
    
    except Exception as e:
        console.print(f"[bold red]发生错误:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def generate_comparison_report(
    result_paths: List[str] = typer.Argument(..., help="测试结果目录路径列表（空格分隔）"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="报告输出路径")
):
    """
    生成多个测试结果的比较报告
    
    对比多个测试结果的性能指标，生成直观的对比图表和性能分析
    """
    logger.info(f"开始生成比较报告，对比 {len(result_paths)} 个测试结果")
    
    if len(result_paths) < 2:
        logger.error("至少需要2个测试结果才能生成比较报告")
        typer.echo("错误: 至少需要2个测试结果才能生成比较报告")
        raise typer.Exit(code=1)
    
    try:
        from api_test_project.visualization.report_generator import report_generator
        
        # 生成比较报告
        report_path = report_generator.generate_comparison_report(result_paths)
        
        # 如果指定了输出路径，复制文件
        if output_path:
            import shutil
            shutil.copy2(report_path, output_path)
            logger.info(f"比较报告已生成: {output_path}")
            typer.echo(f"比较报告已生成: {output_path}")
        else:
            logger.info(f"比较报告已生成: {report_path}")
            typer.echo(f"比较报告已生成: {report_path}")
    
    except Exception as e:
        logger.error(f"生成比较报告失败: {str(e)}", exc_info=True)
        typer.echo(f"错误: 生成比较报告失败: {str(e)}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app() 