"""
基于Streamlit的API测试可视化应用
提供实时测试数据展示和结果分析
"""
import os
import time
import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import threading
import subprocess
import queue

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from api_test_project.test_runner import test_runner
from api_test_project.visualization.report_generator import report_generator

# 设置页面配置
st.set_page_config(
    page_title="LLM API性能测试工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 全局变量，用于线程间通信
output_queue = queue.Queue()
is_test_running = False
test_start_time = None

# 添加调试日志输出
def debug_log(message):
    """打印调试日志到控制台和UI"""
    print(f"[DEBUG] {message}")
    if 'test_output' in st.session_state:
        st.session_state.test_output.append(f"[DEBUG] {message}")

# 全局状态变量
if 'test_process' not in st.session_state:
    st.session_state.test_process = None
if 'test_running' not in st.session_state:
    st.session_state.test_running = False
if 'test_output' not in st.session_state:
    st.session_state.test_output = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None
if 'elapsed_time_str' not in st.session_state:
    st.session_state.elapsed_time_str = "00:00:00"

# 设置目录常量
DATA_DIR = Path("/Users/zhangborui/Personal_Objects/test_api/api_test_project/results")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 自定义CSS
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4e8df5;
        color: white;
    }
    div[data-testid="stSidebarNav"] {
        background-color: rgba(240, 242, 246, 0.3);
        padding: 1rem;
        border-radius: 10px;
    }
    div[data-testid="stTickBarMax"] > div {
        height: 3px;
        background-color: #4e8df5;
    }
    .metric-card {
        background-color: #ffffff;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .red-metric {
        color: #ff4b4b;
    }
    .green-metric {
        color: #00cc96;
    }
</style>
""", unsafe_allow_html=True)


# 页面标题
st.title("LLM API并发性能测试工具")
st.caption("用于测试大语言模型API在高并发场景下的性能表现")

# 添加自动刷新功能
auto_refresh = st.empty()
with auto_refresh.container():
    if st.session_state.test_running:
        st.empty()
        time.sleep(0.5)
        st.experimental_rerun()

# 侧边栏 - 测试控制
with st.sidebar:
    st.header("测试控制")
    
    # 测试类型选择
    test_type = st.selectbox(
        "选择测试类型",
        ["基础测试", "渐进式加载测试", "峰值压力测试", "持久性能测试", "Locust自定义测试"]
    )
    
    # 令牌文件路径
    tokens_file = st.text_input("令牌文件路径", "access_tokens.csv")
    
    # API基础URL
    api_url = st.text_input("API基础URL", "https://server2.dreaminkflora.com/api/v1/")
    
    # 基础测试参数
    if test_type == "基础测试":
        concurrent_users = st.number_input("并发用户数", min_value=1, max_value=2000, value=10)
        test_duration = st.number_input("测试持续时间(秒)", min_value=10, value=60)
        
        cmd = [
            "python", "-m", "api_test_project.main", "basic",
            "--tokens", tokens_file,
            "--users", str(concurrent_users),
            "--duration", str(test_duration),
            "--api-url", api_url
        ]
    
    # 渐进式加载测试参数
    elif test_type == "渐进式加载测试":
        start_users = st.number_input("起始用户数", min_value=1, value=10)
        max_users = st.number_input("最大用户数", min_value=start_users, value=2000)
        step = st.number_input("用户增加步长", min_value=1, value=100)
        step_duration = st.number_input("每步持续时间(秒)", min_value=10, value=60)
        
        cmd = [
            "python", "-m", "api_test_project.main", "ramp_up",
            "--tokens", tokens_file,
            "--start", str(start_users),
            "--max", str(max_users),
            "--step", str(step),
            "--step-duration", str(step_duration),
            "--api-url", api_url
        ]
    
    # 峰值压力测试参数
    elif test_type == "峰值压力测试":
        users = st.number_input("峰值用户数", min_value=1, max_value=2000, value=1000)
        spawn_rate = st.number_input("每秒新增用户数", min_value=1, value=100)
        duration = st.number_input("测试持续时间(秒)", min_value=10, value=300)
        
        cmd = [
            "python", "-m", "api_test_project.main", "spike",
            "--tokens", tokens_file,
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--duration", str(duration),
            "--api-url", api_url
        ]
    
    # 持久性能测试参数
    elif test_type == "持久性能测试":
        users = st.number_input("并发用户数", min_value=1, max_value=2000, value=500)
        hours = st.number_input("持续时间(小时)", min_value=1, value=4)
        duration = f"{hours}h"
        
        cmd = [
            "python", "-m", "api_test_project.main", "soak",
            "--tokens", tokens_file,
            "--users", str(users),
            "--duration", duration,
            "--api-url", api_url
        ]
    
    # Locust自定义测试参数
    else:
        host = st.text_input("主机", "https://server.dreaminkflora.com")
        users = st.number_input("用户数", min_value=1, max_value=2000, value=50)
        spawn_rate = st.number_input("每秒新增用户数", min_value=1, value=10)
        run_time = st.text_input("运行时间(例如:30m, 1h)", "10m")
        headless = st.checkbox("无界面模式", value=True)
        csv_prefix = st.text_input("CSV结果文件前缀", "data/results/locust_test")
        
        cmd = [
            "python", "-m", "api_test_project.main", "locust",
            "--tokens", tokens_file,
            "--host", host,
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--time", run_time,
            "--csv", csv_prefix
        ]
        
        if headless:
            cmd.append("--headless")

    # 启动和停止测试的按钮
    col1, col2 = st.columns(2)
    with col1:
        start_test = st.button("🚀 启动测试", type="primary")
    with col2:
        stop_test = st.button("🛑 停止测试", type="secondary")
    
    # 分隔线
    st.divider()
    
    # 结果分析区域
    st.header("结果分析")
    
    # 结果文件选择
    result_files = []
    if DATA_DIR.exists():
        for item in DATA_DIR.glob("**/summary.json"):
            result_files.append(str(item))
    
    # 如果找到结果文件
    if result_files:
        selected_result = st.selectbox("选择结果文件", sorted(result_files, reverse=True))
        load_result = st.button("加载结果")
    else:
        st.info("未找到测试结果文件")
        selected_result = None
        load_result = False


# 函数: 启动测试进程
def start_test_process(command):
    global is_test_running, test_start_time
    
    if st.session_state.test_running:
        st.warning("测试已在运行中")
        return
    
    debug_log("开始启动测试进程...")
    st.session_state.test_output = []
    st.session_state.test_running = True
    is_test_running = True
    test_start_time = time.time()
    
    # 添加调试信息
    output_queue.put("开始启动测试...")
    debug_log(f"执行命令: {' '.join(command)}")
    output_queue.put(f"执行命令: {' '.join(command)}")
    
    # 创建进程对象
    process = subprocess.Popen(
        command, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    st.session_state.test_process = process
    output_queue.put("测试进程已启动")
    debug_log("测试进程已创建，PID: " + str(process.pid))
    
    # 启动读取输出的线程
    def read_output():
        global is_test_running
        debug_log("启动输出读取线程")
        
        while process.poll() is None and is_test_running:
            line = process.stdout.readline()
            if line:
                line_stripped = line.strip()
                # 输出到控制台
                print(f"[TEST OUTPUT] {line_stripped}")
                
                # 处理用户操作信息，添加突出显示
                if "用户" in line_stripped and ("正在" in line_stripped or "成功" in line_stripped):
                    # 高亮显示用户操作信息
                    output_queue.put(f"🔷 {line_stripped}")
                elif "错误" in line_stripped or "失败" in line_stripped:
                    # 错误信息用红色标记
                    output_queue.put(f"❌ {line_stripped}")
                else:
                    output_queue.put(line_stripped)
            time.sleep(0.1)  # 短暂睡眠，减少CPU使用
        
        # 进程结束
        debug_log("进程已结束或被停止，正在获取剩余输出")
        remaining_output, _ = process.communicate()
        if remaining_output:
            for line in remaining_output.split('\n'):
                if line.strip():
                    line_stripped = line.strip()
                    print(f"[TEST OUTPUT] {line_stripped}")
                    
                    # 处理用户操作信息，添加突出显示
                    if "用户" in line_stripped and ("正在" in line_stripped or "成功" in line_stripped):
                        # 高亮显示用户操作信息
                        output_queue.put(f"🔷 {line_stripped}")
                    elif "错误" in line_stripped or "失败" in line_stripped:
                        # 错误信息用红色标记
                        output_queue.put(f"❌ {line_stripped}")
                    else:
                        output_queue.put(line_stripped)
        
        debug_log("测试已完成，设置状态为未运行")
        is_test_running = False
        st.session_state.test_running = False
    
    thread = threading.Thread(target=read_output)
    thread.daemon = True
    thread.start()
    debug_log("输出读取线程已启动")


# 函数: 停止测试进程
def stop_test_process():
    global is_test_running
    
    if st.session_state.test_process is not None:
        st.session_state.test_process.terminate()
        st.session_state.test_process = None
        st.session_state.test_running = False
        is_test_running = False


# 处理启动测试按钮
if start_test:
    debug_log("用户点击了启动测试按钮")
    output_queue.put("正在准备启动测试...")
    # 创建必要的目录
    data_dir = Path("data/results")
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 修改命令以直接运行python模块
    cmd_str = " ".join(cmd)
    print(f"[CMD] 执行命令: {cmd_str}")
    output_queue.put(f"准备执行命令: {cmd_str}")
    start_test_process(cmd)
    try:
        st.rerun()  # 启动后立即刷新页面
    except:
        debug_log("启动后rerun失败")
        pass

# 处理停止测试按钮
if stop_test:
    output_queue.put("正在停止测试...")
    stop_test_process()
    st.rerun()  # 停止后立即刷新页面


# 函数: 加载测试结果
def load_test_result(result_file):
    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"加载结果文件出错: {str(e)}")
        return None


# 处理加载结果按钮
if load_result and selected_result:
    result_data = load_test_result(selected_result)
    st.session_state.current_result = result_data


# 主页面内容
# 创建标签页
tab1, tab2, tab3, tab4 = st.tabs(["📊 实时监控", "📈 测试结果", "📝 测试日志", "📑 历史对比"])

# 标签页1: 实时监控
with tab1:
    st.header("测试实时监控")
    
    # 状态指示器
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        # 确保状态显示正确
        status = "运行中" if st.session_state.test_running else "未运行"
        status_color = "🟢" if st.session_state.test_running else "🔴"
        debug_log(f"当前测试状态: {status}")
        st.metric("测试状态", f"{status_color} {status}")
    
    with status_col2:
        # 显示运行时间
        st.metric("运行时间", st.session_state.elapsed_time_str)
    
    with status_col3:
        if st.session_state.test_running and len(st.session_state.test_output) > 0:
            request_count = sum(1 for line in st.session_state.test_output if "请求" in line)
            st.metric("请求数", request_count)
        else:
            st.metric("请求数", 0)
    
    # 实时输出区域
    st.subheader("实时输出")
    output_container = st.container(height=400, border=True)
    
    # 更新实时输出
    with output_container:
        if st.session_state.test_output:
            output_text = "\n".join(st.session_state.test_output[-100:])  # 只显示最近100行
            st.code(output_text)
        else:
            st.info("没有测试输出")


# 标签页2: 测试结果
with tab2:
    st.header("测试结果分析")
    
    if st.session_state.current_result:
        result = st.session_state.current_result
        
        # 显示基本指标
        metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
        
        with metrics_col1:
            success_rate = result.get("success_count", 0) / (result.get("success_count", 0) + result.get("failure_count", 0)) * 100 if (result.get("success_count", 0) + result.get("failure_count", 0)) > 0 else 0
            st.metric("成功率", f"{success_rate:.2f}%")
        
        with metrics_col2:
            avg_ttft = result.get("avg_ttft", 0)
            st.metric("平均首Token响应时间", f"{avg_ttft:.3f}秒")
        
        with metrics_col3:
            avg_ttct = result.get("avg_ttct", 0)
            st.metric("平均完整响应时间", f"{avg_ttct:.3f}秒")
        
        with metrics_col4:
            tokens_per_second = result.get("avg_tokens_per_second", 0)
            st.metric("平均每秒Token数", f"{tokens_per_second:.2f}")
        
        # 显示响应时间分布
        st.subheader("响应时间分布")
        dist_col1, dist_col2 = st.columns(2)
        
        # TTFT分布
        with dist_col1:
            ttft_data = {
                "类型": ["P50", "P90", "P95"],
                "时间(秒)": [
                    result.get("p50_ttft", 0),
                    result.get("p90_ttft", 0),
                    result.get("p95_ttft", 0)
                ]
            }
            ttft_df = pd.DataFrame(ttft_data)
            fig = px.bar(
                ttft_df, 
                x="类型", 
                y="时间(秒)",
                title="首Token响应时间(TTFT)分布",
                color="类型",
                color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c"]
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # TTCT分布
        with dist_col2:
            ttct_data = {
                "类型": ["P50", "P90", "P95"],
                "时间(秒)": [
                    result.get("p50_ttct", 0),
                    result.get("p90_ttct", 0),
                    result.get("p95_ttct", 0)
                ]
            }
            ttct_df = pd.DataFrame(ttct_data)
            fig = px.bar(
                ttct_df, 
                x="类型", 
                y="时间(秒)",
                title="完整响应时间(TTCT)分布",
                color="类型",
                color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c"]
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 错误统计
        st.subheader("错误统计")
        error_types = result.get("error_types", {})
        
        if error_types:
            error_data = {
                "错误类型": list(error_types.keys()),
                "数量": list(error_types.values())
            }
            error_df = pd.DataFrame(error_data)
            fig = px.pie(
                error_df,
                values="数量",
                names="错误类型",
                title="错误类型分布",
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("没有错误记录")
        
        # 原始结果数据
        with st.expander("查看原始结果数据"):
            st.json(result)
    
    else:
        st.info("请从侧边栏选择并加载测试结果")


# 标签页3: 测试日志
with tab3:
    st.header("测试日志")
    
    # 查找并列出日志文件
    log_dir = Path("logs")
    log_files = []
    if log_dir.exists():
        for item in log_dir.glob("*.log"):
            log_files.append(str(item))
    
    if log_files:
        selected_log = st.selectbox("选择日志文件", sorted(log_files, reverse=True))
        if selected_log:
            try:
                with open(selected_log, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                # 日志过滤器
                filter_keyword = st.text_input("过滤日志内容(输入关键词)")
                if filter_keyword:
                    filtered_lines = [line for line in log_content.split('\n') if filter_keyword in line]
                    log_content = '\n'.join(filtered_lines)
                
                # 显示日志内容
                st.code(log_content, language="text")
            except Exception as e:
                st.error(f"读取日志文件出错: {str(e)}")
    else:
        st.info("未找到日志文件")


# 标签页4: 历史对比
with tab4:
    st.header("历史测试结果对比")
    
    # 查找所有结果文件
    result_files = []
    if DATA_DIR.exists():
        for item in DATA_DIR.glob("**/summary.json"):
            result_files.append(str(item))
    
    if len(result_files) >= 2:
        # 选择要比较的结果文件
        selected_results = st.multiselect("选择要比较的结果文件(2-5个)", sorted(result_files, reverse=True))
        
        if len(selected_results) >= 2 and len(selected_results) <= 5:
            # 加载所选结果
            results_data = []
            result_labels = []
            
            for result_file in selected_results:
                data = load_test_result(result_file)
                if data:
                    # 提取测试名称或时间戳作为标签
                    parts = Path(result_file).parts
                    test_name = parts[-3] if len(parts) >= 3 else "未知测试"
                    result_labels.append(test_name)
                    results_data.append(data)
            
            if results_data:
                # 比较核心指标
                st.subheader("核心指标对比")
                
                # 准备对比数据
                compare_data = {
                    "测试标签": result_labels,
                    "并发用户数": [d.get("concurrent_users", 0) for d in results_data],
                    "成功率(%)": [d.get("success_count", 0) / max(d.get("success_count", 0) + d.get("failure_count", 0), 1) * 100 for d in results_data],
                    "平均TTFT(秒)": [d.get("avg_ttft", 0) for d in results_data],
                    "平均TTCT(秒)": [d.get("avg_ttct", 0) for d in results_data],
                    "每秒Token数": [d.get("avg_tokens_per_second", 0) for d in results_data]
                }
                
                compare_df = pd.DataFrame(compare_data)
                st.dataframe(compare_df, use_container_width=True)
                
                # 生成详细比较报告的按钮
                if st.button("📊 生成详细比较报告", type="primary"):
                    with st.spinner("正在生成比较报告..."):
                        try:
                            report_path = report_generator.generate_comparison_report(selected_results)
                            st.success(f"比较报告已生成: {report_path}")
                            
                            # 提供下载链接
                            with open(report_path, "r", encoding="utf-8") as f:
                                report_html = f.read()
                            
                            st.download_button(
                                label="下载比较报告",
                                data=report_html,
                                file_name=Path(report_path).name,
                                mime="text/html"
                            )
                        except Exception as e:
                            st.error(f"生成比较报告失败: {str(e)}")
                
                # 可视化对比
                metrics_to_plot = ["成功率(%)", "平均TTFT(秒)", "平均TTCT(秒)", "每秒Token数"]
                selected_metric = st.selectbox("选择要对比的指标", metrics_to_plot)
                
                # 绘制对比图
                fig = px.bar(
                    compare_df,
                    x="测试标签",
                    y=selected_metric,
                    title=f"{selected_metric}对比",
                    color="测试标签",
                    text_auto='.2f'
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
                
                # 随并发用户数变化的性能曲线
                if len(selected_results) >= 3 and "ramp_up" in "".join(result_labels):
                    st.subheader("性能曲线")
                    
                    # 创建折线图
                    fig = go.Figure()
                    
                    for i, data in enumerate(results_data):
                        fig.add_trace(go.Scatter(
                            x=[data.get("concurrent_users", 0)],
                            y=[data.get("avg_ttft", 0)],
                            mode="lines+markers",
                            name=f"{result_labels[i]} - TTFT"
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=[data.get("concurrent_users", 0)],
                            y=[data.get("avg_ttct", 0)],
                            mode="lines+markers",
                            name=f"{result_labels[i]} - TTCT",
                            line=dict(dash="dash")
                        ))
                    
                    fig.update_layout(
                        title="响应时间随并发用户数变化",
                        xaxis_title="并发用户数",
                        yaxis_title="响应时间(秒)",
                        height=500
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.warning("无法加载所选结果文件")
        
        elif len(selected_results) == 1:
            st.warning("请至少选择2个结果文件进行比较")
        elif len(selected_results) > 5:
            st.warning("最多只能比较5个结果文件")
    
    else:
        st.info("需要至少两个测试结果才能进行比较")


# 实时更新运行时间
def update_elapsed_time():
    global is_test_running, test_start_time
    
    while is_test_running:
        if test_start_time is not None:
            elapsed = time.time() - test_start_time
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)
            formatted_time = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            # 不直接更新session_state，而是通过队列
            output_queue.put(f"ELAPSED_TIME:{formatted_time}")
        time.sleep(1)

# 更新输出的辅助函数
def update_output():
    # 从队列中读取输出并更新UI
    try:
        items_processed = 0
        updates_made = False
        
        while not output_queue.empty() and items_processed < 100:  # 限制每次处理的项目数
            line = output_queue.get_nowait()
            items_processed += 1
            updates_made = True
            
            # 特殊消息处理
            if line.startswith("ELAPSED_TIME:"):
                st.session_state.elapsed_time_str = line[13:]  # 提取时间字符串
            else:
                st.session_state.test_output.append(line)
            
            output_queue.task_done()
        
        # 只有当有更新时才刷新
        if updates_made:
            debug_log(f"处理了{items_processed}条消息")
            try:
                st.rerun()  # 如果有更新，则刷新页面
            except:
                debug_log("rerun失败，继续运行")
                pass
    except Exception as e:
        error_msg = f"更新输出时发生错误: {str(e)}"
        print(error_msg)
        st.error(error_msg)

# 在每次页面加载时检查队列
update_output()

# 如果测试正在运行但没有启动时间更新线程
if st.session_state.test_running and not is_test_running:
    debug_log("检测到状态不一致，同步测试状态")
    is_test_running = True
    test_start_time = time.time()
    output_queue.put("恢复测试状态...")
    
    # 启动时间更新线程
    elapsed_time_thread = threading.Thread(target=update_elapsed_time)
    elapsed_time_thread.daemon = True
    elapsed_time_thread.start()


# 页脚
st.divider()
st.caption("LLM API并发性能测试工具 © 2023") 