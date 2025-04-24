"""
基于Locust的完整工作流测试

模拟用户行为的完整工作流测试，包括：
1. 创建书籍
2. 获取书籍信息
3. 更新书籍风格
4. 生成章节大纲
5. 生成章节内容
6. 生成前文梗概
等操作
"""
import os
import time
import random
import asyncio
import json
from typing import Dict, List, Optional, Any

from locust import HttpUser, task, between, events
import gevent
from loguru import logger

# 配置loguru
logger.add("logs/locust_test_{time}.log", rotation="100 MB")

# 书籍风格
BOOK_STYLES = [
    "玄幻奇幻", "武侠仙侠", "都市青春", "历史军事", 
    "游戏竞技", "科幻灵异", "恐怖悬疑", "古言架空",
    "豪门总裁", "穿越重生", "轻松搞笑"
]

# 书籍标题模板
BOOK_TITLE_TEMPLATES = [
    "在{setting}成为{role}的日子",
    "{role}的{setting}传说",
    "我与{role}的{setting}奇遇",
    "{setting}中的{role}",
    "当{role}闯入{setting}",
    "{role}：{setting}的守护者",
    "{setting}秘闻：{role}的崛起",
    "{role}的{setting}历险记"
]

# 设定
SETTINGS = [
    "魔法学院", "古代王朝", "星际战场", "末日废土", "虚拟游戏", 
    "现代都市", "神秘村庄", "古老森林", "海底王国", "蒸汽朋克城市",
    "修真门派", "科技公司", "皇家宫廷", "荒芜沙漠", "浮空岛屿"
]

# 角色
ROLES = [
    "天才少年", "落魄公主", "神秘剑客", "失忆将军", "双面间谍",
    "魔法师", "继承人", "考古学家", "异能者", "龙骑士",
    "复仇者", "游侠", "守护者", "预言者", "流浪诗人"
]

# 关键词组
KEYWORDS_LIST = [
    ["冒险", "宝藏", "地图", "危险", "勇气"],
    ["背叛", "阴谋", "权力", "欺骗", "真相"],
    ["魔法", "咒语", "神器", "禁忌", "力量"],
    ["情报", "潜入", "追击", "伪装", "秘密行动"],
    ["决斗", "荣誉", "剑术", "挑战", "武道"],
    ["实验", "发明", "科技", "突破", "危险"],
    ["爱情", "误会", "相遇", "阻碍", "命运"],
    ["任务", "委托", "奖励", "难题", "团队"],
    ["远古", "遗迹", "文明", "发现", "秘密"],
    ["修炼", "突破", "瓶颈", "传承", "机缘"]
]


class BookWorkflowUser(HttpUser):
    """
    模拟书籍工作流的用户类
    """
    wait_time = between(3, 8)  # 任务间等待时间（秒）
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.book_id = None
        self.chapter_id = None
        self.chapter_content = None
        self.chapter_outline = None
    
    def on_start(self):
        """用户开始时执行的操作"""
        self.token = self._get_random_token()
        if not self.token:
            logger.error("无法获取访问令牌，用户无法启动")
            return
        
        logger.info(f"用户已初始化，使用令牌: {self.token[:10]}...")

    def _get_random_token(self) -> Optional[str]:
        """获取随机访问令牌"""
        tokens_file = os.environ.get("TOKENS_FILE", "access_tokens.csv")
        try:
            import csv
            with open(tokens_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # 跳过表头
                tokens = [row[1] for row in reader if len(row) > 1]
                if tokens:
                    return random.choice(tokens)
        except Exception as e:
            logger.error(f"读取令牌文件出错: {e}")
        return None
    
    def _generate_book_title(self) -> str:
        """生成随机书籍标题"""
        template = random.choice(BOOK_TITLE_TEMPLATES)
        setting = random.choice(SETTINGS)
        role = random.choice(ROLES)
        return template.format(setting=setting, role=role)
    
    def _get_random_style(self) -> str:
        """获取随机书籍风格"""
        return random.choice(BOOK_STYLES)
    
    def _get_random_keywords(self) -> List[str]:
        """获取随机关键词组"""
        return random.choice(KEYWORDS_LIST)
    
    @task(1)
    def complete_workflow(self):
        """
        完整的工作流测试
        按顺序执行从创建书籍到生成内容的完整流程
        """
        if not self.token:
            logger.error("用户没有有效的访问令牌")
            return
        
        # 生成书籍标题
        title = self._generate_book_title()
        logger.info(f"开始完整工作流测试: {title}")
        
        # 1. 创建书籍
        self.create_book(title)
        if not self.book_id:
            logger.error("创建书籍失败，中止工作流")
            return
        
        # 2. 获取书籍信息
        self.get_book_info()
        
        # 3. 更新书籍风格
        outline_style = self._get_random_style()
        text_style = self._get_random_style()
        self.update_book_style(outline_style, text_style)
        
        # 4. 生成章节大纲
        if self.chapter_id:
            keywords = self._get_random_keywords()
            self.generate_chapter_outline(keywords)
            
            # 5. 生成章节内容
            self.generate_chapter_content()
            
            # 6. 生成前文梗概
            self.generate_chapter_background()
        
        logger.info(f"完整工作流测试完成: {title}")
    
    @task(2)
    def create_book_task(self):
        """创建书籍任务"""
        if not self.token:
            return
        
        title = self._generate_book_title()
        self.create_book(title)
    
    @task(3)
    def generate_outline_task(self):
        """生成章节大纲任务"""
        if not self.token or not self.chapter_id:
            return
        
        keywords = self._get_random_keywords()
        self.generate_chapter_outline(keywords)
    
    @task(4)
    def generate_content_task(self):
        """生成章节内容任务"""
        if not self.token or not self.chapter_id:
            return
        
        self.generate_chapter_content()
    
    @task(1)
    def generate_background_task(self):
        """生成前文梗概任务"""
        if not self.token or not self.chapter_id:
            return
        
        self.generate_chapter_background()
    
    def create_book(self, title: str):
        """
        创建书籍
        
        Args:
            title: 书籍标题
        """
        # 记录开始时间
        start_time = time.time()
        first_byte_time = None
        
        with self.client.post(
            "/homepage/books/save",
            json={
                "saveId": title,
                "chapterFormat": "第*章"
            },
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="创建书籍"
        ) as response:
            first_byte_time = time.time()
            try:
                if response.status_code == 200:
                    data = response.json()
                    self.book_id = data.get("bookId")
                    logger.info(f"创建书籍成功: {title}, ID: {self.book_id}")
                    response.success()
                    
                    # 记录TTFT和TTCT
                    ttft = first_byte_time - start_time
                    ttct = time.time() - start_time
                    events.request.fire(
                        request_type="POST",
                        name="创建书籍",
                        response_time=ttct * 1000,  # 转换为毫秒
                        response_length=len(response.text),
                        context={
                            "ttft": ttft,
                            "success": True
                        }
                    )
                else:
                    error_msg = f"创建书籍失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    response.failure(error_msg)
            except Exception as e:
                logger.exception(f"创建书籍请求出错: {str(e)}")
                response.failure(f"请求异常: {str(e)}")
    
    def get_book_info(self):
        """获取书籍信息"""
        if not self.book_id:
            return
        
        with self.client.get(
            f"/quick-entries/books/{self.book_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="获取书籍信息"
        ) as response:
            try:
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "chapters" in data["data"]:
                        chapters = data["data"]["chapters"]
                        if chapters:
                            # 获取第一个章节
                            self.chapter_id = chapters[0].get("chapterId")
                            logger.info(f"获取到章节ID: {self.chapter_id}")
                    response.success()
                else:
                    error_msg = f"获取书籍信息失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    response.failure(error_msg)
            except Exception as e:
                logger.exception(f"获取书籍信息请求出错: {str(e)}")
                response.failure(f"请求异常: {str(e)}")
    
    def update_book_style(self, outline_style: str, text_style: str):
        """
        更新书籍风格
        
        Args:
            outline_style: 章纲风格
            text_style: 正文风格
        """
        if not self.book_id:
            return
        
        with self.client.patch(
            f"/quick-entries/books/{self.book_id}",
            json={
                "outlineStyle": outline_style,
                "textStyle": text_style
            },
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="更新书籍风格"
        ) as response:
            try:
                if response.status_code == 200:
                    logger.info(f"更新书籍风格成功: {self.book_id}")
                    response.success()
                else:
                    error_msg = f"更新书籍风格失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    response.failure(error_msg)
            except Exception as e:
                logger.exception(f"更新书籍风格请求出错: {str(e)}")
                response.failure(f"请求异常: {str(e)}")
    
    def generate_chapter_outline(self, keywords: List[str]):
        """
        生成章节大纲
        
        Args:
            keywords: 关键词列表
        """
        if not self.chapter_id:
            return
        
        # 记录开始时间
        start_time = time.time()
        first_byte_time = None
        complete_text = ""
        
        # 注意：Locust不直接支持SSE/流式请求的监控，需要手动处理
        with self.client.post(
            f"/sse/chapters/{self.chapter_id}/outline",
            json={
                "outlineStyle": self._get_random_style(),
                "keywords": keywords
            },
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "text/event-stream"
            },
            stream=True,
            catch_response=True,
            name="生成章节大纲"
        ) as response:
            first_byte_time = time.time()
            try:
                if response.status_code == 200:
                    # 手动处理SSE流
                    for line in response.iter_lines():
                        if not line:
                            continue
                        
                        try:
                            line_str = line.decode('utf-8')
                            if line_str.startswith("data:"):
                                data_json = line_str[5:].strip()
                                data = json.loads(data_json)
                                token = data.get("content", "")
                                complete_text += token
                        except Exception as e:
                            logger.error(f"解析流数据出错: {str(e)}")
                    
                    # 流处理完成
                    self.chapter_outline = complete_text
                    logger.info(f"生成章节大纲成功: {self.chapter_id}, 长度: {len(complete_text)}")
                    response.success()
                    
                    # 记录TTFT和TTCT
                    ttft = first_byte_time - start_time
                    ttct = time.time() - start_time
                    token_count = len(complete_text)
                    events.request.fire(
                        request_type="POST",
                        name="生成章节大纲",
                        response_time=ttct * 1000,  # 转换为毫秒
                        response_length=len(complete_text),
                        context={
                            "ttft": ttft,
                            "token_count": token_count,
                            "success": True
                        }
                    )
                else:
                    error_msg = f"生成章节大纲失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    response.failure(error_msg)
            except Exception as e:
                logger.exception(f"生成章节大纲请求出错: {str(e)}")
                response.failure(f"请求异常: {str(e)}")
    
    def generate_chapter_content(self, position: str = "tail"):
        """
        生成章节内容
        
        Args:
            position: 生成位置（尾部或头部）
        """
        if not self.chapter_id:
            return
        
        # 记录开始时间
        start_time = time.time()
        first_byte_time = None
        complete_text = ""
        
        with self.client.get(
            f"/sse/chapters/{self.chapter_id}/{position}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "text/event-stream"
            },
            stream=True,
            catch_response=True,
            name="生成章节内容"
        ) as response:
            first_byte_time = time.time()
            try:
                if response.status_code == 200:
                    # 手动处理SSE流
                    for line in response.iter_lines():
                        if not line:
                            continue
                        
                        try:
                            line_str = line.decode('utf-8')
                            if line_str.startswith("data:"):
                                data_json = line_str[5:].strip()
                                data = json.loads(data_json)
                                token = data.get("content", "")
                                complete_text += token
                        except Exception as e:
                            logger.error(f"解析流数据出错: {str(e)}")
                    
                    # 流处理完成
                    self.chapter_content = complete_text
                    logger.info(f"生成章节内容成功: {self.chapter_id}, 长度: {len(complete_text)}")
                    response.success()
                    
                    # 记录TTFT和TTCT
                    ttft = first_byte_time - start_time
                    ttct = time.time() - start_time
                    token_count = len(complete_text)
                    events.request.fire(
                        request_type="GET",
                        name="生成章节内容",
                        response_time=ttct * 1000,  # 转换为毫秒
                        response_length=len(complete_text),
                        context={
                            "ttft": ttft,
                            "token_count": token_count,
                            "success": True
                        }
                    )
                else:
                    error_msg = f"生成章节内容失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    response.failure(error_msg)
            except Exception as e:
                logger.exception(f"生成章节内容请求出错: {str(e)}")
                response.failure(f"请求异常: {str(e)}")
    
    def generate_chapter_background(self):
        """生成章节前文梗概"""
        if not self.chapter_id:
            return
        
        # 记录开始时间
        start_time = time.time()
        first_byte_time = None
        complete_text = ""
        
        with self.client.get(
            f"/sse/chapters/{self.chapter_id}/background",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "text/event-stream"
            },
            stream=True,
            catch_response=True,
            name="生成前文梗概"
        ) as response:
            first_byte_time = time.time()
            try:
                if response.status_code == 200:
                    # 手动处理SSE流
                    for line in response.iter_lines():
                        if not line:
                            continue
                        
                        try:
                            line_str = line.decode('utf-8')
                            if line_str.startswith("data:"):
                                data_json = line_str[5:].strip()
                                data = json.loads(data_json)
                                token = data.get("content", "")
                                complete_text += token
                        except Exception as e:
                            logger.error(f"解析流数据出错: {str(e)}")
                    
                    # 流处理完成
                    logger.info(f"生成前文梗概成功: {self.chapter_id}, 长度: {len(complete_text)}")
                    response.success()
                    
                    # 记录TTFT和TTCT
                    ttft = first_byte_time - start_time
                    ttct = time.time() - start_time
                    token_count = len(complete_text)
                    events.request.fire(
                        request_type="GET",
                        name="生成前文梗概",
                        response_time=ttct * 1000,  # 转换为毫秒
                        response_length=len(complete_text),
                        context={
                            "ttft": ttft,
                            "token_count": token_count,
                            "success": True
                        }
                    )
                else:
                    error_msg = f"生成前文梗概失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    response.failure(error_msg)
            except Exception as e:
                logger.exception(f"生成前文梗概请求出错: {str(e)}")
                response.failure(f"请求异常: {str(e)}")


# 自定义指标收集
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Locust初始化时注册监听器"""
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    # 初始化自定义指标容器
    environment.stats.ttft_values = {}
    environment.stats.token_counts = {}
    
    # 添加请求完成监听器
    @events.request.add_listener
    def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
        """请求完成时收集TTFT和token数等指标"""
        if context is None:
            return
        
        ttft = context.get("ttft")
        token_count = context.get("token_count")
        success = context.get("success", False)
        
        # 只统计成功请求的指标
        if not success:
            return
        
        # 记录TTFT
        if ttft is not None:
            if name not in environment.stats.ttft_values:
                environment.stats.ttft_values[name] = []
            environment.stats.ttft_values[name].append(ttft)
        
        # 记录token数
        if token_count is not None:
            if name not in environment.stats.token_counts:
                environment.stats.token_counts[name] = []
            environment.stats.token_counts[name].append(token_count) 