# agent 自检清单：项目流程追踪与实验日志记录

> 每次实验结束前逐项过一遍。任何一项不满足，先补记录再结束。

## 项目开始时

- [ ] 项目/复现类任务已建流程文档：`project init` 生成了含主要步骤的 PLAN.md，未建流程不得开跑
- [ ] 步骤描述简明但含主要内容，用户不看对话也能知道整体计划

## 开跑前

- [ ] 日志根目录已确认：首次使用已询问用户并保存默认（`~/.experiment-logger/log_root.txt`）；后续实验复用默认，用户要求更换时才重新询问
- [ ] 属于项目的实验已用 `init --project` 挂到流程下（位于 `<log_root>/projects/<项目>/steps/`）
- [ ] 已创建 canonical 记录（`record.json`），包含 experiment_id 与 title
- [ ] 已登记复现目标：哪篇论文（goal.paper）、哪张表/图（goal.target）、期望指标（goal.expected_metrics）
- [ ] 未登记目标时不得开跑；如确需跳过，必须在对话中显式输出跳过声明

## 实验过程中

- [ ] 每次做出非显然选择（换版本、跳步骤、改参数、换数据），立即 `add --type decision`，写明"做了什么、为什么、放弃了什么"
- [ ] 每次报错后、重试之前，先 `add --type failed_attempt`（含关键报错信息）
- [ ] 长实验每完成一个阶段收束点，记 `add --type event`（过程事件）；阶段结论用 `add --type milestone`（阶段小结）
- [ ] 分析产出（失败原因、外部对照结论）用结构化 findings，不塞进 events/summary
- [ ] 复杂更新用 `set` 点路径赋值，不手写 JSON 脚本；时间戳由工具自动打
- [ ] 默认值 / 未偏离论文的配置不写进人版参数表
- [ ] 记录写入失败时不中断实验，打印警告后继续，finalize 时补记

## 步骤完成时

- [ ] 已用 `project status` 标记步骤状态，不只标"已完成"，还写了一句结果小结
- [ ] 已用 `--link` 把该步实验记录索引进 PLAN.md
- [ ] 用户打开 PLAN.md 能看出当前做到哪一步、卡在哪里（`project list` 验证）

## 实验结束时

- [ ] 已填写 results：核心指标 metrics、headline（哪几个指标上索引，按重要性排序）、与论文/基线的对照 comparison（含偏差与出处）、一句话结论 summary
- [ ] 已填写 artifacts：checkpoint / 日志 / 指标文件 / 配置 / 图的路径（含生成权重位置）
- [ ] 已运行 `scripts/finalize.py`，生成 human.md 与 agent.md；时间戳乱序/未来时间戳 WARN 已处理
- [ ] `<log_root>/INDEX.md` 已追加本次实验摘要行（日期、ID、标题、状态、headline 指标、链接）
- [ ] finalize 结论为 PASS（或 WARN 项已逐条确认可接受 / 已补全）；参数表未超限（>10 行 WARN，>15 行 FAIL）
- [ ] 人版一屏内可读出主要参数与效果，无命令、无环境细节、无失败过程
- [ ] agent 版包含：环境指纹、完整命令、全量配置、数据溯源、代码 commit、全部失败尝试与决策、产物路径
- [ ] PLAN.md / human.md / agent.md 均由脚本渲染自同一份 canonical 记录，未手改渲染产物

## 可复现 dry-run（抽查）

- [ ] 另一个 agent 仅凭 agent.md 能列出：模型与版本、数据与预处理、命令序列、关键超参、硬件与随机种子
- [ ] 若无法满足，说明 agent 版缺信息，回填 record.json 后重渲染
- [ ] A/B 对照类实验用 `compare` 输出指标对照表，不靠人工开两个目录
