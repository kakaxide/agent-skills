#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验日志与项目全流程追踪脚本。

子命令：
  init            创建 canonical 记录（record.json）；--project 可挂到项目流程下
  add             向记录追加 decision / failed_attempt / event（时间戳自动）
  set             点路径赋值，如 --key results.metrics.acc --value 0.86（时间戳自动）
  render          由 canonical 记录渲染 human.md 与 agent.md
  project init    创建项目流程（plan.json + PLAN.md 流程文档）
  project status  更新某步骤状态/小结/实验记录链接，并重渲染 PLAN.md
  project show    重渲染 PLAN.md
  project list    列出所有项目与进度
  compare         两实验核心指标对照表

日志根目录（log_root）规则：
  --log-root 显式指定 > ~/.experiment-logger/log_root.txt 中的默认值。
  两者都没有时，脚本退出并提示 agent 先询问用户日志存放地址。
  首次使用传 --save-default 可把日志根目录记为默认。

仅使用标准库。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "templates"
CONFIG_FILE = Path.home() / ".experiment-logger" / "log_root.txt"

STEP_EMOJI = {
    "pending": "⬜ 待开始",
    "in_progress": "🔄 进行中",
    "done": "✅ 已完成",
    "failed": "❌ 失败",
    "skipped": "⏭️ 跳过",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_default_log_root():
    if CONFIG_FILE.exists():
        p = CONFIG_FILE.read_text(encoding="utf-8").strip()
        return p or None
    return None


def save_default_log_root(log_root: Path) -> None:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(str(log_root), encoding="utf-8")
        print(f"OK: default log root saved -> {CONFIG_FILE}")
    except OSError as e:
        print(f"WARN: failed to save default log root ({e})", file=sys.stderr)


def resolve_log_root(explicit: str) -> Path:
    if explicit:
        return Path(explicit)
    default = load_default_log_root()
    if default:
        return Path(default)
    # 无默认目录：要求 agent 先询问用户，不得擅自决定存放位置
    sys.exit(
        "ACTION REQUIRED: 未设置日志根目录。请先询问用户日志希望存放在哪里，"
        "然后用 --log-root <目录> --save-default 重新执行。"
    )


def load_json(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"ERROR: file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: invalid JSON in {path}: {e}")


def load_record(path: Path) -> dict:
    return load_json(path)


def save_json(data: dict, path: Path, label: str = "record") -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        # 写入失败不阻塞实验：打印警告即可，finalize 会提示补全
        print(f"WARN: {label} write failed ({e}), will backfill at finalize", file=sys.stderr)


def save_record(record: dict, path: Path) -> None:
    save_json(record, path, "record")


def parse_value(s: str):
    """--value 尽量解析为 JSON 类型（数字/布尔/数组/对象），失败则按字符串。"""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s


def set_by_path(record: dict, dotted: str, value) -> None:
    """按 a.b.c 点路径赋值，中间层不存在则自动创建。"""
    keys = dotted.split(".")
    cur = record
    for k in keys[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[keys[-1]] = value


# ---------- 项目流程（PLAN） ----------

def project_dir(log_root: Path, name: str) -> Path:
    if not name or any(ch in name for ch in "/\\"):
        sys.exit("ERROR: --project 名称不能包含路径分隔符")
    return log_root / "projects" / name


def render_plan(plan: dict, pdir: Path) -> None:
    steps = plan.get("steps", [])
    done = sum(1 for s in steps if s.get("status") == "done")
    rows = []
    for s in steps:
        links = []
        for rec in s.get("records", []):
            p = Path(rec)
            target = p / "human.md" if p.suffix == "" else p.parent / "human.md" if p.name == "record.json" else p
            try:
                rel = "./" + target.resolve().relative_to(pdir.resolve()).as_posix()
            except ValueError:
                rel = str(target)
            links.append(f"[{p.parent.name if p.suffix else p.name}]({rel})")
        rows.append(
            f"| {s.get('id', '')} | {s.get('name', '')} | {STEP_EMOJI.get(s.get('status', 'pending'), s.get('status'))} "
            f"| {s.get('summary') or '-'} | {'、'.join(links) or '-'} |"
        )
    body = (TEMPLATE_DIR / "plan.md.tpl").read_text(encoding="utf-8")
    body = (body
        .replace("{{title}}", plan.get("title", ""))
        .replace("{{name}}", plan.get("name", ""))
        .replace("{{target}}", plan.get("target") or "-")
        .replace("{{paper}}", plan.get("paper") or "-")
        .replace("{{progress}}", f"{done}/{len(steps)}")
        .replace("{{updated_at}}", plan.get("updated_at", ""))
        .replace("{{step_rows}}", "\n".join(rows) or "| - | - | - | - | - |")
        .replace("{{notes}}", plan.get("notes") or "")
    )
    (pdir / "PLAN.md").write_text(body, encoding="utf-8")


def cmd_project_init(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    if args.save_default:
        save_default_log_root(log_root)
    pdir = project_dir(log_root, args.name)
    plan_path = pdir / "plan.json"
    if plan_path.exists() and not args.force:
        sys.exit(f"ERROR: project already exists: {plan_path}（覆盖请加 --force）")

    steps = []
    for i, spec in enumerate(args.step or [], 1):
        name, _, desc = spec.partition("：") if "：" in spec else spec.partition(":")
        steps.append({
            "id": i, "name": name.strip(), "description": desc.strip(),
            "status": "pending", "summary": "", "records": [], "updated_at": now(),
        })
    plan = {
        "name": args.name, "title": args.title, "paper": args.paper or "",
        "target": args.target or "", "notes": "",
        "created_at": now(), "updated_at": now(), "steps": steps,
    }
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "steps").mkdir(exist_ok=True)
    save_json(plan, plan_path, "plan")
    render_plan(plan, pdir)
    print(f"OK: project created -> {pdir}")
    print(f"流程文档: {pdir / 'PLAN.md'}（共 {len(steps)} 步）")
    print("提醒：每步实验用 init --project 挂到该项目；完成后用 project status 标记并链接实验记录。")


def cmd_project_status(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    pdir = project_dir(log_root, args.name)
    plan_path = pdir / "plan.json"
    plan = load_json(plan_path)
    steps = plan.get("steps", [])
    step = next((s for s in steps if s.get("id") == args.step), None)
    if step is None:
        sys.exit(f"ERROR: step {args.step} not found（现有步骤: {[s.get('id') for s in steps]}）")

    changed = False
    if args.status:
        if args.status not in STEP_EMOJI:
            sys.exit(f"ERROR: --status must be one of: {', '.join(STEP_EMOJI)}")
        step["status"] = args.status
        changed = True
    if args.summary is not None:
        step["summary"] = args.summary
        changed = True
    if args.link:
        link = Path(args.link).resolve()
        target = link.parent if link.suffix == ".json" else link
        recs = step.setdefault("records", [])
        if str(target) not in recs:
            recs.append(str(target))
        changed = True
    if args.step_desc is not None:
        step["description"] = args.step_desc
        changed = True
    if changed:
        step["updated_at"] = now()
        plan["updated_at"] = now()
        save_json(plan, plan_path, "plan")
        render_plan(plan, pdir)
        print(f"OK: step {args.step} updated, PLAN.md re-rendered -> {pdir / 'PLAN.md'}")
    else:
        print("WARN: 未提供任何更新项（--status/--summary/--link/--step-desc）")


def cmd_project_show(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    pdir = project_dir(log_root, args.name)
    plan = load_json(pdir / "plan.json")
    render_plan(plan, pdir)
    print(f"OK: PLAN.md re-rendered -> {pdir / 'PLAN.md'}")


def cmd_project_list(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    projs = log_root / "projects"
    if not projs.exists():
        print("（暂无项目）")
        return
    for d in sorted(projs.iterdir()):
        plan_path = d / "plan.json"
        if not plan_path.exists():
            continue
        plan = load_json(plan_path)
        steps = plan.get("steps", [])
        done = sum(1 for s in steps if s.get("status") == "done")
        cur = next((s for s in steps if s.get("status") == "in_progress"), None)
        cur_txt = f"，当前卡在 step {cur['id']}（{cur['name']}）" if cur else ""
        print(f"- {plan.get('name')}: {plan.get('title')} [{done}/{len(steps)}]{cur_txt}")


def cmd_project_add_step(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    pdir = project_dir(log_root, args.name)
    plan = load_json(pdir / "plan.json")
    name, _, desc = args.step.partition("：") if "：" in args.step else args.step.partition(":")
    steps = plan.setdefault("steps", [])
    sid = (steps[-1]["id"] + 1) if steps else 1
    steps.append({"id": sid, "name": name.strip(), "description": desc.strip(),
                  "status": "pending", "summary": "", "records": [], "updated_at": now()})
    plan["updated_at"] = now()
    save_json(plan, pdir / "plan.json", "plan")
    render_plan(plan, pdir)
    print(f"OK: step {sid} added, PLAN.md re-rendered")


# ---------- 实验记录 ----------

def cmd_init(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    if args.save_default:
        save_default_log_root(log_root)
    exp_id = args.exp_id or f"exp_{datetime.now().strftime('%Y%m%d_%H%M')}"
    exp_dir = log_root / exp_id
    project_info = {}
    if args.project:
        pdir = project_dir(log_root, args.project)
        if not (pdir / "plan.json").exists():
            sys.exit(f"ERROR: project not found: {pdir / 'plan.json'}（先用 project init 创建）")
        exp_dir = pdir / "steps" / exp_id
        project_info = {"name": args.project, "plan": str(pdir / "plan.json")}
    out = exp_dir / "record.json"
    if out.exists():
        sys.exit(f"ERROR: record already exists: {out}")
    record = {
        "experiment_id": exp_id,
        "title": args.title,
        "goal": {"paper": args.paper, "target": args.target or "", "expected_metrics": {}},
        "status": "running",
        "created_at": now(),
        "updated_at": now(),
        "log_root": str(log_root),
        "params": {"model": args.model or "", "dataset": args.dataset or "", "hyperparameters": {}, "hardware": ""},
        "environment": {},
        "commands": [],
        "data_provenance": {},
        "code": {},
        "decisions": [],
        "failed_attempts": [],
        "events": [],
        "milestones": [],
        "results": {"metrics": {}, "comparison": [], "findings": [], "summary": "", "headline": []},
        "artifacts": [],
    }
    if project_info:
        record["project"] = project_info
    exp_dir.mkdir(parents=True, exist_ok=True)
    save_record(record, out)
    print(f"OK: record created -> {out}")
    print(f"日志根目录: {log_root}（首次使用请与用户确认；更换位置请用 --log-root --save-default）")
    if project_info:
        print(f"项目流程: {project_info['plan']}")
    print("提醒：开跑前请确认已登记复现目标（paper/target）。")


def cmd_add(args: argparse.Namespace) -> None:
    path = Path(args.record)
    record = load_record(path)
    entry = {"time": now(), "content": args.content}
    key = {
        "decision": "decisions",
        "failed_attempt": "failed_attempts",
        "event": "events",
        "milestone": "milestones",
    }.get(args.type)
    if key is None:
        sys.exit("ERROR: --type must be one of: decision, failed_attempt, event, milestone")
    if args.type == "failed_attempt" and args.error:
        entry["error"] = args.error
    if args.type == "milestone":
        entry["name"] = args.name or entry["content"][:20]
        entry["summary"] = args.content
    record.setdefault(key, []).append(entry)
    record["updated_at"] = now()  # updated_at 由工具自动打，不依赖手填
    save_record(record, path)
    print(f"OK: {args.type} appended -> {path}")


def cmd_set(args: argparse.Namespace) -> None:
    path = Path(args.record)
    record = load_record(path)
    value = parse_value(args.value)
    set_by_path(record, args.key, value)
    record["updated_at"] = now()
    save_record(record, path)
    print(f"OK: {args.key} = {json.dumps(value, ensure_ascii=False)} -> {path}")


def cmd_compare(args: argparse.Namespace) -> None:
    ra, rb = load_record(Path(args.record_a)), load_record(Path(args.record_b))
    ma, mb = ra.get("results", {}).get("metrics", {}), rb.get("results", {}).get("metrics", {})
    keys = ([k.strip() for k in args.metrics.split(",") if k.strip()] if args.metrics
            else list(dict.fromkeys(list(ra.get("results", {}).get("headline", [])) +
                                    list(mb.keys()) + list(ma.keys()))))
    print(f"| 指标 | {ra.get('experiment_id', 'A')} | {rb.get('experiment_id', 'B')} | Δ(B-A) |")
    print("|---|---|---|---|")
    for k in keys:
        va, vb = ma.get(k, "-"), mb.get(k, "-")
        delta = "-"
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta = round(vb - va, 6)
        print(f"| {k} | {va} | {vb} | {delta} |")
    sa, sb = ra.get("results", {}).get("summary", ""), rb.get("results", {}).get("summary", "")
    if sa or sb:
        print(f"\nA 结论：{sa or '-'}\nB 结论：{sb or '-'}")


# ---------- 渲染 ----------

def fmt(v) -> str:
    return str(v).replace("|", "\\|") if v not in (None, "") else "-"


def is_path_like(s: str) -> bool:
    return ("/" in s or "\\" in s) and not s.startswith("论文")


def status_emoji(status: str) -> str:
    return {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "⏳")


def sort_by_time(items: list) -> list:
    return sorted(items or [], key=lambda x: x.get("time", ""))


def render(record: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # ----- 人版 -----
    params = record.get("params", {})
    rows = [f"| 模型 | {fmt(params.get('model'))} |", f"| 数据 | {fmt(params.get('dataset'))} |"]
    if params.get("hardware"):
        rows.append(f"| 硬件 | {fmt(params['hardware'])} |")
    for k, v in (params.get("hyperparameters") or {}).items():
        rows.append(f"| {fmt(k)} | {fmt(v)} |")
    for k, v in params.items():
        if k not in ("model", "dataset", "hyperparameters", "hardware") and v not in (None, "", {}, []):
            rows.append(f"| {fmt(k)} | {fmt(v)} |")
    n_param_rows = len(rows)

    results = record.get("results", {})
    comp = results.get("comparison") or []
    # 人版 source 列只留文件名/短出处，完整路径只在 agent 版出现（防表格横向爆炸）
    def short_src(s: str) -> str:
        return Path(s.replace("\\", "/")).name if is_path_like(s) else s
    sources = {short_src(c.get("source")) for c in comp if c.get("source")}
    ref_src = "、".join(sorted(sources)) if sources else "论文/基线"
    comp_rows = [
        f"| {fmt(c.get('metric'))} | {fmt(c.get('ours'))} | {fmt(short_src(c.get('source')) if c.get('source') else c.get('reference'))} | {fmt(c.get('delta'))} |"
        for c in comp
    ]

    # 关键结论（findings）：结构化分析产出，人版单独渲染
    findings = results.get("findings") or []
    if findings:
        f_rows = "\n".join(
            f"| {fmt(f.get('conclusion'))} | {fmt(f.get('evidence'))} | {fmt(f.get('confidence', 'medium'))} |"
            for f in findings
        )
        findings_section = f"\n## 关键结论\n\n| 结论 | 依据 | 置信度 |\n|---|---|---|\n{f_rows}\n"
    else:
        findings_section = ""

    # 阶段小结（milestones）：多阶段实验的结论演进，仅在有内容时渲染
    milestones = sort_by_time(record.get("milestones") or [])
    if milestones:
        m_lines = "\n".join(f"- `{m.get('time', '')}` **{m.get('name', '')}**：{m.get('summary', '')}" for m in milestones)
        milestones_section = f"\n## 阶段小结\n\n{m_lines}\n"
    else:
        milestones_section = ""

    human = (TEMPLATE_DIR / "human.md.tpl").read_text(encoding="utf-8")
    human = (human
        .replace("{{title}}", record.get("title", ""))
        .replace("{{experiment_id}}", record.get("experiment_id", ""))
        .replace("{{status_emoji}}", status_emoji(record.get("status", "")))
        .replace("{{status}}", record.get("status", ""))
        .replace("{{updated_at}}", record.get("updated_at", ""))
        .replace("{{summary}}", results.get("summary") or "（待 finalize 填写一句话结论）")
        .replace("{{human_params_rows}}", "\n".join(rows) or "| - | - |")
        .replace("{{reference_source}}", ref_src)
        .replace("{{comparison_rows}}", "\n".join(comp_rows) or "| - | - | - | - |")
        .replace("{{findings_section}}", findings_section)
        .replace("{{milestones_section}}", milestones_section)
    )
    (out_dir / "human.md").write_text(human, encoding="utf-8")
    record["_human_param_rows"] = n_param_rows
    record["_human_line_count"] = len(human.splitlines())

    # ----- agent 版 -----
    env = record.get("environment", {})
    goal = record.get("goal", {})
    code = record.get("code", {})
    data = record.get("data_provenance", {})
    metrics = results.get("metrics", {})

    def bullets(items) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- （无）"

    cmds = "\n".join(
        f"{i}. `{c.get('command', '')}`" + (f" —— {c['note']}" if c.get("note") else "")
        for i, c in enumerate(record.get("commands", []), 1)
    ) or "（无）"

    decisions = "\n".join(
        f"- `{d.get('time', '')}` {d.get('content', '')}"
        + (f"（放弃方案：{d['alternatives']}）" if d.get("alternatives") else "")
        for d in sort_by_time(record.get("decisions"))
    ) or "（无）"

    fails = "\n".join(
        f"- `{f.get('time', '')}` {f.get('content', '')}"
        + (f"  报错：{f['error']}" if f.get("error") else "")
        + (f"  解决：{f['resolution']}" if f.get("resolution") else "")
        for f in sort_by_time(record.get("failed_attempts"))
    ) or "（无）"

    events = "\n".join(f"- `{e.get('time', '')}` {e.get('content', '')}" for e in sort_by_time(record.get("events"))) or "（无）"

    findings_detail = "\n".join(
        f"- **{f.get('conclusion', '')}**（置信度 {f.get('confidence', 'medium')}）\n  依据：{f.get('evidence', '')}"
        for f in findings
    ) or "（无）"

    arts = "\n".join(f"- `{a.get('path', '')}`（{a.get('kind', '')}）" for a in record.get("artifacts", [])) or "（无）"

    proj = record.get("project") or {}

    agent = (TEMPLATE_DIR / "agent.md.tpl").read_text(encoding="utf-8")
    agent = (agent
        .replace("{{title}}", record.get("title", ""))
        .replace("{{experiment_id}}", record.get("experiment_id", ""))
        .replace("{{status}}", record.get("status", ""))
        .replace("{{created_at}}", record.get("created_at", ""))
        .replace("{{updated_at}}", record.get("updated_at", ""))
        .replace("{{project_line}}", f"- 所属项目：{proj.get('name', '')}（流程文档：{proj.get('plan', '')}）" if proj else "")
        .replace("{{goal_paper}}", fmt(goal.get("paper")))
        .replace("{{goal_target}}", fmt(goal.get("target")))
        .replace("{{expected_metrics}}", json.dumps(goal.get("expected_metrics", {}), ensure_ascii=False))
        .replace("{{env_os}}", fmt(env.get("os")))
        .replace("{{env_python}}", fmt(env.get("python")))
        .replace("{{env_cuda}}", fmt(env.get("cuda")))
        .replace("{{env_gpu}}", fmt(env.get("gpu")))
        .replace("{{env_seed}}", fmt(env.get("random_seed")))
        .replace("{{env_packages}}", "\n".join(f"- {k}: {v}" for k, v in (env.get("packages") or {}).items()) or "- （未记录）")
        .replace("{{code_repo}}", fmt(code.get("repo")))
        .replace("{{code_commit}}", fmt(code.get("commit")))
        .replace("{{code_branch}}", fmt(code.get("branch")))
        .replace("{{code_dirty}}", "、".join(code.get("dirty_files", [])) or "（无）")
        .replace("{{commands_list}}", cmds)
        .replace("{{config_json}}", json.dumps(record.get("config", {}), ensure_ascii=False, indent=2))
        .replace("{{data_source}}", fmt(data.get("source")))
        .replace("{{data_path}}", fmt(data.get("path")))
        .replace("{{data_hash}}", fmt(data.get("hash")))
        .replace("{{data_preprocessing}}", bullets(data.get("preprocessing", [])))
        .replace("{{decisions_list}}", decisions)
        .replace("{{failed_attempts_list}}", fails)
        .replace("{{events_list}}", events)
        .replace("{{milestones_list}}", milestones and "\n".join(
            f"- `{m.get('time', '')}` **{m.get('name', '')}**：{m.get('summary', '')}" for m in milestones) or "（无）")
        .replace("{{metrics_inline}}", json.dumps(metrics, ensure_ascii=False))
        .replace("{{headline_line}}", "、".join(results.get("headline", [])) or "（未指定，取前 3 项）")
        .replace("{{comparison_full_rows}}", "\n".join(
            f"| {fmt(c.get('metric'))} | {fmt(c.get('ours'))} | {fmt(c.get('reference'))} | {fmt(c.get('delta'))} | {fmt(c.get('source'))} |"
            for c in comp) or "| - | - | - | - | - |")
        .replace("{{findings_detail}}", findings_detail)
        .replace("{{artifacts_list}}", arts)
    )
    (out_dir / "agent.md").write_text(agent, encoding="utf-8")

    print(f"OK: rendered human.md, agent.md -> {out_dir}")


def cmd_render(args: argparse.Namespace) -> None:
    record = load_record(Path(args.record))
    render(record, Path(args.out_dir))


def main() -> None:
    p = argparse.ArgumentParser(description="实验日志与项目全流程追踪（canonical 记录 -> 人版/agent 版/PLAN）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="创建 canonical 记录；--project 挂到项目流程下")
    pi.add_argument("--log-root", default="", help="日志根目录；省略则读取默认配置")
    pi.add_argument("--save-default", action="store_true", help="把 --log-root 记为默认日志根目录")
    pi.add_argument("--exp-id", default="", help="实验 ID，默认 exp_YYYYMMDD_HHMM")
    pi.add_argument("--project", default="", help="挂到指定项目流程（先 project init 创建）")
    pi.add_argument("--title", required=True, help="实验标题")
    pi.add_argument("--paper", required=True, help="复现目标论文")
    pi.add_argument("--target", default="", help="论文中的表/图，如 Table 2")
    pi.add_argument("--model", default="", help="模型")
    pi.add_argument("--dataset", default="", help="数据集")
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("add", help="追加 decision / failed_attempt / event / milestone（时间戳自动）")
    pa.add_argument("--record", required=True)
    pa.add_argument("--type", required=True, choices=["decision", "failed_attempt", "event", "milestone"])
    pa.add_argument("--content", required=True)
    pa.add_argument("--error", default="", help="failed_attempt 的关键报错")
    pa.add_argument("--name", default="", help="milestone 的阶段名")
    pa.set_defaults(func=cmd_add)

    ps = sub.add_parser("set", help="点路径赋值，如 --key results.metrics.acc --value 0.86（时间戳自动）")
    ps.add_argument("--record", required=True)
    ps.add_argument("--key", required=True, help="点路径，如 results.summary 或 params.hyperparameters.lr")
    ps.add_argument("--value", required=True, help="值；JSON 可解析则按类型解析，否则按字符串")
    ps.set_defaults(func=cmd_set)

    pr = sub.add_parser("render", help="渲染 human.md 与 agent.md")
    pr.add_argument("--record", required=True)
    pr.add_argument("--out-dir", required=True)
    pr.set_defaults(func=cmd_render)

    pc = sub.add_parser("compare", help="两实验核心指标对照表")
    pc.add_argument("--record-a", required=True)
    pc.add_argument("--record-b", required=True)
    pc.add_argument("--metrics", default="", help="逗号分隔的指标名；省略则用 A 的 headline + 两者全部指标")
    pc.set_defaults(func=cmd_compare)

    pj = sub.add_parser("project", help="项目流程文档（PLAN.md）管理")
    psub = pj.add_subparsers(dest="pcmd", required=True)

    pji = psub.add_parser("init", help="创建项目流程")
    pji.add_argument("--log-root", default="")
    pji.add_argument("--save-default", action="store_true")
    pji.add_argument("--name", required=True, help="项目名（作目录名，不含路径分隔符）")
    pji.add_argument("--title", required=True, help="项目标题，如 复现 XX 论文 Table 2")
    pji.add_argument("--paper", default="", help="目标论文")
    pji.add_argument("--target", default="", help="目标表/图")
    pji.add_argument("--step", action="append", required=True, help='步骤，格式 "名称:描述"，可重复传')
    pji.add_argument("--force", action="store_true", help="覆盖已存在项目")
    pji.set_defaults(func=cmd_project_init)

    pst = psub.add_parser("status", help="更新步骤状态/小结/实验记录链接")
    pst.add_argument("--log-root", default="")
    pst.add_argument("--name", required=True)
    pst.add_argument("--step", required=True, type=int, help="步骤编号")
    pst.add_argument("--status", default="", help=f"one of: {', '.join(STEP_EMOJI)}")
    pst.add_argument("--summary", default=None, help="一句话小结（实验做到什么程度）")
    pst.add_argument("--link", default="", help="实验 record.json 或其目录路径，将索引到 PLAN.md")
    pst.add_argument("--step-desc", default=None, help="修改步骤描述")
    pst.set_defaults(func=cmd_project_status)

    psh = psub.add_parser("show", help="重渲染 PLAN.md")
    psh.add_argument("--log-root", default="")
    psh.add_argument("--name", required=True)
    psh.set_defaults(func=cmd_project_show)

    pls = psub.add_parser("list", help="列出所有项目与进度")
    pls.add_argument("--log-root", default="")
    pls.set_defaults(func=cmd_project_list)

    pas = psub.add_parser("add-step", help="给项目追加步骤")
    pas.add_argument("--log-root", default="")
    pas.add_argument("--name", required=True)
    pas.add_argument("--step", required=True, help='格式 "名称:描述"')
    pas.set_defaults(func=cmd_project_add_step)

    args = p.parse_args()
    if args.cmd == "project":
        args.func(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
