"""
企业微信回调路由
"""

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
import xml.etree.ElementTree as ET

from app.services.wecom_service import wecom_service
from app.services.llm_service import glm_service
from app.services.emotion_engine import emotion_engine
from app.services.memory_service import memory_service
from app.prompts.templates import build_dynamic_prompt
from app.utils.helpers import get_current_time

router = APIRouter()


@router.get("/callback")
async def wecom_callback_verify(
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(None),
):
    """
    企业微信回调 URL 验证
    企业微信会发送 GET 请求来验证回调 URL
    """
    print(f"收到验证请求: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr}")

    # 解密 echostr 并返回明文
    if echostr:
        try:
            decrypted_echostr = wecom_service.decrypt_echostr(echostr)
            print(f"解密成功: {decrypted_echostr}")
            return PlainTextResponse(content=decrypted_echostr)
        except Exception as e:
            print(f"解密失败: {e}")
            raise HTTPException(status_code=403, detail=f"Decryption failed: {e}")

    return PlainTextResponse(content="success")


@router.post("/callback")
async def wecom_callback_handler(
    request: Request,
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """
    企业微信消息回调处理
    接收用户发送的消息并处理
    """
    # 读取请求体
    body = await request.body()
    xml_content = body.decode("utf-8")
    print(f"收到消息回调: msg_signature={msg_signature}, xml={xml_content[:200]}...")

    # 解密消息
    try:
        decrypted_xml = wecom_service.decrypt_message(
            xml_content, msg_signature, timestamp, nonce
        )
    except Exception as e:
        print(f"解密消息失败: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to decrypt message: {e}")

    # 解析消息
    message = wecom_service.parse_message(decrypted_xml)
    print(f"收到消息: {message}")

    # 只处理文本消息
    if message.get("msg_type") != "text":
        return PlainTextResponse(content="success")

    user_id = message.get("from_user")
    user_content = message.get("content", "")

    # 1. 获取或创建用户
    user = await memory_service.get_or_create_user(user_id)

    # 2. 分析用户情绪
    user_emotion = await glm_service.analyze_emotion(user_content)

    # 3. 更新 Agent 情绪状态
    agent_emotion = await emotion_engine.update_state(user_id, user_content, user_emotion)

    # 4. 获取记忆上下文
    context = await memory_service.get_conversation_context(user_id)

    # 5. 构建 Prompt
    system_prompt = build_dynamic_prompt(
        user_input=user_content,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
        context=context,
        current_time=get_current_time(),
    )

    # 6. 调用 LLM 生成回复
    context_messages = await memory_service.get_recent_messages(user_id, limit=10)
    agent_response = await glm_service.chat_with_context(
        system_prompt=system_prompt,
        user_message=user_content,
        context_messages=context_messages,
        temperature=0.7,
    )

    # 7. 保存对话记录
    await memory_service.save_conversation(
        user_id=user_id,
        user_message=user_content,
        agent_message=agent_response,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
    )

    # 8. 发送回复
    await wecom_service.send_text_message(user_id, agent_response)

    return PlainTextResponse(content="success")


@router.post("/send")
async def send_message(
    to_user: str = Query(...),
    content: str = Query(...),
):
    """
    手动发送消息接口（用于测试）
    """
    result = await wecom_service.send_text_message(to_user, content)
    return {"success": True, "result": result}