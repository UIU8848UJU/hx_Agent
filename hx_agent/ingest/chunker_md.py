# 切md的文档模块

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Dict, Any

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

@dataclass
class Chunk:
    heading: str
    start_line: int
    end_line: int
    text: str

def chunk_markdown(text: str) -> List[Dict[str, Any]]:
    """
    最小可用版本：
    - 非代码块内：遇到 #/##/### 标题就切块
    - 代码块（``` 或 ~~~）内：不识别标题，不切
    - heading 使用 “H1 > H2 > H3” 的路径
    """
    lines = text.splitlines()
    chunks: List[Chunk] = []

    heading_stack: List[str] = []  # index 0..5 对应 H1..H6
    buf: List[str] = []
    buf_start = 1

    in_code = False
    fence = None  # ``` or ~~~

    def current_heading() -> str:
        hs = [h for h in heading_stack if h]
        return " > ".join(hs)

    def flush(end_line: int):
        nonlocal buf, buf_start
        if not buf:
            return
        content = "\n".join(buf).strip()
        if content:
            chunks.append(Chunk(current_heading(), buf_start, end_line, content))
        buf = []

    for i, raw in enumerate(lines, start=1):
        line = raw

        # fenced code toggle
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            mark = line.strip()[:3]
            if not in_code:
                in_code = True
                fence = mark
            else:
                if fence == mark:
                    in_code = False
                    fence = None
            buf.append(line)
            continue

        # heading split (only when not in code)
        if not in_code:
            m = _HEADING_RE.match(line)
            if m:
                # 遇到新标题：先 flush 上一个 chunk
                flush(i - 1)
                buf_start = i

                level = len(m.group(1))
                title = m.group(2).strip()

                # 更新 heading 栈
                # level=1 -> index 0
                idx = level - 1
                while len(heading_stack) < 6:
                    heading_stack.append("")
                heading_stack[idx] = title
                # 清空更深层
                for j in range(idx + 1, 6):
                    heading_stack[j] = ""

                buf.append(line)
                continue

        buf.append(line)

    flush(len(lines))

    # 返回 dict，方便 DB 写入
    return [
        {"heading": c.heading, "start_line": c.start_line, "end_line": c.end_line, "text": c.text}
        for c in chunks
    ]