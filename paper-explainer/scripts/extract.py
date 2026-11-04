#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文全文与原图提取。

PDF（pymupdf）双通道提图：
  通道 A：页面上的嵌入位图（照片、实验图）
  通道 B：页面渲染裁剪（矢量图、组合图）——定位图题文本块，向上裁剪到
          正文文本块底部，收敛到图题上方图形区域的联合外接框
  配对规则、过滤阈值见 references/figure-rules.md

DOCX（标准库 zipfile）：
  word/media/ 解出图片，按文档流顺序与图题段落配对

产出：
  <workdir>/fulltext.txt   全文文本，图题处带 [FIGURE:fig_XXX] 标记
  <workdir>/figures.json   图元数据（图题/页码/通道/置信度）
  <workdir>/figures/       论文原图 PNG

仅依赖标准库 + pymupdf（PDF 时）。
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

CAPTION_RE = re.compile(
    r"^\s*(?:(figure|fig|scheme|chart|table)\.?\s*(\d+)|(图|表)\s*(\d+))",
    re.IGNORECASE,
)
MIN_CROP_W = 100   # pt，裁剪宽度过小视为碎片
MIN_CROP_H = 50    # pt，裁剪高度过小视为碎片
MERGE_OVERLAP = 0.5  # 与上一张裁剪框重叠比例超过此值视为同图子图题，合并
ZOOM = 3           # 渲染倍率（3 -> 216 dpi）


def is_caption(text: str):
    """返回 (kind, caption_text) 或 None。只认块首行。"""
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    m = CAPTION_RE.match(first_line)
    if not m:
        return None
    kind = "table" if (m.group(1) in ("table",) or m.group(3) == "表") else "figure"
    return kind, first_line.strip()


# ---------------- PDF ----------------

def extract_pdf(pdf_path: Path, workdir: Path) -> list:
    try:
        import pymupdf
    except ImportError:
        sys.exit(
            "MISSING DEPENDENCY: 未安装 pymupdf，无法处理 PDF。"
            "请告知用户需要执行 pip install pymupdf，经用户同意后安装。"
        )

    doc = pymupdf.open(pdf_path)
    fig_dir = workdir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    figures = []
    fulltext_parts = []

    for pno, page in enumerate(doc, start=1):
        W, H = page.rect.width, page.rect.height
        margin = 36
        blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,no,type)

        # 页面图形区域候选：嵌入位图 + 矢量绘图
        gfx = []
        for info in page.get_image_info():
            b = info["bbox"]
            if (b[2] - b[0]) * (b[3] - b[1]) > 16:
                gfx.append(list(b))
        for d in page.get_drawings():
            r = d["rect"]
            if (r.width * r.height > 16) and (r.width < 0.95 * W and r.height < 0.95 * H):
                gfx.append([r.x0, r.y0, r.x1, r.y1])

        text_blocks = [b for b in blocks if b[6] == 0]
        captions = []  # (block, kind, caption_text)
        for b in text_blocks:
            c = is_caption(b[4])
            if c and (b[3] - b[1]) < 80:
                captions.append((b, c[0], c[1]))
        captions.sort(key=lambda t: t[0][1])

        def column_bounds(cb):
            cx0, cy0, cx1, cy1 = cb[:4]
            if (cx1 - cx0) > 0.55 * (W - 2 * margin):
                return margin, W - margin
            if cx1 <= W / 2 + 15:
                return margin, W / 2 + 15
            if cx0 >= W / 2 - 15:
                return W / 2 - 15, W - margin
            return margin, W - margin

        def body_bottom(col, y_limit, prev_cap_bottom):
            """正文文本块的最低底部，作为裁剪上界。"""
            top = margin
            for b in text_blocks:
                bx0, by0, bx1, by1, btxt = b[0], b[1], b[2], b[3], b[4]
                if by1 > y_limit + 2:
                    continue
                if not (bx0 >= col[0] - 5 and bx1 <= col[1] + 5):
                    continue
                if (bx1 - bx0) > 0.7 * (col[1] - col[0]) and (by1 - by0) > 25:
                    if is_caption(btxt) is None:
                        top = max(top, by1 + 2)
            if prev_cap_bottom is not None:
                top = max(top, prev_cap_bottom + 2)
            return top

        kept_regions = []  # 本页已保留裁剪框，用于子图题合并
        for cap_block, kind, cap_text in captions:
            col = column_bounds(cap_block)
            cy0 = cap_block[1]
            prev_bottom = None
            for pb, _, _ in captions:
                if pb is cap_block:
                    break
                pc = column_bounds(pb)
                if pb[3] <= cy0 and not (pc[1] < col[0] or pc[0] > col[1]):
                    prev_bottom = max(prev_bottom or 0, pb[3])
            top = body_bottom(col, cy0, prev_bottom)

            # 收集图题上方、本列内的图形，取联合外接框
            sel = [g for g in gfx
                   if g[3] <= cy0 + 4 and g[2] > col[0] and g[0] < col[1]
                   and g[1] >= top - 2 and (g[3] - g[1]) > 8]
            if sel:
                # 上界严格不低于正文底部，防止裁入上一行文字残影
                ux0 = max(col[0] + 1, min(g[0] for g in sel) - 4)
                uy0 = max(top, min(g[1] for g in sel))
                ux1 = min(col[1] - 1, max(g[2] for g in sel) + 4)
                uy1 = min(cy0 + 1, max(g[3] for g in sel)) + 2
                source, confidence = "render-crop", "high"
            else:
                # 无图形：可能是纯文字图题（图在别处），放弃，宁缺毋滥
                continue
            if (ux1 - ux0) < MIN_CROP_W or (uy1 - uy0) < MIN_CROP_H:
                continue

            # 子图题合并：与同页上一张保留区域高度重叠则并入
            merged = False
            for reg in kept_regions:
                ox = max(0, min(ux1, reg[2]) - max(ux0, reg[0]))
                oy = max(0, min(uy1, reg[3]) - max(uy0, reg[1]))
                inter = ox * oy
                small = min((ux1 - ux0) * (uy1 - uy0), (reg[2] - reg[0]) * (reg[3] - reg[1]))
                if small > 0 and inter / small > MERGE_OVERLAP:
                    figures[-1]["caption"] += " / " + cap_text
                    merged = True
                    break
            if merged:
                continue

            fig_id = f"fig_{len(figures) + 1:03d}"
            pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=pymupdf.Rect(ux0, uy0, ux1, uy1), alpha=False)
            out = fig_dir / f"{fig_id}.png"
            pix.save(out)
            figures.append({
                "id": fig_id, "file": f"figures/{fig_id}.png",
                "caption": cap_text, "page": pno, "kind": kind,
                "source": source, "confidence": confidence,
            })
            kept_regions.append([ux0, uy0, ux1, uy1])

        # 全文文本（图题块后插入标记）
        page_text_parts = []
        # 注意：captions 元素为 (block, kind, text)，cb 即 block 本身，键须用 id(cb)
        cap_by_block = {id(cb): (t_text, kind) for cb, kind, t_text in captions}
        id2fig = {}
        for f in figures:
            id2fig.setdefault((f["page"], f["caption"].split(" / ")[0]), f)
        for b in blocks:
            if b[6] == 0:
                page_text_parts.append(b[4].rstrip())
                cap = cap_by_block.get(id(b))
                if cap:
                    f = id2fig.get((pno, cap[0]))
                    if f:
                        page_text_parts.append(f"[FIGURE:{f['id']}] {cap[0]}")
        fulltext_parts.append(f"\n===== Page {pno} =====\n" + "\n".join(page_text_parts))

    (workdir / "fulltext.txt").write_text("\n".join(fulltext_parts), encoding="utf-8")
    return figures


# ---------------- DOCX ----------------

def extract_docx(docx_path: Path, workdir: Path) -> list:
    fig_dir = workdir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path) as z:
        rels_xml = z.read("word/_rels/document.xml.rels").decode("utf-8", "ignore")
        doc_xml = z.read("word/document.xml").decode("utf-8", "ignore")
        rid2target = dict(re.findall(
            r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', rels_xml))

        SUPPORTED = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif")
        figures, pending_imgs, fulltext_parts = [], [], []
        img_counter = 0

        for para in re.findall(r"<w:p[ >].*?</w:p>", doc_xml, re.S):
            texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, re.S)
            ptext = "".join(texts).strip()
            embeds = re.findall(r'r:embed="([^"]+)"', para) + re.findall(
                r'r:id="(rId\d+)"[^>]*/>', para)
            for rid in embeds:
                target = rid2target.get(rid, "")
                fname = target.split("/")[-1]
                if not fname or not fname.lower().endswith(SUPPORTED):
                    if fname:
                        print(f"WARN: 不支持的图片格式已跳过: {fname}", file=sys.stderr)
                    continue
                img_counter += 1
                fig_id = f"fig_{img_counter:03d}"
                out = fig_dir / f"{fig_id}{Path(fname).suffix.lower()}"
                try:
                    out.write_bytes(z.read("word/" + target.lstrip("/")))
                except KeyError:
                    continue
                pending_imgs.append({
                    "id": fig_id, "file": f"figures/{out.name}",
                    "caption": "", "page": 0, "kind": "figure",
                    "source": "docx-media", "confidence": "medium",
                })
            if ptext:
                c = is_caption(ptext)
                if c and pending_imgs:
                    img = pending_imgs.pop(0)
                    img["caption"] = ptext
                    img["confidence"] = "high"
                    figures.append(img)
                    fulltext_parts.append(f"[FIGURE:{img['id']}] {ptext}")
                else:
                    fulltext_parts.append(ptext)
        # 未配到图题的图：保留但标记低置信，讲解时按宁缺毋滥处理
        for img in pending_imgs:
            img["caption"] = img["caption"] or "（未找到图题）"
            img["confidence"] = "low"
            figures.append(img)
            fulltext_parts.append(f"[FIGURE:{img['id']}] {img['caption']}")

    (workdir / "fulltext.txt").write_text("\n".join(fulltext_parts), encoding="utf-8")
    return figures


def main() -> None:
    p = argparse.ArgumentParser(description="论文全文与原图提取")
    p.add_argument("--input", required=True, help="论文文件（.pdf / .docx）")
    p.add_argument("--workdir", required=True, help="解析输出目录")
    args = p.parse_args()

    src = Path(args.input)
    if not src.exists():
        sys.exit(f"ERROR: file not found: {src}")
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    ext = src.suffix.lower()
    if ext == ".pdf":
        figures = extract_pdf(src, workdir)
    elif ext == ".docx":
        figures = extract_docx(src, workdir)
    else:
        sys.exit("ERROR: 仅支持 .pdf 与 .docx")

    (workdir / "figures.json").write_text(
        json.dumps(figures, ensure_ascii=False, indent=2), encoding="utf-8")
    hi = sum(1 for f in figures if f["confidence"] == "high")
    print(f"OK: 提取 {len(figures)} 张图（高置信 {hi}），全文 -> {workdir / 'fulltext.txt'}")
    print("提醒：讲解前先完成多模态阀门自检（SKILL.md 第 2 步）。")


if __name__ == "__main__":
    main()
