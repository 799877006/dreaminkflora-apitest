# LLM API 并发性能测试工具

本项目是一个用于测试大语言模型(LLM) API并发性能的工具包，主要关注在高并发场景下API的性能表现。

## 功能特点

- **完整工作流测试**：支持创建书籍、写章纲、续写、扩写、章纲生成写正文、总结前文梗概等全流程API测试
- **高并发测试**：支持模拟最多2000名并发用户
- **性能指标监控**：测量首token返回时间(TTFT)、完整响应时间(TTCT)、吞吐量等关键指标
- **多种测试模式**：支持渐进式加载测试、峰值压力测试、持久性能测试等
- **实时数据可视化**：通过Streamlit界面实时展示测试结果和性能指标
- **全面的测试报告**：生成详细的测试报告，包括成功率、错误类型统计等
- **多测试结果比较**：支持多个测试结果的对比分析，自动生成对比报告和性能趋势图表

## 项目结构

```
api_test_project/
├── __init__.py          # 包初始化文件
├── __main__.py          # 主入口点
├── cli.py               # 命令行接口
├── test_runner.py       # 测试运行器
├── api_client/          # API客户端实现
│   ├── __init__.py
│   ├── client.py        # 基础API客户端
│   └── book_client.py   # 书籍API客户端
├── locust_tests/        # Locust测试脚本
│   └── workflow_test.py # 完整工作流测试
├── metrics/             # 性能指标收集和分析
│   ├── __init__.py
│   └── metrics_collector.py
├── models/              # 数据模型定义
│   ├── __init__.py
│   └── response_models.py
├── visualization/       # 数据可视化组件
│   ├── __init__.py
│   ├── report_generator.py  # 报告生成器
│   └── templates/      # 报告模板
│       ├── basic_report_template.html    # 基础报告模板
│       ├── locust_report_template.html   # Locust报告模板
│       └── comparison_report_template.html  # 比较报告模板
└── streamlit_app.py     # Streamlit应用界面
```

## 安装

### 使用pip安装

```bash
pip install llm-api-concurrent-test
```

### 从源码安装

```bash
git clone https://github.com/dreaminkflora/llm-api-concurrent-test.git
cd llm-api-concurrent-test
pip install -e .
```

## 快速开始

### 1. 配置API密钥

首先创建一个访问令牌文件 `access_tokens.csv`：

```csv
user_id,token
user1,your_api_token_1
user2,your_api_token_2
```

### 2. 运行基础测试

使用命令行运行基础性能测试：

```bash
api-test basic --users 10 --duration 60 --test-type response_time
```

### 3. 运行Locust测试

运行Locust高并发测试：

```bash
api-test locust --test-type spike --users 100 --spawn-rate 10 --run-time 5m
```

### 4. 启动可视化界面

启动Streamlit可视化界面：

```bash
streamlit run api_test_project/streamlit_app.py
```

## 命令行用法

```
api-test [COMMAND] [OPTIONS]
```

### 可用命令：

- **basic**: 运行基础性能测试
  ```
  api-test basic --test-type response_time --users 10 --duration 60 --workflow basic
  ```

- **locust**: 运行Locust负载测试
  ```
  api-test locust --test-type spike --users 100 --spawn-rate 10 --run-time 5m
  ```

- **stop**: 停止当前运行的测试
  ```
  api-test stop [--force]
  ```

- **status**: 检查当前测试状态
  ```
  api-test status
  ```

- **results**: 列出最近的测试结果
  ```
  api-test results --limit 5
  ```

- **show**: 显示指定测试结果的详细信息
  ```
  api-test show results/basic_test_response_time_20240521_123456
  ```

- **logs**: 显示测试日志
  ```
  api-test logs --lines 20
  ```

- **generate-report**: 为测试结果生成报告
  ```
  api-test generate-report results/basic_test_response_time_20240521_123456 --output report.html
  ```

- **generate-comparison-report**: 生成多个测试结果的比较报告
  ```
  api-test generate-comparison-report results/test1 results/test2 results/test3 --output comparison.html
  ```

## 测试类型

### 基础测试类型

- **response_time**: 响应时间测试，关注API在不同负载下的响应速度
- **throughput**: 吞吐量测试，关注API在一定时间内能处理的最大请求数
- **ttft**: 首Token响应时间测试，针对流式API的关键指标

### Locust测试类型

- **spike**: 峰值压力测试，模拟突然的高流量场景
- **ramp-up**: 渐进式加载测试，逐步增加负载以确定系统极限
- **soak**: 持久性能测试，在较长时间内维持稳定负载测试系统稳定性

## 工作流类型

- **basic**: 基础工作流，包含创建书籍、生成大纲、生成内容等基本操作
- **advanced**: 高级工作流，包含多书籍并行操作、长上下文维护测试等

## 测试报告功能

### 基础测试报告

基础测试报告包含以下内容：

- **测试配置信息**：测试类型、并发用户数、持续时间等
- **性能指标摘要**：平均响应时间、吞吐量、成功率等关键指标
- **响应时间分析**：TTFT和TTCT的分布图和时序图
- **吞吐量分析**：每秒Token数的分布和变化趋势
- **错误分析**：错误类型分布和时序变化

### Locust测试报告

Locust测试报告包含以下内容：

- **测试配置信息**：用户数、生成速率、运行时间等
- **请求统计表格**：各端点的请求数、失败数、响应时间等
- **响应时间图表**：不同百分位的响应时间随时间变化
- **请求率和用户数图表**：RPS和并发用户数随时间变化
- **失败率图表**：每秒失败数随时间变化

### 比较测试报告

比较测试报告支持对多个测试结果进行对比分析：

- **测试信息对比**：展示各测试的基本配置和执行时间
- **关键指标对比**：使用表格和图表对比多个测试的性能指标
- **性能雷达图**：使用雷达图直观展示多个测试在不同维度的表现
- **响应时间对比**：对比不同测试的TTFT和TTCT
- **吞吐量和成功率对比**：对比不同测试的处理能力和稳定性
- **变化百分比**：计算关键指标的变化百分比，突出性能提升或下降
- **优化建议**：基于对比结果自动生成优化建议

## 开发指南

### 环境设置

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码格式化
ruff format api_test_project/
```

### 添加新的测试类型

1. 在 `test_runner.py` 中扩展 `TestRunner` 类
2. 在 `cli.py` 中添加新的命令和参数
3. 在 `metrics_collector.py` 中添加相应的指标收集逻辑

### 扩展可视化功能

1. 在 `visualization/templates/` 目录中添加新的HTML模板
2. 在 `report_generator.py` 中添加新的报告生成方法
3. 更新 `cli.py` 和 `streamlit_app.py` 以支持新的可视化功能

## 报告示例

### 生成单个测试报告

```python
from api_test_project.visualization.report_generator import report_generator

# 生成测试报告
report_path = report_generator.generate_report(
    result_path="results/locust_spike_20240521_123456"
)
print(f"报告已生成: {report_path}")
```

### 生成比较测试报告

```python
from api_test_project.visualization.report_generator import report_generator

# 生成比较报告
report_path = report_generator.generate_comparison_report([
    "results/test1_20240521_123456",
    "results/test2_20240522_123456",
    "results/test3_20240523_123456"
])
print(f"比较报告已生成: {report_path}")
```

## 许可证

MIT License 