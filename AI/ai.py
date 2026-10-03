"""
Qwen3.5-0.8B 本地推理封装类
基于 llama-cpp-python，模型常驻内存（按需懒加载）。

公开接口
--------
- :class:`QwenLocalEngine`  —— 推理引擎（懒加载模型，单轮 / 多轮 / 流式）
- :func:`get_engine`        —— 进程内单例，避免重复加载 500MB+ 的权重
- :func:`is_model_available` —— 快速判断模型文件是否存在
- :func:`is_llama_available` —— 判断 llama_cpp 是否已安装

用法:
    engine = get_engine()                 # 首次调用时加载模型
    reply  = engine.chat("sess_1", "你好")
    for tok in engine.stream_chat("sess_1", "讲个笑话"):
        print(tok, end="", flush=True)
"""
from __future__ import annotations

import os
import re
from typing import Dict, Iterator, List, Optional

try:
    from llama_cpp import Llama  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - 仅在未安装 llama_cpp 时触发
    Llama = None  # type: ignore

# Qwen3 系列会输出 <think>...</think> 推理片段，这里在返回/落库前统一剥离，
# 避免把模型的“内心独白”直接暴露给最终用户。
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """去掉 ``<think>...</think>`` 推理块，返回干净文本。"""
    return _THINK_RE.sub("", text).strip()


#: 对外暴露的公开别名（前端展示时也需要剥离推理块）。
strip_think = _strip_think


def _default_model_path() -> str:
    """返回与本模块同目录下的默认模型权重路径。"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen.gguf")


def is_llama_available() -> bool:
    """llama_cpp 是否可用。"""
    return Llama is not None


def is_model_available(model_path: Optional[str] = None) -> bool:
    """模型权重文件是否存在（懒加载前可先用它做快速判定）。"""
    if model_path is None:
        model_path = _default_model_path()
    return os.path.exists(model_path)


class QwenLocalEngine:
    """
    Qwen 本地推理引擎封装。

    模型权重在第一次真正生成时才加载（懒加载），因此构造实例本身很廉价，
    可以放心地由 :func:`get_engine` 以单例方式持有。
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 8192,
        n_threads: Optional[int] = None,
        n_gpu_layers: int = 0,
        chat_format: Optional[str] = None,
        verbose: bool = False,
    ):
        self.model_path = model_path
        self._n_ctx = n_ctx
        self._n_threads = n_threads
        self._n_gpu_layers = n_gpu_layers
        self._chat_format = chat_format
        self._verbose = verbose
        self._llm = None  # type: ignore
        self._sessions: Dict[str, List[Dict[str, str]]] = {}

    # ── 模型加载（懒加载）──────────────────────────────────────
    def _ensure_model(self) -> None:
        """确保底层 Llama 模型已加载；未安装依赖或缺少权重时给出清晰报错。"""
        if self._llm is not None:
            return
        if Llama is None:
            raise RuntimeError(
                "未安装 llama_cpp（pip install llama-cpp-python），无法加载本地模型。"
            )
        if not os.path.exists(self.model_path):
            raise RuntimeError(f"未找到模型权重文件：{self.model_path}")
        self._llm = Llama(
            model_path=self.model_path,
            n_ctx=self._n_ctx,
            n_threads=self._n_threads,
            n_gpu_layers=self._n_gpu_layers,
            chat_format=self._chat_format,
            verbose=self._verbose,
        )

    # ── 公开接口 ──────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 512,
        repeat_penalty: float = 1.1,
    ) -> str:
        """单轮生成：给定提示词，返回生成文本（已剥离推理块）。"""
        self._ensure_model()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        out = self._llm.create_chat_completion(  # type: ignore[union-attr]
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty,
        )
        return _strip_think(out["choices"][0]["message"]["content"].strip())

    def _set_session_system(self, session_id: str, system_prompt: str) -> None:
        """在会话历史头部维护/更新一条 system 消息（支持每轮刷新上下文）。"""
        msgs = self._sessions[session_id]
        if msgs and msgs[0].get("role") == "system":
            msgs[0]["content"] = system_prompt
        else:
            msgs.insert(0, {"role": "system", "content": system_prompt})

    def chat(
        self,
        session_id: str,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        repeat_penalty: float = 1.1,
    ) -> str:
        """带上下文的对话接口，自动维护 session_id 对应的历史。

        ``system_prompt`` 每次调用都可更新（被放在历史头部），因此适合在每轮
        根据问题检索到的资料动态注入上下文。
        """
        self._ensure_model()
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        if system_prompt is not None:
            self._set_session_system(session_id, system_prompt)

        self._sessions[session_id].append(
            {"role": "user", "content": user_message}
        )

        out = self._llm.create_chat_completion(  # type: ignore[union-attr]
            messages=self._sessions[session_id],
            temperature=temperature,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty,
        )
        reply = _strip_think(out["choices"][0]["message"]["content"].strip())

        self._sessions[session_id].append(
            {"role": "assistant", "content": reply}
        )
        return reply

    def stream_chat(
        self,
        session_id: str,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        repeat_penalty: float = 1.1,
    ) -> Iterator[str]:
        """
        流式对话接口，逐 token 返回（原始 delta，便于前端做“打字机”效果）。

        ``system_prompt`` 每次调用都可更新（放在历史头部），便于按问题检索注入。

        返回的每一个 token 都可能包含在 ``<think>`` 推理块内，前端应自行
        用 :func:`_strip_think` 做展示过滤；而写入历史的内容已是被剥离后的干净文本。
        """
        self._ensure_model()
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        if system_prompt is not None:
            self._set_session_system(session_id, system_prompt)

        self._sessions[session_id].append(
            {"role": "user", "content": user_message}
        )

        stream = self._llm.create_chat_completion(  # type: ignore[union-attr]
            messages=self._sessions[session_id],
            temperature=temperature,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty,
            stream=True,
        )

        full_reply = ""
        for chunk in stream:
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta:
                full_reply += delta
                yield delta

        reply = _strip_think(full_reply)
        self._sessions[session_id].append(
            {"role": "assistant", "content": reply}
        )

    def clear_session(self, session_id: str) -> None:
        """清除指定会话的上下文历史。"""
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> List[str]:
        """返回所有活跃会话 ID。"""
        return list(self._sessions.keys())


# ── 进程内单例 ───────────────────────────────────────────────
_engine: Optional[QwenLocalEngine] = None


def get_engine(model_path: Optional[str] = None,
               **kwargs) -> QwenLocalEngine:
    """返回进程内共享的推理引擎单例（首次调用时懒加载模型）。"""
    global _engine
    if _engine is None:
        if model_path is None:
            model_path = _default_model_path()
        _engine = QwenLocalEngine(model_path, **kwargs)
    return _engine


# ── 使用示例 ──────────────────────────────────────────────────
if __name__ == "__main__":
    mp = _default_model_path()
    print("model:", mp, "available:", is_model_available(mp))
    engine = get_engine(mp, n_ctx=8192)

    # 单轮
    print(engine.generate("用一句话解释机器学习。", max_tokens=100))
    print("-" * 40)

    # 多轮
    engine.chat("user_001", "我叫小明，喜欢编程。", system_prompt="记住用户信息。")
    print(engine.chat("user_001", "我叫什么名字？"))
    print("-" * 40)

    # 流式
    for token in engine.stream_chat("user_001", "给我讲个笑话。"):
        print(token, end="", flush=True)
