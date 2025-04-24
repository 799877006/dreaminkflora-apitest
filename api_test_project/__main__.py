"""
主入口模块

使包可以作为模块直接运行：python -m api_test_project
"""
import sys

from api_test_project.cli import app


if __name__ == "__main__":
    sys.exit(app()) 