#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把讲解内容（content.md）+ 提取的论文原图渲染为单文件 HTML。

content.md 约定（见 SKILL.md 第 3 步）：
  - YAML 风格 frontmatter：title / authors / year / oneliner / mode
  - mode: text-only 时顶部渲染"非多模态生成"警告条
  - 图片：![fig_XXX](figures/fig_XXX.png)，图后紧邻行写"图解：……"
  - 支持：# ## ### 标题、段落、**加粗**、- 列表、| 表格 |

图片以 base64 内嵌，产物离线可开。
"""
import argparse
import base64
import json
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def parse_content(md_text: str):
    lines = md_text.replace("\r\n", "\n").split("\n")
    meta, body_lines = {}, lines
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end:
            for ln in lines[1:end]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip()
            body_lines = lines[end + 1:]

    blocks, para, i = [], [], 0
    while i < len(body_lines):
        ln = body_lines[i]
        s = ln.strip()
        if not s:
            if para:
                blocks.append(("p", list(para)))
                para = []
            i += 1
            continue
        m_img = _match_image(s)
        if m_img:
            if para:
                blocks.append(("p", list(para)))
                para = []
            note_lines = []
            j = i + 1
            while j < len(body_lines) and body_lines[j].strip():
                note_lines.append(body_lines[j].strip())
                j += 1
            blocks.append(("img", {"ref": m_img[1], "note": "\n".join(note_lines)}))
            i = j
            continue
        if s.startswith("|") and s.endswith("|"):
            if para:
                blocks.append(("p", list(para)))
                para = []
            rows = []
            while i < len(body_lines) and body_lines[i].strip().startswith("|"):
                cells = [c.strip() for c in body_lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        if s.startswith("- "):
            if para:
                blocks.append(("p", list(para)))
                para = []
            items = []
            while i < len(body_lines) and body_lines[i].strip().startswith("- "):
                items.append(body_lines[i].strip()[2:])
                i += 1
            blocks.append(("ul", items))
            continue
        m_h = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m_h:
            if para:
                blocks.append(("p", list(para)))
                para = []
            blocks.append((f"h{len(m_h.group(1))}", m_h.group(2)))
            i += 1
            continue
        para.append(s)
        i += 1
    if para:
        blocks.append(("p", list(para)))
    return meta, blocks


def _match_image(s: str):
    m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
    return m.groups() if m else None


def inline(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(s))


def render_body(blocks, workdir: Path, figures_meta: dict) -> str:
    out = []
    for kind, data in blocks:
        if kind == "p":
            out.append(f"<p>{inline(' '.join(data))}</p>")
        elif kind in ("h1", "h2", "h3"):
            out.append(f"<{kind}>{inline(data)}</{kind}>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in data) + "</ul>")
        elif kind == "table":
            head = data[0] if data else []
            rows = data[1:] if len(data) > 1 else []
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
        elif kind == "img":
            ref, note = data["ref"], data["note"]
            fig_id = Path(ref).stem
            meta = figures_meta.get(fig_id, {})
            img_path = workdir / ref
            if not img_path.exists():
                out.append(f'<p class="fig-missing">[图片缺失: {escape(ref)}]</p>')
                continue
            b64 = base64.b64encode(img_path.read_bytes()).decode()
            suffix = img_path.suffix.lower().lstrip(".")
            mime = {"jpg": "jpeg", "tif": "tiff"}.get(suffix, suffix)
            cap = escape(meta.get("caption", ""))
            src_label = "视觉识别" if meta.get("confidence") == "high" else "依据：图题与正文"
            note_html = ""
            if note:
                body = inline(note)
                body = re.sub(r"^图解[:：]\s*", "", body)
                note_html = f'<div class="fig-note"><span class="fig-src">{escape(src_label)}</span>{body}</div>'
            out.append(
                f'<figure><img src="data:image/{mime};base64,{b64}" alt="{escape(fig_id)}">'
                f"<figcaption>{escape(fig_id.upper())}"
                + (f" · {cap}" if cap else "")
                + (f" · p.{meta['page']}" if meta.get("page") else "")
                + f"</figcaption>{note_html}</figure>"
            )
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="content.md + 论文原图 -> 单文件 HTML")
    p.add_argument("--content", required=True)
    p.add_argument("--workdir", required=True, help="extract.py 的输出目录（figures 所在）")
    p.add_argument("--out", required=True, help="输出 HTML 路径")
    args = p.parse_args()

    workdir = Path(args.workdir)
    meta, blocks = parse_content(Path(args.content).read_text(encoding="utf-8-sig"))

    figures_meta = {}
    fj = workdir / "figures.json"
    if fj.exists():
        for f in json.loads(fj.read_text(encoding="utf-8")):
            figures_meta[f["id"]] = f

    mode = meta.get("mode", "multimodal")
    banner = ""
    if mode == "text-only":
        banner = (
            '<div class="banner"><strong>非多模态生成</strong>：本讲解未结合图像视觉内容，'
            "图解仅依据图题与正文上下文，关键信息请回原文核对。</div>"
        )

    body = render_body(blocks, workdir, figures_meta)
    meta_line = " · ".join(x for x in (meta.get("authors", ""), meta.get("year", "")) if x)
    tpl = (SKILL_DIR / "templates" / "report.html.tpl").read_text(encoding="utf-8")
    html = (tpl
        .replace("{{title}}", escape(meta.get("title", "论文讲解")))
        .replace("{{meta_line}}", escape(meta_line))
        .replace("{{oneliner}}", escape(meta.get("oneliner", "")))
        .replace("{{banner}}", banner)
        .replace("{{body}}", body)
        .replace("{{generated_at}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    n_img = sum(1 for k, _ in blocks if k == "img")
    print(f"OK: {out}（内嵌图片 {n_img} 张，mode={mode}）")


if __name__ == "__main__":
    main()
