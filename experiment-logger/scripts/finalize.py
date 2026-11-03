#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验结束 finalize：校验 canonical 记录完整性 -> 渲染双日志 -> 给出结论。

用法：
  python scripts/finalize.py --record runs/exp_xxx/record.json \
      [--results runs/exp_xxx/results.json] [--out-dir runs/exp_xxx] [--strict]

结论：
  PASS  记录完整，双日志已生成
  WARN  有缺失项（决策缺失、报错未记录等），已生成日志但需补全
  FAIL  缺少必需字段（results / artifacts 等），--strict 时以非零码退出

仅使用标准库。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import load_record, render, status_emoji  # noqa: E402


def validate(record: dict, warnings: list, errors: list) -> None:
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


def update_index(record: dict, exp_dir: Path, log_root: Path) -> None:
    """向 <log_root>/INDEX.md 追加一行实验摘要（幂等：同实验 ID 先移除旧行再追加）。"""
    index_path = log_root / "INDEX.md"
    date = (record.get("updated_at") or "")[:10]
    exp_id = record.get("experiment_id", exp_dir.name)
    status = f"{status_emoji(record.get('status', ''))} {record.get('status', '')}"
    metrics = record.get("results", {}).get("metrics") or {}
    summary = "；".join(f"{k}={v}" for k, v in list(metrics.items())[:3]) or "-"
    row = f"| {date} | {exp_id} | {record.get('title', '')} | {status} | {summary} | [日志](./{exp_id}/human.md) |"

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

    if args.results:
        res = json.loads(Path(args.results).read_text(encoding="utf-8-sig"))
        record["results"].update(res)
        record["updated_at"] = record.get("updated_at")

    errors: list = []
    warnings: list = []
    validate(record, warnings, errors)

    out_dir = Path(args.out_dir) if args.out_dir else record_path.parent
    render(record, out_dir)

    log_root = Path(args.log_root) if args.log_root else Path(record.get("log_root") or out_dir.parent)
    log_root.mkdir(parents=True, exist_ok=True)
    update_index(record, out_dir, log_root)

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
