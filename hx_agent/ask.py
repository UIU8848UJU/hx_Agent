from __future__ import annotations
from collections import defaultdict



def stitch_chunks(rows, neighbor_gap: int = 1):
    """
    rows: list of sqlite row/tuple/dict，至少要有 path, chunk_index, text 等字段
    合并同一文件中 chunk_index 连续（gap<=1）的块
    """
    by_path = defaultdict(list)
    for r in rows:
        by_path[r["path"]].append(r)

    stitched = []
    for path, items in by_path.items():
        items.sort(key=lambda x: int(x.get("chunk_index", 0)))

        cur = None
        for it in items:
            if cur is None:
                cur = dict(it)
                continue

            if "chunk_index" in it and "chunk_index" in cur:
                if int(it["chunk_index"]) <= int(cur["chunk_index"]) + neighbor_gap:
                    cur["text"] = (cur["text"] + "\n" + it["text"]).strip()
                    cur["end_line"] = max(int(cur["end_line"]), int(it["end_line"]))
                    # 引用聚合：保留 chunk_id 列表
                    cur.setdefault("chunk_ids", [int(cur["chunk_id"])])
                    cur["chunk_ids"].append(int(it["chunk_id"]))
                    cur["chunk_index"] = max(int(cur["chunk_index"]), int(it["chunk_index"]))
                    continue

            stitched.append(cur)
            cur = dict(it)

        if cur is not None:
            stitched.append(cur)

    # 如果没有 chunk_ids，补上自己
    for s in stitched:
        if "chunk_ids" not in s:
            s["chunk_ids"] = [int(s["chunk_id"])]

    return stitched

def summarize_rule(text: str, mode: str):
    """
    超简规则摘要：v0.1 先能用即可
    summary: 提取前几句
    steps: 过滤出像步骤的行（列表/编号/关键字）
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""

    if mode == "steps":
        keep = []
        for ln in lines:
            if ln.startswith(("-", "*")):
                keep.append(ln)
            elif ln[:2].isdigit() and (ln[2:3] in [".", "、"]):
                keep.append(ln)
            elif any(k in ln for k in ["步骤", "流程", "做法", "建议", "注意"]):
                keep.append(ln)
        if keep:
            return "\n".join(keep[:12])
        # 没提取到就退化成 summary
        mode = "summary"

    # summary
    return "\n".join(lines[:8])