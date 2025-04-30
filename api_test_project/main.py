"""
API测试项目主程序入口
"""
from typing import Dict, List, Optional, Union, Any
import os
import time
import asyncio
import argparse
import subprocess
from pathlib import Path
import json
import csv
import random

import typer
from loguru import logger

from api_test_project.api_client.client import ApiClientConfig
from api_test_project.api_client.book_client import BookClient
from api_test_project.metrics.metrics_collector import MetricsCollector
from api_test_project.utils.logging_utils import setup_logging


# 创建Typer应用
app = typer.Typer(help="LLM API并发性能测试工具")

# 配置日志系统
setup_logging(log_dir="logs", test_name="api_test")


@app.command()
def basic(
    tokens_file: str = typer.Option("access_tokens.csv", "--tokens", "-t", help="访问令牌CSV文件路径"),
    concurrent_users: int = typer.Option(10, "--users", "-u", help="并发用户数"),
    test_duration: int = typer.Option(60, "--duration", "-d", help="测试持续时间(秒)"),
    api_url: str = typer.Option("https://server2.dreaminkflora.com/api/v1", "--api-url", help="API基础URL")
):
    """
    执行基础测试，使用内置API客户端
    """
    # 配置日志系统，使用特定的测试名称
    setup_logging(log_dir="logs", test_name="basic_test")
    
    logger.info(f"开始基础测试: {concurrent_users}个并发用户, 持续{test_duration}秒")
    
    # 初始化API客户端配置
    config = ApiClientConfig(
        base_url=api_url,
        tokens_file=tokens_file,
        timeout=6000
    )
    
    # 初始化指标收集器
    metrics_collector = MetricsCollector()
    
    try:
        # 启动测试协程
        asyncio.run(run_basic_test(config, metrics_collector, concurrent_users, test_duration))
        
        # 保存测试结果
        results_path = metrics_collector.save_results("basic_test", concurrent_users)
        logger.info(f"测试完成，结果保存在: {results_path}")
        
    except KeyboardInterrupt:
        logger.warning("测试被用户中断")
    except Exception as e:
        logger.exception(f"测试过程中发生错误: {str(e)}")


@app.command()
def locust(
    tokens_file: str = typer.Option("access_tokens.csv", "--tokens", "-t", help="访问令牌CSV文件路径"),
    host: str = typer.Option("https://server.dreaminkflora.com", "--host", help="API主机"),
    users: int = typer.Option(50, "--users", "-u", help="并发用户数"),
    spawn_rate: int = typer.Option(5, "--spawn-rate", "-r", help="每秒新增用户数"),
    run_time: str = typer.Option("10m", "--time", help="测试运行时间(例如:1h30m)"),
    headless: bool = typer.Option(False, "--headless", help="无界面模式运行"),
    csv_prefix: Optional[str] = typer.Option(None, "--csv", help="CSV结果文件前缀")
):
    """
    启动Locust测试
    """
    # 配置日志系统，使用特定的测试名称
    setup_logging(log_dir="logs", test_name="locust_test")
    
    logger.info(f"启动Locust测试: {users}个用户, 生成速率{spawn_rate}用户/秒")
    
    # 设置环境变量
    os.environ["TOKENS_FILE"] = tokens_file
    
    # 构建Locust命令
    cmd = [
        "locust",
        "-f", "api_test_project/locust_tests/workflow_test.py",
        "--host", host
    ]
    
    if headless:
        cmd.extend([
            "--headless",
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", run_time
        ])
    
    if csv_prefix:
        cmd.extend(["--csv", csv_prefix])
    
    try:
        # 运行Locust进程
        logger.info(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logger.info("Locust测试完成")
    except KeyboardInterrupt:
        logger.warning("测试被用户中断")
    except subprocess.CalledProcessError as e:
        logger.error(f"Locust进程执行失败: {e}")
    except Exception as e:
        logger.exception(f"启动Locust时发生错误: {str(e)}")


@app.command()
def ramp_up(
    tokens_file: str = typer.Option("access_tokens.csv", "--tokens", "-t", help="访问令牌CSV文件路径"),
    start_users: int = typer.Option(10, "--start", "-s", help="起始用户数"),
    max_users: int = typer.Option(2000, "--max", "-m", help="最大用户数"),
    step: int = typer.Option(100, "--step", help="每步增加的用户数"),
    step_duration: int = typer.Option(60, "--step-duration", "-d", help="每步持续时间(秒)"),
    api_url: str = typer.Option("https://server2.dreaminkflora.com/api/v1", "--api-url", help="API基础URL")
):
    """
    执行渐进式加载测试
    从少量用户开始，逐步增加并发用户数，评估系统的扩展性
    """
    # 配置日志系统，使用特定的测试名称
    setup_logging(log_dir="logs", test_name="ramp_up_test")
    
    logger.info(f"开始渐进式加载测试: 从{start_users}用户开始，最大{max_users}用户，步长{step}用户")
    
    # 设置环境变量
    os.environ["TOKENS_FILE"] = tokens_file
    
    # 收集所有步骤的结果
    all_results = []
    
    try:
        for users in range(start_users, max_users + 1, step):
            logger.info(f"==== 测试阶段: {users}个并发用户 ====")
            
            # 为每个阶段构建Locust命令
            cmd = [
                "locust",
                "-f", "api_test_project/locust_tests/workflow_test.py",
                "--host", api_url,
                "--headless",
                "--users", str(users),
                "--spawn-rate", str(min(users // 5, 100)),  # 控制生成速率
                "--run-time", f"{step_duration}s",
                "--csv", f"data/results/ramp_up_{users}_users"
            ]
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 运行当前阶段的测试
            try:
                subprocess.run(cmd, check=True, timeout=step_duration + 60)  # 额外60秒作为缓冲
                
                # 读取结果数据
                stats_file = f"data/results/ramp_up_{users}_users_stats.csv"
                if os.path.exists(stats_file):
                    with open(stats_file, 'r') as f:
                        reader = csv.DictReader(f)
                        stats = next(reader, None)
                        if stats:
                            all_results.append({
                                "users": users,
                                "stats": stats
                            })
                
            except subprocess.TimeoutExpired:
                logger.warning(f"测试阶段 {users}用户 超时")
            except Exception as e:
                logger.error(f"测试阶段 {users}用户 失败: {str(e)}")
            
            # 检查是否应该停止测试
            # 如果错误率超过50%，停止测试
            if all_results and float(all_results[-1]["stats"].get("Fail %", "0").strip("%") or 0) > 50:
                logger.warning(f"错误率过高，在{users}用户时停止测试")
                break
        
        # 保存汇总结果
        if all_results:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            result_path = f"data/results/ramp_up_summary_{timestamp}.json"
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2)
            logger.info(f"渐进式测试完成，结果保存在: {result_path}")
        
    except KeyboardInterrupt:
        logger.warning("测试被用户中断")
    except Exception as e:
        logger.exception(f"渐进式测试过程中发生错误: {str(e)}")


@app.command()
def spike(
    tokens_file: str = typer.Option("access_tokens.csv", "--tokens", "-t", help="访问令牌CSV文件路径"),
    users: int = typer.Option(1000, "--users", "-u", help="峰值用户数"),
    spawn_rate: int = typer.Option(100, "--spawn-rate", "-r", help="每秒新增用户数"),
    duration: int = typer.Option(300, "--duration", "-d", help="测试持续时间(秒)"),
    api_url: str = typer.Option("https://server2.dreaminkflora.com/api/v1", "--api-url", help="API基础URL")
):
    """
    执行峰值压力测试
    模拟突然的高流量场景，评估系统在极端负载下的表现
    """
    # 配置日志系统，使用特定的测试名称
    setup_logging(log_dir="logs", test_name="spike_test")
    
    logger.info(f"开始峰值压力测试: {users}个并发用户, 生成速率{spawn_rate}用户/秒")
    
    # 设置环境变量
    os.environ["TOKENS_FILE"] = tokens_file
    
    # 构建Locust命令
    cmd = [
        "locust",
        "-f", "api_test_project/locust_tests/workflow_test.py",
        "--host", api_url,
        "--headless",
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", f"{duration}s",
        "--csv", f"data/results/spike_test_{users}_users"
    ]
    
    try:
        # 运行测试
        logger.info(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logger.info("峰值压力测试完成")
    except KeyboardInterrupt:
        logger.warning("测试被用户中断")
    except Exception as e:
        logger.exception(f"峰值压力测试过程中发生错误: {str(e)}")


@app.command()
def soak(
    tokens_file: str = typer.Option("access_tokens.csv", "--tokens", "-t", help="访问令牌CSV文件路径"),
    users: int = typer.Option(500, "--users", "-u", help="并发用户数"),
    duration: str = typer.Option("4h", "--duration", "-d", help="测试持续时间(例如:4h)"),
    api_url: str = typer.Option("https://server2.dreaminkflora.com/api/v1", "--api-url", help="API基础URL")
):
    """
    执行持久性能测试
    在较长时间内维持稳定负载，评估系统的稳定性和资源泄漏问题
    """
    # 配置日志系统，使用特定的测试名称
    setup_logging(log_dir="logs", test_name="soak_test")
    
    logger.info(f"开始持久性能测试: {users}个并发用户, 持续{duration}")
    
    # 设置环境变量
    os.environ["TOKENS_FILE"] = tokens_file
    
    # 构建Locust命令
    cmd = [
        "locust",
        "-f", "api_test_project/locust_tests/workflow_test.py",
        "--host", api_url,
        "--headless",
        "--users", str(users),
        "--spawn-rate", str(min(users // 10, 50)),  # 控制生成速率
        "--run-time", duration,
        "--csv", f"data/results/soak_test_{users}_users"
    ]
    
    try:
        # 运行测试
        logger.info(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logger.info("持久性能测试完成")
    except KeyboardInterrupt:
        logger.warning("测试被用户中断")
    except Exception as e:
        logger.exception(f"持久性能测试过程中发生错误: {str(e)}")


async def run_basic_test(
    config: ApiClientConfig,
    metrics_collector: MetricsCollector,
    concurrent_users: int,
    test_duration: int
) -> None:
    """
    运行基础测试
    
    Args:
        config: API客户端配置
        metrics_collector: 指标收集器
        concurrent_users: 并发用户数
        test_duration: 测试持续时间(秒)
    """
    # 创建BookClient实例
    client = BookClient(config)
    client.metrics_collector = metrics_collector
    
    # 获取可用的用户ID列表（手机号）
    user_ids = client.user_ids
    if len(user_ids) < concurrent_users:
        logger.warning(f"可用用户数({len(user_ids)})少于请求的并发用户数({concurrent_users})，将使用全部可用用户")
        concurrent_users = len(user_ids)
    
    # 选择要使用的用户ID (限制为concurrent_users个)
    selected_user_ids = user_ids[:concurrent_users]
    
    # 生成测试用书籍标题
    book_titles = [
        f"测试书籍 {user_id} - {time.strftime('%Y%m%d%H%M%S')}"
        for user_id in selected_user_ids
    ]
    
    # 创建并发任务
    async def user_workflow(idx: int):
        try:
            # 获取用户信息
            user_id = selected_user_ids[idx]
            book_name = book_titles[idx]
            
            # 1. 创建书籍 - 准备参数
            outline_styles = ["年代文"]
            text_styles = ["语言简练（去味版）"]
            outline_style = random.choice(outline_styles)
            text_style = random.choice(text_styles)
            keyword_group_id = "1"  # 使用示例值
            setting_group_id = "1"  # 使用示例值

            logger.info(f"用户 {user_id} 正在创建书籍: {book_name} (风格: {outline_style}/{text_style}, 关键词组: {keyword_group_id}, 设定组: {setting_group_id})")
            book_response = await client.create_book(
                book_name=book_name,
                outline_style=outline_style,
                text_style=text_style,
                keyword_group_id=keyword_group_id,
                setting_group_id=setting_group_id,
                user_id=user_id
            )
            
            if not book_response.success or not book_response.data:
                logger.error(f"用户 {user_id} 创建书籍失败: {book_name}")
                return
            
            # 检查是否使用新的API响应格式（数据在data字段中）
            book_data = book_response.data
            if "data" in book_response.data:
                book_data = book_response.data["data"]
            
            book_id = book_data.get("bookId")
            if not book_id:
                logger.error(f"用户 {user_id} 创建书籍响应中没有bookId: {book_name}")
                return
            
            logger.info(f"用户 {user_id} 成功创建书籍: {book_name}, ID: {book_id}")
            
            # 根据标题生成第一章章纲
            logger.info(f"用户 {user_id} 正在根据标题生成第一章章纲: {book_name}, 风格: {outline_style}")
            first_outline_response = await client.generate_first_chapter_outline(
                book_name=book_name,
                outline_style=outline_style,
                user_id=user_id
            )

            if not first_outline_response.success:
                logger.error(f"用户 {user_id} 生成第一章章纲失败: {book_name}")
                return

            first_outline_length = len(str(first_outline_response.data.get("outline", "")))
            logger.info(f"用户 {user_id} 成功生成第一章章纲: {book_name}, 长度: {first_outline_length} 字符")
            logger.info(f"第一章章纲: {first_outline_response.data.get('outline', '未知')}")
            # 2. 获取书籍信息 (后续流程可能需要调整或移除，因为创建时已包含部分信息)
            logger.info(f"用户 {user_id} 正在获取书籍信息: ID {book_id}")
            book_info_response = await client.get_book_info(book_id, user_id=user_id)
            
            if not book_info_response.success or not book_info_response.data:
                logger.error(f"用户 {user_id} 获取书籍信息失败: ID {book_id}")
                # 即使获取信息失败，后续步骤可能仍可进行，取决于API依赖
                # return # 暂时注释掉，允许继续执行
            else:
                logger.info(f"用户 {user_id} 成功获取书籍信息: ID {book_id}, 标题: {book_info_response.data.get('title', '未知')}")
                
            # 提取章节ID (逻辑保持不变，但可能需要从创建响应获取?)
            chapter_id = None
            if book_info_response.success and "chapters" in book_info_response.data:
                chapters = book_info_response.data["chapters"]
                if chapters:
                    chapter_id = chapters[0].get("chapterId")
                    chapter_title = chapters[0].get("title", "第一章")
                    logger.info(f"用户 {user_id} 找到章节: ID {chapter_id}, 标题: {chapter_title}")
            
            if not chapter_id:
                # 尝试从创建书籍的响应中查找 chapterId
                if book_data and book_data.get("chapters"):
                     initial_chapters = book_data["chapters"]
                     if initial_chapters:
                         chapter_id = initial_chapters[0].get("chapterId")
                         chapter_title = initial_chapters[0].get("title", "第一章") 
                         logger.info(f"用户 {user_id} 从创建响应中找到章节: ID {chapter_id}, 标题: {chapter_title}")
            
            if not chapter_id:
                logger.error(f"用户 {user_id} 无法获取章节ID, 书籍ID: {book_id}")
                return

            # 3. 章纲匹配设定集
            logger.info(f"用户 {user_id} 正在匹配章节设定集: 章节ID {chapter_id}")
            match_settings_response = await client.match_chapter_settings(
                chapter_id=chapter_id,
                scene="outline",
                user_id=user_id
            )

            if not match_settings_response.success:
                logger.error(f"用户 {user_id} 匹配章节设定集失败: 章节ID {chapter_id}")
                # 可以继续执行，因为匹配设定集失败不一定会影响后续流程
                logger.warning(f"用户 {user_id} 将继续处理，但可能缺少设定集支持")
            else:
                logger.info(f"用户 {user_id} 成功匹配章节设定集: 章节ID {chapter_id}")
                if match_settings_response.data:
                    matched_settings = match_settings_response.data.get("settings", [])
                    logger.info(f"匹配到的设定集: {matched_settings}")

            # 4. 章纲扩写
            logger.info(f"用户 {user_id} 正在扩写章节大纲: 章节ID {chapter_id}")
            expanded_outline_response = await client.expand_chapter_outline(
                chapter_id=chapter_id,
                user_id=user_id
            )

            if not expanded_outline_response.success:
                logger.error(f"用户 {user_id} 扩写章节大纲失败: 章节ID {chapter_id}")
                return

            expanded_outline_length = len(str(expanded_outline_response.data.get("expanded_outline", "")))
            logger.info(f"用户 {user_id} 成功扩写章节大纲: 章节ID {chapter_id}, 长度: {expanded_outline_length} 字符")

            # 5. 保存章纲
            expanded_outline = expanded_outline_response.data.get("expanded_outline", "")
            logger.info(f"用户 {user_id} 正在保存章节大纲: 章节ID {chapter_id}")
            save_outline_response = await client.update_chapter_outline(
                chapter_id=chapter_id,
                outline=expanded_outline,
                user_id=user_id
            )

            if not save_outline_response.success:
                logger.error(f"用户 {user_id} 保存章节大纲失败: 章节ID {chapter_id}")
                return

            logger.info(f"用户 {user_id} 成功保存章节大纲: 章节ID {chapter_id}")
            
            # 6. 获取章纲句列表
            logger.info(f"用户 {user_id} 正在获取章纲句列表: 章节ID {chapter_id}")
            sentences_response = await client.get_outline_sentences(
                chapter_id=chapter_id,
                user_id=user_id
            )

            if not sentences_response.success:
                logger.error(f"用户 {user_id} 获取章纲句列表失败: 章节ID {chapter_id}")
                return

            sentences = sentences_response.data.get("data", [])
            sentence_count = len(sentences)
            logger.info(f"用户 {user_id} 成功获取章纲句列表: 章节ID {chapter_id}, 句子数量: {sentence_count}")

            # 7. 章纲句生成正文
            if sentence_count > 0:
                logger.info(f"用户 {user_id} 开始为每个章纲句生成正文")
                
                # 记录所有生成的正文段落
                all_paragraphs = []
                
                # 依次处理每个章纲句
                for sentence in sentences:
                    sentence_id = sentence.get("sentenceId")
                    sentence_text = sentence.get("sentence", "")
                    sentence_order = sentence.get("sentenceOrder", 0)
                    
                    if not sentence_id:
                        logger.warning(f"用户 {user_id} 跳过缺少ID的章纲句")
                        continue
                    
                    logger.info(f"用户 {user_id} 正在处理章纲句 [{sentence_order}]: '{sentence_text}'")
                    
                    # 调用API生成正文
                    generate_response = await client.generate_text_from_sentence(
                        sentence_id=sentence_id,
                        text_style=text_style,  # 使用书籍创建时选择的文本风格
                        user_id=user_id
                    )
                    
                    if not generate_response.success:
                        logger.error(f"用户 {user_id} 为章纲句 {sentence_id} 生成正文失败")
                        continue
                    
                    generated_text = generate_response.data.get("content", "")
                    
                    # 打印章纲句和生成的正文
                    logger.info(f"章纲句 [{sentence_order}]: {sentence_text}")
                    logger.info(f"生成正文: {generated_text}")
                    
                    # 添加到所有段落中
                    all_paragraphs.append({
                        "sentenceId": sentence_id,
                        "sentence": sentence_text,
                        "generatedText": generated_text
                    })
                
                # 所有章纲句处理完毕
                logger.info(f"用户 {user_id} 已完成所有章纲句的正文生成，共 {len(all_paragraphs)} 段")
            else:
                logger.warning(f"用户 {user_id} 没有可用的章纲句，跳过生成正文步骤")
            
            logger.info(f"用户 {user_id} 成功完成全部工作流测试! 书籍ID: {book_id}, 章节ID: {chapter_id}")
            
        except Exception as e:
            logger.exception(f"用户 {user_id} 工作流执行出错: {str(e)}")
    
    # 创建并发任务 - 使用索引来确保从selected_user_ids和book_titles中获取正确的值
    tasks = [asyncio.create_task(user_workflow(i)) for i in range(len(selected_user_ids))]
    
    # 设置超时时间
    done, pending = await asyncio.wait(
        tasks, 
        timeout=test_duration,
        return_when=asyncio.ALL_COMPLETED
    )
    
    # 取消未完成的任务
    for task in pending:
        task.cancel()
    
    # 关闭客户端
    await client.close()
    
    # 输出测试摘要
    summary = metrics_collector.get_session_metrics(concurrent_users)
    avg_ttft_str = f"{summary.avg_ttft:.3f}" if summary.avg_ttft is not None else "N/A"
    avg_ttct_str = f"{summary.avg_ttct:.3f}" if summary.avg_ttct is not None else "N/A"
    logger.info(f"测试摘要: 成功率 {summary.success_count/(summary.success_count+summary.failure_count)*100:.2f}%, "
                f"平均TTFT {avg_ttft_str}秒, 平均TTCT {avg_ttct_str}秒")


if __name__ == "__main__":
    app() 