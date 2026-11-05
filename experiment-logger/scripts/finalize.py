#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验结束 finalize：校验 canonical 记录完整性 -> 渲染双日志 -> 给出结论。

用法：
  python scripts/finalize.py --record runs/exp_xxx/record.json \
      [--results runs/exp_xxx/results.json] [--out-dir runs/exp_xxx] [--strict]

结论：
  PASS  记录完整，双日志已生成
  WARN  有缺失项（决策缺失、报错未记录、时间戳乱序等），已生成日志但需补全
  FAIL  缺少必需字段，--strict 时以非零码退出

仅使用标准库。
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import load_record, render, status_emoji, fmt, is_path_like  # noqa: E402


def parse_ts(s: str):
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt
    except (ValueError, TypeError):
        return None


def check_timestamps(record: dict, warnings: list) -> None:
    """时间戳校验：乱序 WARN、未来时间 WARN。渲染时由脚本统一按时间排序。"""
    now_local = datetime.now().astimezone()
    for key in ("decisions", "failed_attempts", "events", "milestones"):
        items = record.get(key) or []
        times = [parse_ts(x.get("time", "")) for x in items]
        if any(t is None for t in times):
            warnings.append(f"{key} 存在无法解析的时间戳")
            continue
        for t in times:
            if t > now_local + timedelta(minutes=5):
                warnings.append(f"{key} 存在未来时间戳: {t.isoformat()}")
                break
        ordered = [t for t in times]
        if ordered != sorted(ordered):
            warnings.append(f"{key} 时间戳乱序（渲染时已自动按时间排序，建议补录时修正源头）")


def check_paths(record: dict, record_dir: Path, warnings: list) -> None:
    """comparison 引用的路径与产物路径存在性检查。"""
    for c in record.get("results", {}).get("comparison", []) or []:
        src = c.get("source") or ""
        if is_path_like(src):
            p = Path(src)
            if not (p.is_absolute() and p.exists()) and not (record_dir / src).exists():
                warnings.append(f"comparison 出处路径不存在: {src}")
    for a in record.get("artifacts", []) or []:
        p = Path(a.get("path", ""))
        if p.is_absolute():
            if not p.exists():
                warnings.append(f"产物路径不存在: {p}")
        elif not (record_dir / p).exists():
            warnings.append(f"产物路径不存在（相对记录目录）: {p}")


def validate(record: dict, warnings: list, errors: list, record_dir: Path) -> None:
    """按 SKILL.md 的检查点要求校验记录。"""
    required_top = ["experiment_id", "title", "goal", "status", "created_at", "updated_at", "params", "environment", "commands", "results", "artifacts"]
    for k in required_top:
        if k not in record or record[k] in (None, "", {}, []):
            errors.append(f"缺少必需字段: {k}")

    goal = record.get("goal") or {}
    if not goal.get("paper"):
        errors.append("开跑前未登记复现目标（goal.paper 为空）——违反检查点 1")
    if not (record.get("params") or {}).get("model"):
        warnings.append("params.model 为空")
    if not (record.get("params") or {}).get("dataset"):
        warnings.append("params.dataset 为空")
    if not (record.get("environment") or {}).get("os"):
        warnings.append("环境指纹不完整（environment.os 缺失），agent 版可复现性下降")
    if not (record.get("environment") or {}).get("python"):
        warnings.append("环境指纹不完整（environment.python 缺失）")
    if not (record.get("commands") or []):
        warnings.append("无完整命令序列（commands 为空），agent 版无法据此重建实验")
    if not (record.get("artifacts") or []):
        warnings.append("无产物路径（artifacts 为空）")

    if not (record.get("decisions") or []) and not (record.get("failed_attempts") or []):
        warnings.append("全程无决策记录也无失败记录——请确认实验确实没有非显然选择与报错")

    env = record.get("environment") or {}
    missing_env = [k for k in ("os", "python", "cuda", "gpu", "packages") if not env.get(k)]
    if missing_env:
        warnings.append(f"环境指纹缺失项: {', '.join(missing_env)}")

    # 时间戳与路径
    check_timestamps(record, warnings)
    check_paths(record, record_dir, warnings)


def post_render_checks(record: dict, human_path: Path, warnings: list, errors: list) -> None:
    """渲染后检查：参数表行数上限、human.md 一屏。"""
    n_rows = record.get("_human_param_rows", 0)
    if n_rows > 15:
        errors.append(f"人版参数表 {n_rows} 行，超过 15 行上限——把非关键参数移入 config，仅保留偏离默认值的核心参数")
    elif n_rows > 10:
        warnings.append(f"人版参数表 {n_rows} 行，超过建议的 10 行——考虑精简")

    try:
        n_lines = len(human_path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return
    if n_lines > 40:
        warnings.append(f"human.md 共 {n_lines} 行，超过一屏建议（约 40 行）——检查 comparison/findings 是否堆砌")


def update_index(record: dict, exp_dir: Path, log_root: Path) -> None:
    """向 <log_root>/INDEX.md 追加一行实验摘要（幂等：同实验 ID 先移除旧行再追加）。"""
    index_path = log_root / "INDEX.md"
    date = (record.get("updated_at") or "")[:10]
    exp_id = record.get("experiment_id", exp_dir.name)
    status = f"{status_emoji(record.get('status', ''))} {record.get('status', '')}"

    metrics = record.get("results", {}).get("metrics") or {}
    headline = record.get("results", {}).get("headline") or []
    # 核心指标顺序由实验作者决定：优先 headline 字段，缺省退回前 3 个
    keys = [k for k in headline if k in metrics] or list(metrics.keys())[:3]
    summary = "；".join(f"{k}={metrics[k]}" for k in keys[:3]) or "-"

    try:
        rel = exp_dir.resolve().relative_to(log_root.resolve()).as_posix()
    except ValueError:
        rel = str(exp_dir)
    row = f"| {date} | {exp_id} | {record.get('title', '')} | {status} | {summary} | [日志](./{rel}/human.md) |"

    header = (
        "# 实验日志索引\n\n"
        "由 experiment-logger finalize 自动维护，一实验一行；详情见各实验子目录。\n\n"
        "| 日期 | 实验 ID | 标题 | 状态 | 核心指标 | 日志 |\n"
        "|---|---|---|---|---|---|\n"
    )
    lines = []
    if index_path.exists():
        lines = index_path.read_text(encoding="utf-8").splitlines()
        lines = [ln for ln in lines if not (ln.startswith("|") and f"| {exp_id} |" in ln)]
    else:
        lines = header.splitlines()
    lines.append(row)
    try:
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"OK: index updated -> {index_path}")
    except OSError as e:
        print(f"WARN: index write failed ({e}), will backfill at next finalize", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description="实验 finalize：校验 + 渲染双日志")
    p.add_argument("--record", required=True, help="canonical record.json 路径")
    p.add_argument("--results", default="", help="results JSON 路径（可选，将合并进 record.results）")
    p.add_argument("--out-dir", default="", help="输出目录，默认与 record.json 同目录")
    p.add_argument("--log-root", default="", help="日志根目录（INDEX.md 所在处），默认取 record.log_root")
    p.add_argument("--strict", action="store_true", help="FAIL 时以非零退出码结束")
    args = p.parse_args()

    record_path = Path(args.record)
    record = load_record(record_path)
    record_dir = record_path.parent

    if args.results:
        res = json.loads(Path(args.results).read_text(encoding="utf-8-sig"))
        record.setdefault("results", {}).update(res)
        record["updated_at"] = record.get("updated_at")

    errors: list = []
    warnings: list = []
    validate(record, warnings, errors, record_dir)

    out_dir = Path(args.out_dir) if args.out_dir else record_path.parent
    render(record, out_dir)
    post_render_checks(record, out_dir / "human.md", warnings, errors)

    log_root = Path(args.log_root) if args.log_root else Path(record.get("log_root") or out_dir.parent)
    log_root.mkdir(parents=True, exist_ok=True)
    update_index(record, out_dir, log_root)

    if record.get("project"):
        print(f"提醒：本实验属于项目 {record['project'].get('name', '')}，"
              f"完成后用 project status --link {record_path} 更新流程文档。")

    print("\n===== finalize 校验报告 =====")
    for e in errors:
        print(f"[ERROR] {e}")
    for w in warnings:
        print(f"[WARN]  {w}")
    if not errors and not warnings:
        print("记录完整，无缺失项。")

    if errors:
        print("\n结论: FAIL —— 请补全 canonical 记录后重跑 finalize。实验状态记为未完成。")
        if args.strict:
            sys.exit(2)
    elif warnings:
        print("\n结论: WARN —— 双日志已生成，但存在缺失项，建议补全后重跑 finalize。")
    else:
        print("\n结论: PASS —— 双日志已生成。")


if __name__ == "__main__":
    main()
