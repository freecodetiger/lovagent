"""
企业微信回调路由
"""

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
from wechatpy.exceptions import InvalidSignatureException

from app.services.llm_service import glm_service  # 兼容测试 patch
from app.services.emotion_engine import emotion_engine  # 兼容测试 patch
from app.services.incoming_aggregation_service import incoming_aggregation_service
from app.services.memory_service import memory_service  # 兼容测试 patch
from app.services.multimodal_chat_service import multimodal_chat_service
from app.services.persona_service import persona_service  # 兼容测试 patch
from app.services.wecom_service import wecom_service

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

    registration = await incoming_aggregation_service.register_event(message)
    if not registration.get("duplicate"):
        incoming_aggregation_service.schedule_user_processing(str(message.get("from_user") or ""))

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
