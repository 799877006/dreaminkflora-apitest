"""
书籍API客户端实现模块，处理与书籍相关的API调用
"""
from typing import Any, Dict, List, Optional, Union
import asyncio

from loguru import logger

from api_test_project.api_client.client import LlmApiClient, ApiClientConfig
from api_test_project.models.response_models import ApiResponse, TokenStreamEvent


class BookClient(LlmApiClient):
    """
    书籍API客户端类
    实现与书籍相关的API调用
    """
    
    def __init__(self, config: Optional[ApiClientConfig] = None):
        """
        初始化书籍API客户端
        
        Args:
            config: API客户端配置
        """
        super().__init__(config or ApiClientConfig())
    
    async def create_book(
        self, 
        book_name: str, 
        outline_style: str, 
        text_style: str, 
        keyword_group_id: str, # 使用 str 类型，因为示例中是字符串 "4"
        setting_group_id: str,  # 使用 str 类型，因为示例中是字符串 "1"
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        创建新书籍 (使用详细参数)
        
        Args:
            book_name: 书籍名称
            outline_style: 章纲风格
            text_style: 正文风格
            keyword_group_id: 关键词组ID
            setting_group_id: 设定组ID
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象，成功时data中包含book_id
        """
        data = {
            "bookName": book_name,
            "outlineStyle": outline_style,
            "textStyle": text_style,
            "keywordGroupId": keyword_group_id,
            "settingGroupId": setting_group_id
        }
        
        logger.info(f"创建书籍: {book_name}, 大纲风格: {outline_style}, 文本风格: {text_style}")
        response = await self.post("/homepage/book", data=data, user_id=user_id)
        
        if response.success and response.data:
            # 新的API响应格式，数据存放在data字段中
            if "data" in response.data:
                book_data = response.data["data"]
                book_id = book_data.get("bookId")
                if book_id:
                    logger.info(f"书籍创建成功，ID: {book_id}")
                else:
                    logger.warning("书籍创建成功，但未返回bookId")
            else:
                book_id = response.data.get("bookId")
                if book_id:
                    logger.info(f"书籍创建成功，ID: {book_id}")
                else:
                    logger.warning("书籍创建成功，但未返回bookId")
        elif response.error:
            logger.error(f"创建书籍失败: {response.error.status_code} - {response.error.message}")
        else:
            logger.error("创建书籍失败: 未知错误或无响应内容")

        return response
    
    async def get_book_info(self, book_id: int, user_id: Optional[str] = None) -> ApiResponse:
        """
        获取书籍信息
        
        Args:
            book_id: 书籍ID
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象，成功时data中包含书籍信息
        """
        logger.info(f"获取书籍信息: {book_id}")
        return await self.get(f"/quick-entries/books/{book_id}", user_id=user_id)
    
    async def update_book_style(
        self, 
        book_id: int, 
        outline_style: str,
        text_style: str,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        更新书籍风格
        
        Args:
            book_id: 书籍ID
            outline_style: 章纲风格
            text_style: 正文风格
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        data = {
            "outlineStyle": outline_style,
            "textStyle": text_style
        }
        
        logger.info(f"更新书籍风格: {book_id}, 章纲风格: {outline_style}, 正文风格: {text_style}")
        return await self.patch(f"quick-entries/books/{book_id}", data=data, user_id=user_id)
    
    async def generate_chapter_outline(
        self, 
        chapter_id: int, 
        outline_style: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        生成章节大纲
        
        Args:
            chapter_id: 章节ID
            outline_style: 大纲风格
            keywords: 大纲关键词
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        data = {}
        if outline_style:
            data["outlineStyle"] = outline_style
        if keywords:
            data["keywords"] = keywords
            
        logger.info(f"生成章节大纲: 章节ID {chapter_id}")
        response = await self.post(f"/sse/chapters/{chapter_id}/outline", data=data, stream=True, user_id=user_id)
        
        # 处理流式响应
        complete_text = ""
        async for event in response:
            if event.event_type == "token" and event.data:
                token = event.data.get("token", "")
                complete_text += token
                
            elif event.event_type == "error":
                logger.error(f"生成章节大纲出错: {event.data}")
                return ApiResponse(
                    success=False, 
                    error=event.data
                )
        
        logger.info(f"章节大纲生成完成: {chapter_id}, 长度: {len(complete_text)}")
        return ApiResponse(
            success=True,
            data={"outline": complete_text}
        )
    
    async def generate_chapter_content(
        self, 
        chapter_id: int, 
        position: str = "tail",  # "tail" 或 "head"
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        生成章节内容
        
        Args:
            chapter_id: 章节ID
            position: 生成位置（尾部或头部）
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        logger.info(f"生成章节内容: 章节ID {chapter_id}, 位置: {position}")
        response = await self.get(f"sse/chapters/{chapter_id}/{position}", stream=True, user_id=user_id)
        
        # 处理流式响应
        complete_text = ""
        async for event in response:
            if event.event_type == "token" and event.data:
                token = event.data.get("token", "")
                complete_text += token
                
            elif event.event_type == "error":
                logger.error(f"生成章节内容出错: {event.data}")
                return ApiResponse(
                    success=False, 
                    error=event.data
                )
        
        logger.info(f"章节内容生成完成: {chapter_id}, 长度: {len(complete_text)}")
        return ApiResponse(
            success=True,
            data={"content": complete_text}
        )
    
    async def generate_chapter_background(self, chapter_id: int, user_id: Optional[str] = None) -> ApiResponse:
        """
        生成章节前文梗概
        
        Args:
            chapter_id: 章节ID
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        logger.info(f"生成章节前文梗概: 章节ID {chapter_id}")
        response = await self.get(f"sse/chapters/{chapter_id}/background", stream=True, user_id=user_id)
        
        # 处理流式响应
        complete_text = ""
        async for event in response:
            if event.event_type == "token" and event.data:
                token = event.data.get("token", "")
                complete_text += token
                
            elif event.event_type == "error":
                logger.error(f"生成章节前文梗概出错: {event.data}")
                return ApiResponse(
                    success=False, 
                    error=event.data
                )
        
        logger.info(f"章节前文梗概生成完成: {chapter_id}, 长度: {len(complete_text)}")
        return ApiResponse(
            success=True,
            data={"background": complete_text}
        )
    
    async def update_chapter_outline(
        self,
        chapter_id: int,
        outline: str,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        修改章节大纲
        
        Args:
            chapter_id: 章节ID
            outline: 修改后的章纲内容
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        logger.info(f"修改章节大纲: 章节ID {chapter_id}")
        
        # 计算大纲字数
        word_count = len(outline)
        
        # 构造请求数据
        data = {
            "outline": outline,
            "outlineWordCount": word_count
        }
        
        # 发送PATCH请求到修改章纲接口
        return await self.patch(f"/write/chapters/{chapter_id}", data=data, user_id=user_id)
    
    async def update_content(
        self, 
        book_id: int, 
        old_content: str, 
        new_content: str
    ) -> ApiResponse:
        """
        更新书籍内容
        
        Args:
            book_id: 书籍ID
            old_content: 旧内容
            new_content: 新内容
            
        Returns:
            API响应对象
        """
        data = {
            "oldContent": old_content,
            "newContent": new_content
        }
        
        logger.info(f"更新书籍内容: 书籍ID {book_id}")
        return await self.patch(f"quick-entries/books/{book_id}/content", data=data)
    
    async def append_to_book(
        self, 
        book_id: int, 
        content: str, 
        chapter_format: str = "第*章"
    ) -> ApiResponse:
        """
        追加内容到书籍
        
        Args:
            book_id: 书籍ID
            content: 追加内容
            chapter_format: 章节格式
            
        Returns:
            API响应对象
        """
        data = {
            "saveId": content,
            "chapterFormat": chapter_format
        }
        
        logger.info(f"追加内容到书籍: 书籍ID {book_id}, 内容长度: {len(content)}")
        return await self.post(f"homepage/books/{book_id}/append", data=data)
    
    async def generate_first_chapter_outline(
        self,
        book_name: str,
        outline_style: str,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        根据标题生成第一章章纲
        
        Args:
            book_name: 书籍名称
            outline_style: 大纲风格
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        logger.info(f"根据标题生成第一章章纲: 书名 {book_name}, 风格: {outline_style}")
        
        # 添加查询参数
        params = {
            "outlineStyle": outline_style,
            "bookName": book_name
        }
        
        response = await self.get(f"/sse/outline", params=params, stream=True, user_id=user_id)
        
        # 处理流式响应
        complete_text = ""
        async for event in response:
            if event.event_type == "token" and event.data:
                token = event.data.get("token", "")
                complete_text += token
                
            elif event.event_type == "error":
                logger.error(f"生成第一章章纲出错: {event.data}")
                return ApiResponse(
                    success=False, 
                    error=event.data
                )
        
        logger.info(f"第一章章纲生成完成: 书名 {book_name}, 长度: {len(complete_text)} 字符")
        return ApiResponse(
            success=True,
            data={"outline": complete_text}
        )
    
    async def expand_chapter_outline(
        self,
        chapter_id: int,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        扩写章节大纲
        
        Args:
            chapter_id: 章节ID
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象，成功时data中包含expanded_outline
        """
        logger.info(f"扩写章节大纲: 章节ID {chapter_id}")
        
        # 构造请求数据
        data = {
            "chapterId": chapter_id
        }
        
        # 发送POST请求到章纲扩写接口，流式响应
        response = await self.post(f"/sse/outline/expand/{chapter_id}", data=data, stream=True, user_id=user_id)
        
        # 处理流式响应
        complete_text = ""
        async for event in response:
            if event.event_type == "token" and event.data:
                token = event.data.get("token", "")
                complete_text += token
                
            elif event.event_type == "error":
                logger.error(f"扩写章节大纲出错: {event.data}")
                return ApiResponse(
                    success=False, 
                    error=event.data
                )
        
        logger.info(f"章节大纲扩写完成: 章节ID {chapter_id}, 扩写后长度: {len(complete_text)} 字符")
        logger.info(f"扩写后章节大纲: {complete_text}")
        return ApiResponse(
            success=True,
            data={"expanded_outline": complete_text}
        )
    
    async def match_chapter_settings(
        self,
        chapter_id: int,
        scene: str,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        匹配章节设定集
        
        Args:
            chapter_id: 章节ID
            scene: 章纲内容或正文
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象
        """
        logger.info(f"匹配章节设定集: 章节ID {chapter_id}")
        
        # 添加查询参数
        params = {
            "scene": scene  
        }
        
        # 发送GET请求到章纲匹配设定集接口
        return await self.get(f"/write/chapters/{chapter_id}/match-settings", params=params, user_id=user_id)
    
    async def get_outline_sentences(
        self,
        chapter_id: int,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        获取章纲句列表
        
        Args:
            chapter_id: 章节ID
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象，包含章纲句列表
        """
        logger.info(f"获取章纲句列表: 章节ID {chapter_id}")
        
        # 添加查询参数
        params = {
            "chapterId": chapter_id
        }
        
        # 发送GET请求获取章纲句列表
        return await self.get("/write/outline/sentences", params=params, user_id=user_id)
    
    async def generate_text_from_sentence(
        self,
        sentence_id: int,
        text_length: Optional[str] = None,
        text_style: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        根据章纲句生成一段正文
        
        Args:
            sentence_id: 章纲句ID
            text_length: 可选，生成文本长度
            text_style: 可选，文本风格
            user_id: 可选，用户ID(手机号)
            
        Returns:
            API响应对象，包含生成的正文内容
        """
        logger.info(f"根据章纲句生成正文: 章纲句ID {sentence_id}")
        
        # 构造请求参数
        params = {}
        if text_length:
            params["textLength"] = text_length
        if text_style:
            params["textStyle"] = text_style
        
        # 发送POST请求到章纲句生成正文接口，流式响应
        response = await self.post(f"/sse/sentences/{sentence_id}/text", data=params, stream=True, user_id=user_id)
        
        # 处理流式响应
        complete_text = ""
        async for event in response:
            if event.event_type == "token" and event.data:
                token = event.data.get("token", "")
                complete_text += token
                
            elif event.event_type == "error":
                logger.error(f"根据章纲句生成正文出错: {event.data}")
                return ApiResponse(
                    success=False, 
                    error=event.data
                )
        
        logger.info(f"章纲句生成正文完成: 章纲句ID {sentence_id}, 生成文本长度: {len(complete_text)} 字符")
        return ApiResponse(
            success=True,
            data={"content": complete_text}
        ) 