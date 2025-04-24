#!/usr/bin/env python3
"""
安装脚本
"""
from setuptools import setup, find_packages

# 读取版本号
with open("api_test_project/__init__.py", "r") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"\'')
            break

# 读取README作为长描述
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="llm-api-concurrent-test",
    version=version,
    description="LLM API并发性能测试工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="DreaminkFlora",
    author_email="test@dreaminkflora.ai",
    url="https://github.com/dreaminkflora/llm-api-concurrent-test",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.26.0",
        "asyncio>=3.4.3",
        "pandas>=2.1.4",
        "numpy>=1.26.3",
        "matplotlib>=3.8.2",
        "seaborn>=0.13.1",
        "plotly>=5.18.0",
        "streamlit>=1.30.0",
        "locust>=2.20.1",
        "aiohttp>=3.9.3",
        "typer>=0.9.0",
        "loguru>=0.7.2",
        "pydantic>=2.5.3",
        "tqdm>=4.66.1",
        "python-dotenv>=1.0.1",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "api-test=api_test_project.cli:app",
        ],
    },
) 