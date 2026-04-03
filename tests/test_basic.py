"""
简单测试脚本，验证项目配置和基本功能
"""

import asyncio
import sys
sys.path.insert(0, "/Users/zpc/Documents/girlchat")


def test_config():
    """测试配置加载"""
    print("测试配置加载...")
    from app.config import settings
    print(f"✅ 配置加载成功")
    print(f"  - 智谱 API Key: {settings.zhipu_api_key[:20]}...")
    print(f"  - 模型: {settings.zhipu_model}")
    print(f"  - 服务端口: {settings.server_port}")


def test_utils():
    """测试工具函数"""
    print("\n测试工具函数...")
    from app.utils.helpers import get_current_time, get_time_period, get_time_period_behavior
    print(f"✅ 当前时间: {get_current_time()}")
    print(f"✅ 时间段: {get_time_period()}")
    print(f"✅ 行为特征: {get_time_period_behavior(get_time_period())}")


def test_prompts():
    """测试 Prompt 模板"""
    print("\n测试 Prompt 模板...")
    from app.prompts.templates import BASE_PERSONA, build_dynamic_prompt, build_morning_greeting
    print(f"✅ 基础人设长度: {len(BASE_PERSONA)} 字符")
    print(f"✅ 早安问候: {build_morning_greeting()}")


async def test_llm():
    """测试 LLM 服务"""
    print("\n测试智谱 GLM-5 API...")
    from app.services.llm_service import glm_service

    try:
        # 简单测试
        response = await glm_service.chat_completion(
            messages=[{"role": "user", "content": "你好，请用一句话介绍一下自己"}],
            max_tokens=100,
        )
        print(f"✅ LLM 响应: {response}")
    except Exception as e:
        print(f"❌ LLM 测试失败: {e}")


async def test_emotion():
    """测试情绪分析"""
    print("\n测试情绪分析...")
    from app.services.llm_service import glm_service

    try:
        emotion = await glm_service.analyze_emotion("今天工作好累啊，有点烦")
        print(f"✅ 情绪分析结果: {emotion}")
    except Exception as e:
        print(f"❌ 情绪分析失败: {e}")


def test_emotion_engine():
    """测试情绪引擎"""
    print("\n测试情绪引擎...")
    from app.services.emotion_engine import emotion_engine

    # 检测触发词
    triggered = emotion_engine.detect_emotion_trigger("今天好开心啊哈哈")
    print(f"✅ 触发词检测: '开心' -> {triggered}")

    # 获取默认状态
    default_state = emotion_engine._get_default_emotion_state()
    print(f"✅ 默认情绪状态: {default_state['current_mood']} (强度: {default_state['intensity']})")


async def main():
    """主测试流程"""
    print("=" * 50)
    print("恋爱 Agent 项目测试")
    print("=" * 50)

    test_config()
    test_utils()
    test_prompts()
    test_emotion_engine()

    await test_llm()
    await test_emotion()

    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())