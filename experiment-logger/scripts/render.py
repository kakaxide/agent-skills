#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验日志渲染脚本。

子命令：
  init    创建 canonical 记录（record.json），实验子目录位于日志根目录下
  add     向记录追加 decision / failed_attempt / event
  render  由 canonical 记录渲染 human.md 与 agent.md

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
        "然后用 --log-root <目录> --save-default 重新执行 init。"
    )


def load_record(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"ERROR: record not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_record(record: dict, path: Path) -> None:
    try:
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        # 记录失败不阻塞实验：打印警告即可
        print(f"WARN: log write failed ({e}), will backfill at finalize", file=sys.stderr)


def cmd_init(args: argparse.Namespace) -> None:
    log_root = resolve_log_root(args.log_root).expanduser().resolve()
    if args.save_default:
        save_default_log_root(log_root)
    exp_id = args.exp_id or f"exp_{datetime.now().strftime('%Y%m%d_%H%M')}"
    exp_dir = log_root / exp_id
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
        "results": {"metrics": {}, "comparison": [], "summary": ""},
        "artifacts": [],
    }
    exp_dir.mkdir(parents=True, exist_ok=True)
    save_record(record, out)
    print(f"OK: record created -> {out}")
    print(f"日志根目录: {log_root}（首次使用请与用户确认；更换位置请用 --log-root --save-default）")
    print("提醒：开跑前请确认已登记复现目标（paper/target）。")


def cmd_add(args: argparse.Namespace) -> None:
    path = Path(args.record)
    record = load_record(path)
    entry = {"time": now(), "content": args.content}
    key = {
        "decision": "decisions",
        "failed_attempt": "failed_attempts",
        "event": "events",
    }.get(args.type)
    if key is None:
        sys.exit("ERROR: --type must be one of: decision, failed_attempt, event")
    if args.type == "failed_attempt" and args.error:
        entry["error"] = args.error
    record.setdefault(key, []).append(entry)
    record["updated_at"] = now()
    save_record(record, path)
    print(f"OK: {args.type} appended -> {path}")


# ---------- 渲染 ----------

def fmt(v) -> str:
    return str(v).replace("|", "\\|") if v not in (None, "") else "-"


def status_emoji(status: str) -> str:
    return {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "⏳")


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

    comp = record.get("results", {}).get("comparison") or []
    sources = {c.get("source") for c in comp if c.get("source")}
    ref_src = "、".join(sorted(sources)) if sources else "论文/基线"
    comp_rows = [
        f"| {fmt(c.get('metric'))} | {fmt(c.get('ours'))} | {fmt(c.get('reference'))} | {fmt(c.get('delta'))} |"
        for c in comp
    ]

    human = (TEMPLATE_DIR / "human.md.tpl").read_text(encoding="utf-8")
    human = (human
        .replace("{{title}}", record.get("title", ""))
        .replace("{{experiment_id}}", record.get("experiment_id", ""))
        .replace("{{status_emoji}}", status_emoji(record.get("status", "")))
        .replace("{{status}}", record.get("status", ""))
        .replace("{{updated_at}}", record.get("updated_at", ""))
        .replace("{{summary}}", record.get("results", {}).get("summary") or "（待 finalize 填写一句话结论）")
        .replace("{{human_params_rows}}", "\n".join(rows) or "| - | - |")
        .replace("{{reference_source}}", ref_src)
        .replace("{{comparison_rows}}", "\n".join(comp_rows) or "| - | - | - | - |")
    )
    (out_dir / "human.md").write_text(human, encoding="utf-8")

    # ----- agent 版 -----
    env = record.get("environment", {})
    goal = record.get("goal", {})
    code = record.get("code", {})
    data = record.get("data_provenance", {})
    results = record.get("results", {})

    def bullets(items) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- （无）"

    cmds = "\n".join(
        f"{i}. `{c.get('command', '')}`" + (f" —— {c['note']}" if c.get("note") else "")
        for i, c in enumerate(record.get("commands", []), 1)
    ) or "（无）"

    decisions = "\n".join(
        f"- `{d.get('time', '')}` {d.get('content', '')}"
        + (f"（放弃方案：{d['alternatives']}）" if d.get("alternatives") else "")
        for d in record.get("decisions", [])
    ) or "（无）"

    fails = "\n".join(
        f"- `{f.get('time', '')}` {f.get('content', '')}"
        + (f"  报错：{f['error']}" if f.get("error") else "")
        + (f"  解决：{f['resolution']}" if f.get("resolution") else "")
        for f in record.get("failed_attempts", [])
    ) or "（无）"

    events = "\n".join(f"- `{e.get('time', '')}` {e.get('content', '')}" for e in record.get("events", [])) or "（无）"

    arts = "\n".join(f"- `{a.get('path', '')}`（{a.get('kind', '')}）" for a in record.get("artifacts", [])) or "（无）"

    agent = (TEMPLATE_DIR / "agent.md.tpl").read_text(encoding="utf-8")
    agent = (agent
        .replace("{{title}}", record.get("title", ""))
        .replace("{{experiment_id}}", record.get("experiment_id", ""))
        .replace("{{status}}", record.get("status", ""))
        .replace("{{created_at}}", record.get("created_at", ""))
        .replace("{{updated_at}}", record.get("updated_at", ""))
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
        .replace("{{metrics_inline}}", json.dumps(results.get("metrics", {}), ensure_ascii=False))
        .replace("{{comparison_rows}}", "\n".join(comp_rows) or "| - | - | - | - | - |")
        .replace("{{artifacts_list}}", arts)
    )
    (out_dir / "agent.md").write_text(agent, encoding="utf-8")

    print(f"OK: rendered human.md, agent.md -> {out_dir}")


def cmd_render(args: argparse.Namespace) -> None:
    record = load_record(Path(args.record))
    render(record, Path(args.out_dir))


def main() -> None:
    p = argparse.ArgumentParser(description="实验日志渲染脚本（canonical 记录 -> 人版/agent 版）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="创建 canonical 记录（位于 <log_root>/<实验ID>/）")
    pi.add_argument("--log-root", default="", help="日志根目录；省略则读取默认配置")
    pi.add_argument("--save-default", action="store_true", help="把 --log-root 记为默认日志根目录")
    pi.add_argument("--exp-id", default="", help="实验 ID，默认 exp_YYYYMMDD_HHMM")
    pi.add_argument("--title", required=True, help="实验标题")
    pi.add_argument("--paper", required=True, help="复现目标论文")
    pi.add_argument("--target", default="", help="论文中的表/图，如 Table 2")
    pi.add_argument("--model", default="", help="模型")
    pi.add_argument("--dataset", default="", help="数据集")
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("add", help="追加 decision / failed_attempt / event")
    pa.add_argument("--record", required=True)
    pa.add_argument("--type", required=True, choices=["decision", "failed_attempt", "event"])
    pa.add_argument("--content", required=True)
    pa.add_argument("--error", default="", help="failed_attempt 的关键报错")
    pa.set_defaults(func=cmd_add)

    pr = sub.add_parser("render", help="渲染 human.md 与 agent.md")
    pr.add_argument("--record", required=True)
    pr.add_argument("--out-dir", required=True)
    pr.set_defaults(func=cmd_render)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
