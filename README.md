# Agent Skills 集合

个人 Agent Skill 仓库，收录为 AI Agent 编写的可复用技能（遵循 `SKILL.md` 目录规范）。每个子目录是一个独立 Skill，可直接复制或链接到 agent 的技能目录中使用。

## 目录结构

```
agent-skills/
└── experiment-logger/     # 实验日志 Skill：强制 agent 在实验过程中记录
    ├── SKILL.md           # 主文件：触发条件、强制提醒点、接口清单、行为约束
    ├── schema/
    │   └── record.schema.json   # canonical 记录结构（单一事实源）
    ├── templates/
    │   ├── human.md.tpl   # 人版日志模板（极简：主要参数 + 效果 + 一行状态）
    │   └── agent.md.tpl   # agent 版日志模板（可复现级别详尽）
    ├── scripts/
    │   ├── render.py      # init / add / render：维护 canonical 记录并渲染双日志
    │   └── finalize.py    # 实验结束校验 + 渲染 + PASS/WARN/FAIL 结论
    └── references/
        └── checklist.md   # agent 自检清单：开跑前/中/结束各查什么
```

## experiment-logger：实验日志 Skill

核心定位：**持续提醒并约束 agent 在实验过程中记录实验**，记录是强制环节而非可选功能。产出双日志：

| 日志 | 受众 | 内容边界 |
|---|---|---|
| 人版 human.md | 人 | 不超过 10 项主要参数、核心指标与基线对照、一行状态结论。一屏读完 |
| agent 版 agent.md | agent | 环境指纹、完整命令、全量配置、数据溯源、commit、失败尝试、决策理由、产物路径 |

设计原则：人版做减法、agent 版做加法；两份日志由同一份 canonical 记录（record.json）渲染生成，从机制上禁止分别手写导致分叉。

### 快速上手

```bash
# 1. 开跑前登记复现目标（未登记不得开跑）
python scripts/render.py init --out runs/exp_001/record.json \
  --title "复现 XX 论文 Table 2" --paper "论文标题" --target "Table 2" \
  --model "resnet50" --dataset "ImageNet"

# 2. 过程中记录决策与失败（报错后、重试前必须先记一条）
python scripts/render.py add --record runs/exp_001/record.json \
  --type decision --content "PyTorch 2.1 降级到 2.0，对齐论文环境"

# 3. 实验结束 finalize：校验完整性 + 生成 human.md / agent.md
python scripts/finalize.py --record runs/exp_001/record.json --strict
```

脚本仅依赖 Python 标准库，无需安装额外包。

### 强制提醒点

开跑前登记 → 关键决策时记录 → 失败/重试时记录 → 周期性心跳补记 → 结束时 finalize。未记录不会阻塞实验，但会在 finalize 校验报告中暴露并要求补全。

详细行为约束见 [experiment-logger/SKILL.md](experiment-logger/SKILL.md)。

## 后续 Skill

后续新增的 Skill 将以独立子目录形式放入本仓库根目录，并在本 README 中补充说明。
