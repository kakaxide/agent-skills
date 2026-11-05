# Agent Skills 集合

个人 Agent Skill 仓库，收录为 AI Agent 编写的可复用技能（遵循 `SKILL.md` 目录规范）。每个子目录是一个独立 Skill，可直接复制或链接到 agent 的技能目录中使用。

## 目录结构

```
agent-skills/
├── experiment-logger/     # 项目实验全流程追踪：流程文档 + 双日志
│   ├── SKILL.md           # 主文件：触发条件、强制提醒点、接口清单、行为约束
│   ├── schema/
│   │   └── record.schema.json   # canonical 记录结构（单一事实源）
│   ├── templates/
│   │   ├── human.md.tpl   # 人版日志模板（极简：主要参数 + 效果 + 一行状态）
│   │   ├── agent.md.tpl   # agent 版日志模板（可复现级别详尽）
│   │   └── plan.md.tpl    # 项目流程文档模板（步骤状态 + 小结 + 索引）
│   ├── scripts/
│   │   ├── render.py      # init/add/set/render/project/compare：维护 canonical 记录
│   │   └── finalize.py    # 实验结束校验 + 渲染 + PASS/WARN/FAIL 结论
│   └── references/
│       └── checklist.md   # agent 自检清单：项目开始/开跑前/中/结束各查什么
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

## experiment-logger：项目实验全流程追踪 Skill

核心定位：**流程文档 + 实验日志双层记录**。agent 接到项目/复现任务先建流程文档（PLAN.md），用户随时能看到做到哪一步、卡在哪里；每步实验产出双日志（人版极简，agent 版可复现），步骤完成后在 PLAN.md 上标记状态、写小结并索引实验记录。

### 双层文档

| 层 | 文件 | 内容 |
|---|---|---|
| 流程文档 | PLAN.md | 步骤清单 + 状态（⬜🔄✅❌）+ 一句话结果小结 + 实验记录索引，由 plan.json 渲染 |
| 人版日志 | human.md | ≤10 项主要参数、核心指标与基线对照、关键结论、一行状态。一屏读完 |
| agent 版日志 | agent.md | 环境指纹、完整命令、全量配置、数据溯源、commit、失败尝试、决策、产物路径（含权重位置） |

三层文档全部由脚本从 canonical 记录（plan.json / record.json）渲染生成，从机制上禁止手写分叉。

### 快速上手

日志根目录由用户掌控：agent 首次使用必须询问并记住默认（`~/.experiment-logger/log_root.txt`）。

```bash
# 1. 项目开始：建流程文档（复现类任务必须先做这步）
python scripts/render.py project init --log-root "D:\experiment-logs" --save-default \
  --name repro_act --title "复现 ACT 插入攻击" --paper "ACT 2025" --target "Table 2" \
  --step "环境与数据准备:装环境" --step "训练基线:复现基线" --step "评测与分析:对照论文"

# 2. 每步实验：创建记录（--project 挂到流程下）+ 过程记录（时间戳自动）
python scripts/render.py init --project repro_act --exp-id exp_baseline \
  --title "基线训练" --paper "ACT 2025" --target "Table 2" --model "resnet50" --dataset "ImageNet"
python scripts/render.py add --record <record> --type failed_attempt --content "OOM" --error "CUDA out of memory"
python scripts/render.py set --record <record> --key results.metrics.eval_success --value 0.867
python scripts/render.py set --record <record> --key results.headline --value '["eval_success"]'   # INDEX 显示哪些指标由实验作者决定

# 3. 步骤收束：finalize + 更新流程文档（状态 + 小结 + 索引实验记录）
python scripts/finalize.py --record <record> --strict
python scripts/render.py project status --name repro_act --step 2 \
  --status done --summary "基线 0.867" --link <record>

# 4. 进度定位与 A/B 对照
python scripts/render.py project list        # 输出"当前卡在 step N"
python scripts/render.py compare --record-a <A> --record-b <B>
```

日志目录结构：

```
<log_root>/
├── INDEX.md                        # 全局实验索引（跨项目），finalize 自动维护
├── exp_xxx/                        # 独立实验
└── projects/<项目名>/
    ├── plan.json / PLAN.md         # 流程 canonical 与渲染产物
    └── steps/<实验ID>/              # 每步实验：record.json / human.md / agent.md
```

脚本仅依赖 Python 标准库。finalize 校验含：时间戳乱序/未来时间告警、参数表限行（>10 行 WARN，>15 行 FAIL）、comparison/产物路径存在性、human.md 一屏检查。INDEX 核心指标由 `results.headline` 显式指定，不受字典插入顺序影响。

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
