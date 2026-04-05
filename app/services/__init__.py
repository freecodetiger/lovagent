"""
业务服务模块
"""

from importlib import import_module

__all__ = [
    "WeComService",
    "wecom_service",
    "GLMService",
    "glm_service",
    "EmotionEngine",
    "emotion_engine",
    "MemoryService",
    "memory_service",
]


_SERVICE_EXPORTS = {
    "WeComService": ("app.services.wecom_service", "WeComService"),
    "wecom_service": ("app.services.wecom_service", "wecom_service"),
    "GLMService": ("app.services.llm_service", "GLMService"),
    "glm_service": ("app.services.llm_service", "glm_service"),
    "EmotionEngine": ("app.services.emotion_engine", "EmotionEngine"),
    "emotion_engine": ("app.services.emotion_engine", "emotion_engine"),
    "MemoryService": ("app.services.memory_service", "MemoryService"),
    "memory_service": ("app.services.memory_service", "memory_service"),
}


def __getattr__(name):
    """按需导入服务，避免无关依赖在包初始化阶段被强制加载。"""
    if name not in _SERVICE_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _SERVICE_EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
