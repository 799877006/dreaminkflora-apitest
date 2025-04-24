import requests
import csv

# 基础API地址
base_url = "https://server.dreaminkflora.com/api/v1"
room_id = 66 

tokens = []
try:
    with open('/Users/zhangborui/Personal_Objects/test_api/access_tokens.csv', 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)  # 跳过第一行表头
        for i, row in enumerate(csv_reader):
            if i < 1999:
                tokens.append(row[1])  # 假设token在第一列
            else:
                break
except Exception as e:
    print(f"读取CSV文件出错: {e}")
    exit(1)

# 发送请求让用户加入房间
success_count = 0
for i, token in enumerate(tokens):
    url = f"{base_url}/rooms/{room_id}/join"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            success_count += 1
            print(f"用户 {i+1} 成功加入房间")
        else:
            print(f"用户 {i+1} 加入房间失败: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"用户 {i+1} 请求出错: {e}")

print(f"总计: {success_count}/29 用户成功加入房间")
