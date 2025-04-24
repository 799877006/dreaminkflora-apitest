"""
日志配置工具
提供统一的日志配置和管理功能
"""
from pathlib import Path
from typing import Optional, Union, Dict, Any
import sys
import os

from loguru import logger


def setup_logging(
    log_dir: Union[str, Path] = "logs",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    test_name: Optional[str] = None,
    rotation: str = "100 MB", 
    retention: str = "1 week",
    add_test_details_file: bool = True
) -> None:
    """
    配置日志系统
    
    Args:
        log_dir: 日志文件目录
        console_level: 控制台日志级别
        file_level: 文件日志级别
        test_name: 测试名称，用于日志文件命名
        rotation: 日志文件轮转条件
        retention: 日志保留时间
        add_test_details_file: 是否添加详细测试日志文件
    """
    # 确保日志目录存在
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 移除所有默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        level=console_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    # 文件名前缀
    file_prefix = f"{test_name}_" if test_name else "api_test_"
    
    # 添加主日志文件处理器
    logger.add(
        log_dir / f"{file_prefix}{{time}}.log",
        level=file_level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    
    # 添加详细测试日志处理器
    if add_test_details_file:
        logger.add(
            log_dir / f"{file_prefix}details_{{time}}.txt",
            level=file_level,
            rotation=rotation,
            retention=retention,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
    
    logger.info(f"日志系统已配置，主日志文件保存在: {log_dir}")


def get_logger():
    """获取配置好的logger实例"""
    return logger


def add_log_file(
    filepath: Union[str, Path],
    level: str = "DEBUG",
    format_str: Optional[str] = None
) -> int:
    """
    添加一个新的日志文件
    
    Args:
        filepath: 日志文件路径
        level: 日志级别
        format_str: 格式字符串
        
    Returns:
        处理器ID
    """
    # 确保目录存在
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    # 使用默认格式如果未指定
    if format_str is None:
        format_str = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    
    # 添加日志处理器
    handler_id = logger.add(
        filepath,
        level=level,
        format=format_str
    )
    
    logger.info(f"已添加新日志文件: {filepath}")
    return handler_id 