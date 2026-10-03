"""
Reindeer 引擎知识库（检索增强 / RAG-lite）。

把 README.md 与 web_doc/ 下的全部教程页面解析、切片成一个轻量知识库；
每次用户提问时，根据问题检索最相关的若干片段，拼进系统提示词里交给本地
Qwen 模型。这样既能让 0.8B 小模型“学到”完整引擎说明与全部教程，又不会把
整本教程都塞进它有限的上下文（8192 token）里导致跑偏。

零第三方依赖：只用标准库做 HTML 清洗与关键词检索。
"""
from __future__ import annotations

import html as _html
import os
import re
from typing import Dict, List, Optional

_BASE = os.path.dirname(os.path.abspath(__file__))   # .../AI
_ROOT = os.path.dirname(_BASE)                         # .../reindeer
_README = os.path.join(_ROOT, "README.md")
_WEB_DOC = os.path.join(_ROOT, "web_doc")

_CJK = r"一-鿿"  # 中文统一表意文字区段

_INDEX: Optional[List[Dict[str, str]]] = None


# ── 文本清洗 ────────────────────────────────────────────────
def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _strip_html(h: str):
    """返回 (页面标题, [(小节标题, 小节正文), ...])。"""
    h = re.sub(r"<script[\s\S]*?</script>", " ", h, flags=re.I)
    h = re.sub(r"<style[\s\S]*?</style>", " ", h, flags=re.I)
    m = re.search(r"<title>(.*?)</title>", h, re.I | re.S)
    title = _clean(m.group(1)) if m else ""
    parts = re.split(r"<h[1-3][^>]*>(.*?)</h[1-3]>", h, flags=re.I | re.S)
    chunks = []
    pre = _clean(parts[0])
    if pre:
        chunks.append((title or "概览", pre))
    for i in range(1, len(parts), 2):
        htext = _clean(parts[i])
        btext = _clean(parts[i + 1]) if i + 1 < len(parts) else ""
        t = htext if htext else (title or "概览")
        if btext:
            chunks.append((t, btext))
    return title, chunks


def _read_markdown(path: str) -> List[Dict[str, str]]:
    text = open(path, encoding="utf-8", errors="ignore").read()
    # 去掉代码块之外的 markdown 标题/列表符号，保留代码与正文
    lines = text.splitlines()
    chunks: List[Dict[str, str]] = []
    cur_title = "概览"
    buf: List[str] = []
    for ln in lines:
        m = re.match(r"^#{1,3}\s+(.*)$", ln)
        if m:
            if buf:
                body = _clean("\n".join(buf))
                if body:
                    chunks.append({"title": cur_title, "text": body,
                                   "source": os.path.basename(path)})
            cur_title = _clean(m.group(1))
            buf = []
        else:
            buf.append(ln)
    if buf:
        body = _clean("\n".join(buf))
        if body:
            chunks.append({"title": cur_title, "text": body,
                           "source": os.path.basename(path)})
    return chunks


def _read_html(path: str) -> List[Dict[str, str]]:
    h = open(path, encoding="utf-8", errors="ignore").read()
    title, chunks = _strip_html(h)
    page = os.path.basename(path)
    return [{"title": t, "text": b, "source": page} for t, b in chunks]


# ── 建库 ────────────────────────────────────────────────────
def _build_index() -> List[Dict[str, str]]:
    chunks: List[Dict[str, str]] = []
    if os.path.isfile(_README):
        chunks += _read_markdown(_README)
    # 专门的 AI 知识库（比 HTML 教程更详尽），以及今后放在 AI/ 下的其它 .md
    if os.path.isdir(_BASE):
        for fn in os.listdir(_BASE):
            if fn.lower().endswith(".md"):
                try:
                    chunks += _read_markdown(os.path.join(_BASE, fn))
                except Exception:
                    continue
    if os.path.isdir(_WEB_DOC):
        for root, _dirs, files in os.walk(_WEB_DOC):
            for fn in files:
                if fn.lower().endswith(".html"):
                    try:
                        chunks += _read_html(os.path.join(root, fn))
                    except Exception:
                        continue
    return chunks


def get_index() -> List[Dict[str, str]]:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


# ── 检索 ────────────────────────────────────────────────────
def _tokenize(s: str) -> List[str]:
    s = s.lower()
    toks = re.findall(r"[a-z0-9_]+", s)
    cjk = re.findall(f"[{_CJK}]", s)
    toks += cjk
    toks += [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    return toks


def retrieve(query: str, top_k: int = 5, max_chars: int = 2600) -> str:
    """返回与 ``query`` 最相关的若干知识片段拼接文本。"""
    idx = get_index()
    if not idx:
        return ""
    q = _tokenize(query)
    if not q:
        return ""

    scored = []
    for c in idx:
        tl = c["text"].lower()
        score = sum(tl.count(t) for t in q)
        tl2 = c["title"].lower()
        score += sum(3 for t in q if t in tl2)   # 标题命中加权
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])

    # 完全不相关时，回退到 README 概览，保证至少有引擎身份背景
    if scored[0][0] == 0:
        for c in idx:
            if c["source"].endswith("README.md"):
                return c["text"][:max_chars]
        return ""

    out: List[str] = []
    used = 0
    for sc, c in scored:
        if sc <= 0 or len(out) >= top_k:
            break
        if used + len(c["text"]) > max_chars:
            piece = c["text"][: max(0, max_chars - used)]
            if piece.strip():
                out.append(f"【{c['title']}】\n{piece}")
            break
        out.append(f"【{c['title']}】\n{c['text']}")
        used += len(c["text"])
    return "\n\n".join(out)


# ── 系统提示词 ──────────────────────────────────────────────
ROLE = """你是 Reindeer 2D 游戏引擎的官方中文助手。

Reindeer 是一个用 Python 编写、带图形化编辑器（基于 Qt/PySide6）、参考 Godot 设计风格的可扩展 2D 游戏引擎，引擎核心零第三方依赖。

请用简体中文、简洁友好地回答用户关于 Reindeer 引擎、编辑器界面、节点、脚本、物理、插件以及内置教程的问题。
只依据下面“参考资料”中的内容作答；如果资料里没有相关信息，就如实说明“这个我不太确定，建议你在编辑器里查看 帮助 → 教程 / 脚本 API 文档”，不要编造。
回答要简洁、切题，不要重复同一句话。"""


def build_assistant_prompt(query: str) -> str:
    """根据问题检索知识库，拼出本次对话的系统提示词。"""
    ctx = retrieve(query)
    if ctx:
        return ROLE + "\n\n## 参考资料（仅供参考，按需引用）\n" + ctx
    return ROLE
