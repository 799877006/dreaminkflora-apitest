import requests
import csv
import os
import concurrent.futures
import threading

# API地址
url = "https://server2.dreaminkflora.com/api/v1/user/login/password"

# 固定密码
password = "Pwd@1234"

# 手机号范围 (19999998000 到 19999999999，共2000个)
start_phone = 19999998000
end_phone = 19999998000 + 1999

# CSV文件路径
csv_file = "api_test_project/access_tokens.csv"

# 创建或覆盖CSV文件，写入表头
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["手机号", "accessToken"])

# 计数器和锁
success_count = 0
fail_count = 0
counter_lock = threading.Lock()
csv_lock = threading.Lock()

# 处理单个手机号的函数
def process_phone(phone):
    global success_count, fail_count
    
    payload = {
        "phoneNumber": phone,
        "password": password
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            if "data" in data and "accessToken" in data["data"]:
                access_token = data["data"]["accessToken"]
                
                # 使用锁保护写CSV操作
                with csv_lock:
                    with open(csv_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([phone, access_token])
                
                # 使用锁保护计数器更新
                with counter_lock:
                    global success_count
                    success_count += 1
                    print(f"已成功获取 {success_count} 个accessToken")
            else:
                with counter_lock:
                    global fail_count
                    fail_count += 1
                    print(f"手机号 {phone} 无法获取accessToken，响应内容: {data}")
        else:
            with counter_lock:
                fail_count += 1
                print(f"手机号 {phone} 请求失败，状态码: {response.status_code}")
                
    except Exception as e:
        with counter_lock:
            fail_count += 1
            print(f"处理手机号 {phone} 时发生错误: {str(e)}")

# 主函数
def main():
    print(f"开始并发获取{start_phone}到{end_phone}的手机号对应的accessToken...")
    phones = [str(num) for num in range(start_phone, end_phone + 1)]
    
    # 创建线程池，最大工作线程数为20
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        # 提交所有任务
        futures = {executor.submit(process_phone, phone): phone for phone in phones}
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            phone = futures[future]
            try:
                future.result()  # 获取任务结果，如果有异常会在这里抛出
            except Exception as e:
                print(f"处理手机号 {phone} 时出现未捕获的异常: {str(e)}")

    print("\n获取accessToken完成！")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"结果已保存到文件: {os.path.abspath(csv_file)}")

if __name__ == "__main__":
    main()
