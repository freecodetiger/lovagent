"""
企业微信回调路由
"""

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
from wechatpy.exceptions import InvalidSignatureException

from app.services.wecom_service import wecom_service
from app.services.llm_service import glm_service
from app.services.emotion_engine import emotion_engine
from app.services.memory_service import memory_service
from app.services.persona_service import persona_service
from app.prompts.templates import build_dynamic_prompt
from app.utils.helpers import (
    choose_natural_fallback_reply,
    get_current_time,
    get_response_constraints,
    is_response_too_similar,
)

router = APIRouter()


ANTI_REPEAT_RETRY_INSTRUCTION = """

# Retry Rule
- 你刚刚生成的回复和最近几轮表达太像了。
- 这次必须换一个开头、换一个安慰或回应角度、换一个收尾。
- 不要重复“我在呢”“抱抱”“我也想你”这类刚用过的原句，除非用户明确要求。
- 保持同样的人设和情绪，但写得更像这一次临场接话。
"""


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

    if not echostr:
        raise HTTPException(status_code=400, detail="Missing echostr")

    try:
        decrypted_echostr = wecom_service.verify_callback(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echostr=echostr,
        )
        print(f"企业微信回调验证成功，返回明文 echostr: {decrypted_echostr}")
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException as exc:
        print(f"企业微信回调验签失败: {exc}")
        raise HTTPException(status_code=403, detail="Invalid callback signature")
    except Exception as exc:
        print(f"企业微信回调解密失败: {exc}")
        raise HTTPException(status_code=403, detail=f"Callback verification failed: {exc}")


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
    except InvalidSignatureException as exc:
        print(f"企业微信消息回调验签失败: {exc}")
        raise HTTPException(status_code=403, detail="Invalid message signature")
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
    await memory_service.get_or_create_user(user_id)
    persona_config = persona_service.get_persona_config()
    response_constraints = get_response_constraints(
        user_content,
        persona_config.get("response_preferences"),
    )

    # 2. 分析用户情绪
    try:
        user_emotion = await glm_service.analyze_emotion(user_content)
    except Exception as exc:
        print(f"情绪分析失败，回退到默认情绪: {exc}")
        user_emotion = {"neutral": 1.0}

    # 3. 更新 Agent 情绪状态
    agent_emotion = await emotion_engine.update_state(user_id, user_content, user_emotion)

    # 4. 获取记忆上下文
    context = await memory_service.get_conversation_context(user_id)
    user_memory = await memory_service.get_user_memory(user_id)
    recent_agent_replies = await memory_service.get_recent_agent_replies(user_id, limit=3)
    web_search_context = await glm_service.maybe_collect_web_context(user_content)

    # 5. 构建 Prompt
    system_prompt = build_dynamic_prompt(
        user_input=user_content,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
        context=context,
        current_time=get_current_time(),
        recent_agent_replies=recent_agent_replies,
        persona_config=persona_config,
        user_profile=user_memory,
        web_search_context=web_search_context,
    )

    # 6. 调用 LLM 生成回复
    context_messages = await memory_service.get_recent_messages(
        user_id,
        limit=int(response_constraints["context_limit"]),
    )
    agent_response = ""
    try:
        agent_response = await glm_service.chat_with_context(
            system_prompt=system_prompt,
            user_message=user_content,
            context_messages=context_messages,
            temperature=0.88,
            top_p=0.93,
            max_tokens=int(response_constraints["max_tokens"]),
        )
    except Exception as exc:
        print(f"首次生成回复失败，尝试轻量重试: {exc}")
        try:
            agent_response = await glm_service.chat_with_context(
                system_prompt=system_prompt,
                user_message=user_content,
                context_messages=[],
                temperature=0.84,
                top_p=0.9,
                max_tokens=int(response_constraints["max_tokens"]),
            )
        except Exception as retry_exc:
            print(f"轻量重试失败，使用自然兜底: {retry_exc}")
            agent_response = ""

    if agent_response and is_response_too_similar(agent_response, recent_agent_replies):
        retry_prompt = f"{system_prompt}{ANTI_REPEAT_RETRY_INSTRUCTION}"
        try:
            regenerated_response = await glm_service.chat_with_context(
                system_prompt=retry_prompt,
                user_message=user_content,
                context_messages=context_messages,
                temperature=0.95,
                top_p=0.95,
                max_tokens=int(response_constraints["max_tokens"]),
            )
            if regenerated_response:
                agent_response = regenerated_response
        except Exception as exc:
            print(f"重复抑制重试失败，保留原回复: {exc}")

    if not agent_response:
        agent_response = choose_natural_fallback_reply(user_content, user_emotion)

    # 7. 保存对话记录
    await memory_service.save_conversation(
        user_id=user_id,
        user_message=user_content,
        agent_message=agent_response,
        user_emotion=user_emotion,
        agent_emotion=agent_emotion,
    )

    # 8. 发送回复
    try:
        await wecom_service.send_text_message(user_id, agent_response)
    except Exception as exc:
        print(f"发送企业微信消息失败: {exc}")

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
