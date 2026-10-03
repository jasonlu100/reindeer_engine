"""AI 对话窗口（测试功能）。

从菜单栏「测试 -> AI 对话框（测试）」打开。使用 ``AI.ai`` 中的本地 Qwen 模型
做流式对话，所有推理在后台线程进行，避免界面卡死。

模型已被设定为 Reindeer 2D 游戏引擎的中文助手：每次提问都会基于
``AI.knowledge`` 检索到的引擎说明与教程片段，动态拼成系统提示词，从而“学会”
完整的引擎文档与教程内容。
"""
from __future__ import annotations

import re
from typing import List, Tuple

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                               QPushButton, QMessageBox)

from editor.i18n import tr

# 本地模型接口（懒加载；未安装依赖 / 缺少权重时给出友好提示）
try:
    from AI.ai import (get_engine, is_llama_available, is_model_available,
                       strip_think)
    from AI.knowledge import build_assistant_prompt
    _AI_IMPORT_OK = True
except Exception:  # pragma: no cover
    _AI_IMPORT_OK = False

    def build_assistant_prompt(_query: str):
        return None


_SESSION_COUNTER = 0


class _ChatWorker(QThread):
    """后台线程：调用本地模型的流式接口并逐 token 回传。

    模型加载（首次）也发生在线程内，因此不会阻塞编辑器主界面。
    """

    token = Signal(str)
    error = Signal(str)

    def __init__(self, session_id: str, message: str):
        super().__init__()
        self._session_id = session_id
        self._message = message

    def run(self) -> None:
        try:
            engine = get_engine()  # 懒加载；首次会在线程内载入权重
            # 根据问题检索知识库，拼出本次系统提示词（含引擎说明 + 教程）
            system_prompt = build_assistant_prompt(self._message)
            for delta in engine.stream_chat(self._session_id, self._message,
                                           system_prompt=system_prompt):
                self.token.emit(delta)
        except Exception as exc:  # 模型加载 / 推理异常
            self.error.emit(str(exc))


class AIChatDialog(QDialog):
    def __init__(self, editor=None, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle(tr("ai.title"))
        self.resize(520, 600)

        # 每个对话框独立的会话 id（与本地引擎的多轮历史绑定）
        global _SESSION_COUNTER
        _SESSION_COUNTER += 1
        self.session_id = f"editor_{_SESSION_COUNTER}"

        self._messages: List[Tuple[str, str]] = []  # (role, raw_text)
        self._raw_assistant = ""                    # 正在流式输出的原始文本
        self._streaming = False
        self._worker: _ChatWorker = None

        self._build_ui()
        self._check_availability()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setAcceptRichText(False)
        layout.addWidget(self.chat, 1)

        self.input = QTextEdit()
        self.input.setPlaceholderText(tr("ai.input_ph"))
        self.input.setMaximumHeight(90)
        layout.addWidget(self.input)

        btn_row = QHBoxLayout()
        self.send_btn = QPushButton(tr("ai.send"))
        self.clear_btn = QPushButton(tr("ai.clear"))
        self.send_btn.clicked.connect(self._on_send)
        self.clear_btn.clicked.connect(self._on_clear)
        btn_row.addStretch(1)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.send_btn)
        layout.addLayout(btn_row)

        # Enter 发送 / Shift+Enter 换行
        self.input.keyPressEvent = self._input_key  # type: ignore

    def _input_key(self, event) -> None:
        from PySide6.QtGui import QKeyEvent
        if (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter) \
                and not (event.modifiers() & Qt.ShiftModifier):
            self._on_send()
            return
        QTextEdit.keyPressEvent(self.input, event)

    # ------------------------------------------------------------------
    def _check_availability(self) -> None:
        if not _AI_IMPORT_OK:
            self._append("ai", tr("ai.unavailable").format(
                reason=tr("ai.llama_missing")))
            self.input.setEnabled(False)
            self.send_btn.setEnabled(False)
            return
        if not is_llama_available():
            self._append("ai", tr("ai.unavailable").format(
                reason=tr("ai.llama_missing")))
            self.input.setEnabled(False)
            self.send_btn.setEnabled(False)
            return
        if not is_model_available():
            self._append("ai", tr("ai.unavailable").format(
                reason=tr("ai.model_missing")))
            self.input.setEnabled(False)
            self.send_btn.setEnabled(False)
            return
        # 一切就绪：预热提示
        self._append("ai", "我是 Reindeer 引擎助手，问问我知道些什么吧～")

    # ------------------------------------------------------------------
    def _append(self, role: str, text: str) -> None:
        self._messages.append((role, text))
        self._render()

    def _render(self) -> None:
        parts = []
        for role, raw in self._messages:
            label = tr("ai.you") if role == "user" else tr("ai.assistant")
            # 展示时剥离推理块；空的流式占位显示“思考中…”
            shown = strip_think(raw) if role == "assistant" else raw
            if role == "assistant" and not shown:
                shown = tr("ai.thinking")
            parts.append(f"{label}：\n{shown}")
        self.chat.setPlainText("\n\n".join(parts))
        # 滚动到底部
        sb = self.chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    def _on_send(self) -> None:
        if self._streaming:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()

        self._messages.append(("user", text))
        self._messages.append(("assistant", ""))
        self._raw_assistant = ""
        self._streaming = True
        self._render()

        self._worker = _ChatWorker(self.session_id, text)
        self._worker.token.connect(self._on_token)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_token(self, delta: str) -> None:
        self._raw_assistant += delta
        self._messages[-1] = ("assistant", self._raw_assistant)
        self._render()

    def _on_error(self, err: str) -> None:
        self._messages[-1] = ("assistant", tr("ai.error").format(err=err))
        self._render()

    def _on_finished(self) -> None:
        self._streaming = False

    def _on_clear(self) -> None:
        if self._streaming:
            return
        self._messages.clear()
        self._raw_assistant = ""
        self._render()
        try:
            from AI.ai import get_engine
            get_engine().clear_session(self.session_id)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        super().closeEvent(event)
