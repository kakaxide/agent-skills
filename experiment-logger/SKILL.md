---
name: experiment-logger
description: 项目实验全流程追踪 Skill：流程文档（PLAN.md）+ 实验日志双记录。当用户要求复现项目/论文、执行多阶段实验（训练→评测→分析→对照）或跑任何会产生结果数据的脚本时，agent 必须先建/更新流程文档让用户随时知道做到哪一步、卡在哪里，并在固定检查点记录实验（人版极简，agent 版可复现）。触发词包括：复现、实验、训练、评测、跑模型、baseline、消融、项目等。
---

# 你必须记录

以下约束为命令式，优先级高于本文件中其它一切内容：

1. **接到"复现/项目/多阶段实验"类任务，你必须先建流程文档**：用 `project init` 生成 PLAN.md（简明步骤 + 目标），未建流程前不得开跑。用户靠它知道你在做哪一步、卡在哪里。
2. **实验开始前，你必须先确认日志存放根目录**：首次使用时必须询问用户并记住该默认目录；后续实验默认复用，仅在用户要求更换时重新询问。未确认目录前不得开跑。
3. **实验开始前，你必须先登记目标**：哪篇论文、哪张表/图、期望指标。未登记不得开跑。
4. **做出任何非显然选择时（换版本、跳步骤、改参数、换数据），你必须立即写一条决策记录。**
5. **任何报错后重试之前，你必须先写一条 failed_attempt，再继续。**
6. **每完成流程中的一个步骤，你必须用 `project status` 标记状态、写一句结果小结、并链接该步的实验记录。** 只标"已完成"不留小结不算完成。
7. **实验结束时，你必须运行 finalize 生成双日志并更新全局索引。finalize 未完成，实验就不算结束。**
8. **记录失败时，你不得中断实验。打印一行警告后继续实验，结束时补记。**
9. **PLAN.md 与双日志必须由脚本从 canonical 记录渲染生成，严禁手改。**
10. **人版严禁出现完整命令、环境细节、失败过程。这些只属于 agent 版。**

---

## 本 Skill 如何保证 agent 时刻记得记录

记录是 agent 行为的强制环节，不是可选功能。本 Skill 通过强制检查点把记录织入工作流，而不是依赖 agent 自觉：

| 检查点 | 时机 | agent 必须做什么 | 未做的后果 |
|---|---|---|---|
| 建流程文档 | 接到项目/复现任务时 | `project init` 建步骤清单 | 用户无法追踪进度，不得开跑 |
| 确认日志目录 | 首次使用 / 用户要求更换时 | 询问用户日志根目录并记住默认（写入 `~/.experiment-logger/log_root.txt`） | 不得开跑 |
| 开跑前 | 每步实验脚本执行前 | 创建 canonical 记录（项目实验加 `--project`），登记复现目标 | 不得开跑 |
| 决策时 | 做出非显然选择时 | `add --type decision` | finalize 时被检出 |
| 失败时 | 报错后、重试前 | `add --type failed_attempt` | finalize 时被检出 |
| 心跳 | 长实验每阶段/里程碑收束 | `add --type event` / `add --type milestone` | 结论演进缺档 |
| 步骤完成 | 流程某步收束 | `project status --status done --summary ... --link <record>` | PLAN.md 停留在旧状态，用户误判卡点 |
| 结束时 | 实验完成/中止 | finalize 渲染双日志并更新 INDEX.md | 实验状态记为未完成 |

提醒机制的三条设计原则：

- **轻量不阻塞**：检查点只要求追加记录，不拦截实验执行。时间戳由工具自动打，不依赖手填。
- **有痕迹**：被跳过的检查点不会消失，finalize 校验列出所有缺失项（含时间戳乱序、未来时间戳）。
- **单一事实源**：agent 全程只维护 canonical 记录（record.json 与 plan.json），PLAN.md / human.md / agent.md 均为其渲染视图，从机制上杜绝多份手写日志的分叉。

## 双层文档结构

### 流程文档 PLAN.md（给人看：做到哪了）

用户交给 agent 一个项目/复现任务后，agent 先给出简明但含主要内容的流程。每个步骤带状态、一句话小结、实验记录索引：

```
| # | 步骤 | 状态 | 小结 | 实验记录 |
| 2 | 训练基线 | ✅ 已完成 | 基线 0.867，超论文 0.5% | [exp_baseline](./steps/exp_baseline/human.md) |
| 3 | 插入攻击训练 | 🔄 进行中 | - | - |
```

- 步骤做完不只标"已完成"，还要写一句实验结果小结，详情索引到该步的实验记录 human.md
- `project list` 一条命令定位当前卡点（如"当前卡在 step 3"）
- PLAN.md 由 plan.json 渲染，禁止手改

### 实验记录（每步一份：配置/结果/产物）

- **人版 human.md**：不超过 10 项关键参数（训练轮次、batch_size 等核心超参；默认值不写）+ 核心指标与基线对照 + 关键结论 + 一行状态。finalize 校验行数：超 10 行 WARN，超 15 行 FAIL。
- **agent 版 agent.md**：可复现所需的一切——环境指纹、完整命令、全量配置、数据溯源、commit、失败尝试、决策理由、产物路径（如生成权重的确切位置）。

INDEX 核心指标由 `results.headline` 显式指定（按重要性排序），未指定才退回前 3 项——哪几个指标上索引是实验作者的决定，不由字典插入顺序决定。

## 日志存放与组织

日志是用户的历史资产，存放位置必须由用户掌控：

- **日志根目录（log_root）由用户指定**。agent 首次使用时必须询问并写入 `~/.experiment-logger/log_root.txt`；之后默认复用，仅用户要求更换时重新询问。

```
<log_root>/
├── INDEX.md                        # 全局实验索引（跨项目），finalize 自动维护
├── exp_xxx/                        # 独立实验（不属于任何项目）
│   └── record.json / human.md / agent.md
└── projects/<项目名>/
    ├── plan.json                   # 流程 canonical（脚本维护）
    ├── PLAN.md                     # 流程文档（渲染产物）
    └── steps/
        ├── step1_实验/record.json / human.md / agent.md
        └── step2_实验/...
```

## 使用接口

canonical 记录结构见 `schema/record.schema.json`。

### 1. 项目开始：建流程文档

```bash
python scripts/render.py project init --log-root "D:\experiment-logs" --save-default \
  --name repro_act --title "复现 ACT 插入攻击" --paper "ACT 2025" --target "Table 2" \
  --step "环境与数据准备:装环境、整理测试集" \
  --step "训练基线:复现论文基线" \
  --step "插入攻击训练:复现插入模块" \
  --step "评测与分析:指标对照论文"
```

### 2. 每步实验：创建记录、过程记录

```bash
# 挂到项目下（省略 --project 则为独立实验）
python scripts/render.py init --project repro_act \
  --exp-id exp_baseline --title "基线训练" --paper "ACT 2025" \
  --target "Table 2" --model "resnet50" --dataset "ImageNet"

# 过程记录（时间戳自动；复杂更新用 set，不再需要手写 JSON 脚本）
python scripts/render.py add --record <record> --type decision --content "PyTorch 降到 2.0 对齐论文"
python scripts/render.py add --record <record> --type failed_attempt --content "OOM，batch 32->16" --error "CUDA out of memory"
python scripts/render.py add --record <record> --type milestone --name "训练收束" --content "loss 0.31 未发散"
python scripts/render.py set --record <record> --key results.metrics.eval_success --value 0.867
python scripts/render.py set --record <record> --key results.summary --value "基线达成，超论文 0.5%"
python scripts/render.py set --record <record> --key results.headline --value '["eval_success_60000step"]'
python scripts/render.py set --record <record> --key results.findings --value '[{"conclusion":"...","evidence":"...","confidence":"high"}]'
```

### 3. 步骤收束：标记流程 + finalize

```bash
# finalize：校验 + 渲染双日志 + 更新 INDEX（校验时间戳乱序/未来时间、参数行数、路径存在性）
python scripts/finalize.py --record <log_root>/projects/repro_act/steps/exp_baseline/record.json --strict

# 更新流程文档：状态 + 小结 + 索引实验记录
python scripts/render.py project status --name repro_act --step 2 \
  --status done --summary "基线 0.867，超论文 0.5%" --link <record.json 路径>

# 卡点定位与 A/B 指标对照
python scripts/render.py project list
python scripts/render.py compare --record-a <record_A> --record-b <record_B> [--metrics "acc,loss"]
```

## 行为约束细则

- **单一事实源**：record.json 与 plan.json 是唯二手工维护对象（且优先用 add/set 命令维护）。渲染产物只由脚本生成，改内容先改 canonical 再重渲染。
- **记录失败不阻塞实验**：写入失败打印 `WARN: log write failed, will backfill at finalize` 并继续。
- **默认值不进人版**：只有偏离论文/默认配置的参数才进人版参数表。
- **分析产出进 findings**：失败原因分析、外部对照结论用结构化 findings（结论/依据/置信度），不塞进 events 或 summary。
- **禁止事项**：
  - ❌ 人版写成详细报告
  - ❌ 只标"已完成"不写小结不链实验记录
  - ❌ 手改 PLAN.md / human.md / agent.md
  - ❌ 手填时间戳（工具自动打）
  - ❌ 人版堆砌环境/命令细节

## 自检清单

开跑前/中/结束各查什么，见 `references/checklist.md`。实验结束前必须逐项过一遍。

## 验收标准

1. 用户随时打开 PLAN.md 能看到 agent 做到哪一步、卡在哪里
2. agent 在无额外提示下跑完一次实验，自动产出双日志并更新流程文档
3. 人版一屏内读出主要参数与效果
4. 另一个 agent 仅凭 agent 版可重建实验配置（dry-run 验证）
5. 两份日志无信息冲突（同源渲染保证）
6. 日志写入失败不阻塞实验本身
