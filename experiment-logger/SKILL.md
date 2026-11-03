---
name: experiment-logger
description: 实验日志强制记录 Skill。当 agent 开始训练/评测/复现论文实验、跑任何会产生结果数据的脚本、做出实验相关决策、或遇到实验报错时，必须使用本 Skill 在固定检查点记录实验。产出双日志：人版极简（主要参数 + 效果），agent 版详尽（可复现）。触发词包括：实验、训练、评测、复现、跑模型、baseline、消融等。
---

# 你必须记录

以下约束为命令式，优先级高于本文件中其它一切内容：

1. **实验开始前，你必须先登记目标**：哪篇论文、哪张表/图、期望指标。未登记不得开跑。
2. **做出任何非显然选择时（换版本、跳步骤、改参数、换数据），你必须立即写一条决策记录。**
3. **任何报错后重试之前，你必须先写一条 failed_attempt，再继续。**
4. **实验结束时，你必须运行 finalize 生成双日志。finalize 未完成，实验就不算结束。**
5. **记录失败时，你不得中断实验。打印一行警告后继续实验，结束时补记。**
6. **人版和 agent 版必须由同一份 canonical 记录渲染生成，严禁分别手写。**
7. **人版严禁出现完整命令、环境细节、失败过程。这些只属于 agent 版。**

---

## 本 Skill 如何保证 agent 时刻记得记录

记录是 agent 行为的强制环节，不是可选功能。本 Skill 通过五个强制检查点把记录织入实验工作流，而不是依赖 agent 自觉：

| 检查点 | 时机 | agent 必须做什么 | 未做的后果 |
|---|---|---|---|
| 开跑前 | 任何实验脚本执行前 | 创建 canonical 记录，登记复现目标 | 不得开跑（或至少显式输出"跳过登记"的警告） |
| 决策时 | 做出非显然选择时 | 追加一条 decision | finalize 时被检出为"决策缺失" |
| 失败时 | 报错后、重试前 | 追加一条 failed_attempt | finalize 时被检出为"报错未记录" |
| 心跳 | 长实验每隔约 30 分钟或每个 epoch/阶段结束 | 补记关键事件 | 结束日志不完整 |
| 结束时 | 实验完成/中止 | 运行 finalize，渲染双日志 | 实验状态记为未完成 |

提醒机制的三条设计原则：

- **轻量不阻塞**：检查点只要求写 JSON/追加记录，不拦截实验执行。唯一例外是"开跑前未登记"，此时至少要强提醒。
- **有痕迹**：被跳过的检查点不会消失，finalize 校验会列出所有缺失项并要求补全。
- **单一事实源**：agent 全程只维护一份 canonical 记录（JSON），人版与 agent 版均为其渲染视图，从机制上杜绝两份手写日志的分叉。

## 双日志定位

### 人版（human log，给人看，一屏内）

只保留三块：

- **主要实验参数**：不超过 10 项关键参数（模型、数据、核心超参、硬件规模）。默认值不写。
- **效果**：核心指标 + 与论文/基线的对照（有论文目标时给偏差）。
- **一行状态**：✅ / ⚠️ / ❌ + 一句话结论。

### Agent 版（agent log，给 agent 看，可复现）

承载重建实验所需的一切：

- 环境指纹（OS、Python、CUDA、关键包版本、硬件）
- 完整命令序列与全量配置
- 数据溯源（来源、路径、hash、预处理步骤）
- 代码 commit 与工作区状态
- 全部失败尝试与决策理由
- 产物路径（checkpoint、日志、指标文件）

验收标准：另一个 agent 仅凭 agent 版日志即可重建实验配置。

## 使用接口

canonical 记录结构见 `schema/record.schema.json`。

### 1. 开跑前：创建记录

```bash
python scripts/render.py init --out runs/exp_20261103_1430/record.json \
  --paper "Attention Is All You Need" --target "Table 2 / BLEU 28.4" --title "复现 Transformer base"
```

或直接手写初始 JSON（必须包含 goal、status=running）。

### 2. 实验过程中：追加记录

决策与失败用追加方式写入 canonical 记录（脚本或直接编辑 JSON 均可）：

```bash
python scripts/render.py add --record runs/exp_xxx/record.json \
  --type decision --content "PyTorch 从 2.1 降到 2.0，复现论文原始环境"

python scripts/render.py add --record runs/exp_xxx/record.json \
  --type failed_attempt --content "CUDA OOM，batch 32->16 后重试"
```

### 3. 实验结束时：finalize

```bash
python scripts/finalize.py --record runs/exp_xxx/record.json \
  --results runs/exp_xxx/results.json \
  --out-dir runs/exp_xxx
```

finalize 会：

1. 按 schema 校验记录完整性，列出所有缺失项（缺失决策、报错未记录、缺产物路径等）
2. 渲染生成 `human.md` 与 `agent.md`
3. 给出 PASS / WARN / FAIL 结论；FAIL 时 agent 必须补全后重跑 finalize

### 4. 渲染（finalize 已含；单独重渲染）

```bash
python scripts/render.py render --record runs/exp_xxx/record.json --out-dir runs/exp_xxx
```

## 行为约束细则

- **单一事实源**：`record.json` 是唯一手工维护对象。`human.md` 与 `agent.md` 只由脚本生成，改内容先改 record 再重渲染。
- **记录失败不阻塞实验**：若磁盘/权限问题导致写入失败，打印 `WARN: log write failed, will backfill at finalize` 并继续实验。
- **心跳**：长实验中每完成一个阶段（epoch、数据批次、评测组），检查一次 record 是否需要补记。不需要则跳过，不产生噪音。
- **默认值不进人版**：只有偏离论文/默认配置的参数才值得写入人版参数表。
- **禁止事项**：
  - ❌ 人版写成详细报告
  - ❌ 只记接口不执行检查点
  - ❌ 人版与 agent 版分别手写
  - ❌ 为记录暂停或中断实验
  - ❌ 人版堆砌环境/命令细节

## 自检清单

开跑前/中/结束各查什么，见 `references/checklist.md`。实验结束前必须逐项过一遍。

## 验收标准

本 Skill 合格的判定：

1. agent 在无额外人工提示下跑完一次实验，自动产出两份日志
2. 人版一屏内读出主要参数与效果
3. 另一个 agent 仅凭 agent 版可重建实验配置（dry-run 验证）
4. 两份日志无信息冲突（同源渲染保证）
5. 日志写入失败不阻塞实验本身
