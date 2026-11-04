# Agent Skills 集合

个人 Agent Skill 仓库，收录为 AI Agent 编写的可复用技能（遵循 `SKILL.md` 目录规范）。每个子目录是一个独立 Skill，可直接复制或链接到 agent 的技能目录中使用。

## 目录结构

```
agent-skills/
├── experiment-logger/     # 实验日志 Skill：强制 agent 在实验过程中记录
│   ├── SKILL.md           # 主文件：触发条件、强制提醒点、接口清单、行为约束
│   ├── schema/
│   │   └── record.schema.json   # canonical 记录结构（单一事实源）
│   ├── templates/
│   │   ├── human.md.tpl   # 人版日志模板（极简：主要参数 + 效果 + 一行状态）
│   │   └── agent.md.tpl   # agent 版日志模板（可复现级别详尽）
│   ├── scripts/
│   │   ├── render.py      # init / add / render：维护 canonical 记录并渲染双日志
│   │   └── finalize.py    # 实验结束校验 + 渲染 + PASS/WARN/FAIL 结论
│   └── references/
│       └── checklist.md   # agent 自检清单：开跑前/中/结束各查什么
└── paper-explainer/       # 文献讲解 Skill：结合论文原图讲解论文
    ├── SKILL.md           # 主文件：防幻觉条款、多模态阀门、讲解风格约束
    ├── scripts/
    │   ├── extract.py     # PDF/DOCX 全文 + 原图提取（图题定位、区域裁剪）
    │   └── build_html.py  # 讲解内容 + 论文原图 -> 单文件 HTML（base64 内嵌）
    ├── templates/
    │   └── report.html.tpl  # 低饱和学术风 HTML 模板
    └── references/
        └── figure-rules.md  # 图提取与配对规则、过滤阈值、降级策略
```

## experiment-logger：实验日志 Skill

核心定位：**持续提醒并约束 agent 在实验过程中记录实验**，记录是强制环节而非可选功能。产出双日志：

| 日志 | 受众 | 内容边界 |
|---|---|---|
| 人版 human.md | 人 | 不超过 10 项主要参数、核心指标与基线对照、一行状态结论。一屏读完 |
| agent 版 agent.md | agent | 环境指纹、完整命令、全量配置、数据溯源、commit、失败尝试、决策理由、产物路径 |

设计原则：人版做减法、agent 版做加法；两份日志由同一份 canonical 记录（record.json）渲染生成，从机制上禁止分别手写导致分叉。

### 快速上手

日志是用户的历史资产：agent 首次使用时必须询问日志根目录并记住默认（存于 `~/.experiment-logger/log_root.txt`），之后每次实验在该根目录下建独立子目录，finalize 自动维护全局索引 `INDEX.md`。

```bash
# 1. 首次使用：询问用户日志根目录后，--save-default 记住默认
#    后续实验省略 --log-root，自动复用默认目录
python scripts/render.py init --log-root "D:\experiment-logs" --save-default \
  --title "复现 XX 论文 Table 2" --paper "论文标题" --target "Table 2" \
  --model "resnet50" --dataset "ImageNet"

# 2. 过程中记录决策与失败（报错后、重试前必须先记一条）
python scripts/render.py add --record <log_root>/exp_001/record.json \
  --type decision --content "PyTorch 2.1 降级到 2.0，对齐论文环境"

# 3. 实验结束 finalize：校验完整性 + 生成 human.md / agent.md + 更新 INDEX.md
python scripts/finalize.py --record <log_root>/exp_001/record.json --strict
```

日志目录结构：

```
<log_root>/
├── INDEX.md              # 全局索引，一实验一行，自动维护
└── exp_20261103_1430/    # 单次实验目录
    ├── record.json       # canonical 记录（单一事实源）
    ├── human.md          # 人版日志
    └── agent.md          # agent 版日志
```

脚本仅依赖 Python 标准库，无需安装额外包。

### 强制提醒点

确认日志目录（首次询问并记住默认）→ 开跑前登记目标 → 关键决策时记录 → 失败/重试时记录 → 周期性心跳补记 → 结束时 finalize 并更新全局索引。未记录不会阻塞实验，但会在 finalize 校验报告中暴露并要求补全。

详细行为约束见 [experiment-logger/SKILL.md](experiment-logger/SKILL.md)。

## paper-explainer：图文结合文献讲解 Skill

核心定位：**读论文必须结合图**。好论文的核心信息在图里，纯文本讲解丢掉一半信息。输入 PDF 或 Word 论文，产出图文混排的单文件 HTML 讲解。

| 环节 | 做法 |
|---|---|
| 图提取 | PDF 双通道：嵌入位图定位 + 页面渲染按图题裁剪（矢量图/组合图都能截全）；Word 从 media 目录直接解出 |
| 讲解结构 | 背景与动机 → 方法 → 实验效果三段式，论文原图嵌在它解释的那段文字之后，图下紧跟图解 |
| 多模态阀门 | 讲解前自检：非多模态模型必须询问用户（切换模型或确认降级），不得擅自继续；降级产出的 HTML 顶部显著标注"非多模态生成" |
| 防幻觉 | 讲解中的数字必须来自原文，禁止从图中估读；看不清的图只放图不写图解，宁缺毋滥 |
| 语言风格 | 朴素可靠、简单直击本质，禁止模板腔、蹩脚比喻和无数字支撑的空话 |

```bash
# 1. 提取全文与原图
python scripts/extract.py --input 论文.pdf --workdir 解析输出目录

# 2. agent 通读全文 + 逐图理解，撰写三段式讲解 content.md（约定见 SKILL.md）

# 3. 生成单文件 HTML（论文原图 base64 内嵌，离线可开）
python scripts/build_html.py --content content.md --workdir 解析输出目录 --out 论文讲解.html
```

依赖：pymupdf（PDF 提图，安装前需征得用户同意）；Word 解析与 HTML 生成仅用标准库。

详细行为约束见 [paper-explainer/SKILL.md](paper-explainer/SKILL.md)。

## 后续 Skill

后续新增的 Skill 将以独立子目录形式放入本仓库根目录，并在本 README 中补充说明。
